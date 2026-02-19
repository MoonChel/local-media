from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml


@dataclass
class AuthConfig:
    enabled: bool = False
    username: str = "admin"
    password: str = "changeme"


@dataclass
class MediaSource:
    id: str
    label: str
    path: str


@dataclass
class LibraryConfig:
    sources: List[MediaSource]
    extensions: List[str]
    scan_interval_seconds: int = 21600


@dataclass
class WatcherConfig:
    enabled: bool = True
    debounce_seconds: int = 3


@dataclass
class StateConfig:
    db_path: str = "/config/state.db"


@dataclass
class DownloadsConfig:
    enabled: bool = True
    torrent_staging_dir: str = "/config/torrents"


@dataclass
class AppConfig:
    auth: AuthConfig
    library: LibraryConfig
    watcher: WatcherConfig
    state: StateConfig
    downloads: DownloadsConfig


def get_config_path() -> Path:
    return Path(os.getenv("APP_CONFIG", "/config/config.yaml"))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_sources(raw_library: dict) -> List[MediaSource]:
    """Parse sources from library config"""
    sources_raw = raw_library.get("sources", [])
    if not isinstance(sources_raw, list):
        return []
    
    sources = []
    for item in sources_raw:
        if not isinstance(item, dict):
            continue
        src_id = str(item.get("id", "")).strip()
        label = str(item.get("label", src_id)).strip() or src_id
        path = str(item.get("path", "")).strip()
        if src_id and path:
            sources.append(MediaSource(id=src_id, label=label, path=path))
    return sources


def load_config() -> AppConfig:
    config_path = get_config_path()
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    # Use defaults for auth
    auth = AuthConfig(enabled=False, username="admin", password="changeme")

    library_raw = raw.get("library") or {}
    sources = _normalize_sources(library_raw)
    extensions = [
        ext.lower()
        for ext in (library_raw.get("extensions") or [".mp4", ".mkv", ".avi", ".mov", ".webm"])
    ]
    library = LibraryConfig(
        sources=sources,
        extensions=extensions,
        scan_interval_seconds=int(library_raw.get("scan_interval_seconds", 21600)),
    )

    # Create source folders if they don't exist
    for source in sources:
        source_path = Path(source.path)
        source_path.mkdir(parents=True, exist_ok=True)

    # Use defaults for watcher, state, and downloads
    watcher = WatcherConfig(enabled=True, debounce_seconds=3)
    state = StateConfig(db_path="/config/state.db")
    downloads = DownloadsConfig(
        enabled=True,
        torrent_staging_dir="/config/torrents",
    )

    # Allow environment variable overrides for auth
    auth.enabled = _env_bool("AUTH_ENABLED", auth.enabled)
    auth.username = os.getenv("APP_USER", auth.username)
    auth.password = os.getenv("APP_PASSWORD", auth.password)

    return AppConfig(
        auth=auth,
        library=library,
        watcher=watcher,
        state=state,
        downloads=downloads,
    )
