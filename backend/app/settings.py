from __future__ import annotations

from pathlib import Path
import shutil
from threading import Lock

import yaml

from .config import MediaSource


class SettingsStore:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._lock = Lock()

    def _load_raw(self) -> dict:
        if not self.config_path.exists():
            return {}
        with self.config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _save_raw(self, raw: dict) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(raw, f, sort_keys=False)

    def _delete_path(self, path: Path) -> None:
        if not path.exists():
            return
        # For bind mounts/mount points, deleting the mount dir itself fails with EBUSY.
        # In that case, delete contents so host data is removed while mount point remains.
        if path.is_mount():
            for child in path.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink(missing_ok=True)
            return
        shutil.rmtree(path)

    def get_settings(self) -> dict:
        with self._lock:
            raw = self._load_raw()
        library = raw.get("library") or {}
        sources = library.get("sources") or []
        player = raw.get("player") or {}
        return {
            "sources": sources,
            "downloads": raw.get("downloads") or {},
            "auth": {"enabled": bool((raw.get("auth") or {}).get("enabled", False))},
            "player": {
                "seek_time": int(player.get("seek_time", 10)),
            },
        }

    def update_player_settings(self, seek_time: int) -> None:
        if seek_time < 1:
            raise ValueError("Seek value must be >= 1 second")
        if seek_time > 600:
            raise ValueError("Seek value must be <= 600 seconds")
        with self._lock:
            raw = self._load_raw()
            player = raw.setdefault("player", {})
            player["seek_time"] = int(seek_time)
            # Remove old keys to keep config clean.
            player.pop("seek_backward_seconds", None)
            player.pop("seek_forward_seconds", None)
            self._save_raw(raw)

    def upsert_source(self, source: MediaSource, create_if_missing: bool = False) -> None:
        source_path = Path(source.path)
        if create_if_missing:
            source_path.mkdir(parents=True, exist_ok=True)
        if not source_path.exists() or not source_path.is_dir():
            raise ValueError("Folder does not exist")

        with self._lock:
            raw = self._load_raw()
            library = raw.setdefault("library", {})
            sources = library.setdefault("sources", [])
            if not isinstance(sources, list):
                sources = []
                library["sources"] = sources

            entry = {
                "id": source.id,
                "label": source.label,
                "path": str(source_path),
            }
            replaced = False
            for i, item in enumerate(sources):
                if isinstance(item, dict) and str(item.get("id", "")).strip() == source.id:
                    sources[i] = entry
                    replaced = True
                    break
            if not replaced:
                sources.append(entry)

            self._save_raw(raw)

    def delete_source(self, source_id: str, remove_from_disk: bool = True) -> None:
        with self._lock:
            raw = self._load_raw()
            library = raw.setdefault("library", {})
            sources = library.get("sources") or []
            removed = None
            kept = []
            for item in sources:
                if str((item or {}).get("id", "")).strip() == source_id:
                    removed = item
                else:
                    kept.append(item)
            if len(kept) == len(sources):
                raise ValueError("Source not found")
            if not kept:
                raise ValueError("At least one source is required")
            if remove_from_disk and isinstance(removed, dict):
                path = Path(str(removed.get("path", "")).strip())
                if path:
                    blocked = {Path("/"), Path("/data"), Path("/media"), Path("/config"), Path("/app")}
                    if path in blocked:
                        raise ValueError("Refusing to delete protected path")
                    try:
                        self._delete_path(path)
                    except Exception as e:
                        raise ValueError(f"Failed to remove folder from disk: {e}") from e

            library["sources"] = kept
            self._save_raw(raw)
