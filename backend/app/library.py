from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from sqlalchemy.orm import Session

from .config import AppConfig
from .models import Video, Progress

logger = logging.getLogger(__name__)


class LibraryIndex:
    def __init__(self, config: AppConfig, session_maker):
        self.config = config
        self.session_maker = session_maker
        self._scan_lock = asyncio.Lock()

    @staticmethod
    def stable_id(source_id: str, rel_path: str) -> str:
        source = f"{source_id}/{rel_path}".encode("utf-8")
        return hashlib.sha1(source).hexdigest()[:16]

    def _is_video(self, path: Path) -> bool:
        return path.suffix.lower() in self.config.library.extensions

    async def scan(self) -> None:
        async with self._scan_lock:
            session: Session = self.session_maker()
            try:
                seen = set()
                for source in self.config.library.sources:
                    root_path = Path(source.path)
                    if not root_path.exists():
                        continue

                    for file_path in root_path.rglob("*"):
                        if not file_path.is_file() or not self._is_video(file_path):
                            continue

                        rel_path = str(file_path.relative_to(root_path))
                        vid = self.stable_id(source.id, rel_path)
                        stat = file_path.stat()
                        title = file_path.stem

                        # Upsert video
                        video = session.query(Video).filter(Video.id == vid).first()
                        if video:
                            video.source_id = source.id
                            video.source_label = source.label
                            video.abs_path = str(file_path)
                            video.title = title
                            video.size = stat.st_size
                            video.mtime = stat.st_mtime
                        else:
                            video = Video(
                                id=vid,
                                source_id=source.id,
                                source_label=source.label,
                                rel_path=rel_path,
                                abs_path=str(file_path),
                                title=title,
                                size=stat.st_size,
                                mtime=stat.st_mtime,
                            )
                            session.add(video)
                        seen.add(vid)

                # Delete videos not seen
                if seen:
                    session.query(Video).filter(Video.id.notin_(seen)).delete(synchronize_session=False)
                else:
                    session.query(Video).delete()

                session.commit()
            finally:
                session.close()

    def list_videos(self) -> List[dict]:
        session: Session = self.session_maker()
        try:
            results = (
                session.query(Video, Progress.position_seconds, Progress.updated_at)
                .outerjoin(Progress, Video.id == Progress.video_id)
                .order_by(Video.source_label, Video.rel_path)
                .all()
            )
            
            videos = []
            for video, position_seconds, progress_updated_at in results:
                video_dict = video.to_dict()
                video_dict["position_seconds"] = position_seconds or 0
                video_dict["progress_updated_at"] = progress_updated_at
                videos.append(video_dict)
            
            return videos
        finally:
            session.close()

    def get_video(self, video_id: str):
        if not video_id or not isinstance(video_id, str):
            logger.warning(f"Invalid video_id type: {type(video_id)} value: {video_id}")
            return None
        
        session: Session = self.session_maker()
        try:
            video = session.query(Video).filter(Video.id == video_id).first()
            return video.to_dict() if video else None
        finally:
            session.close()

    def get_progress(self, video_id: str) -> float:
        session: Session = self.session_maker()
        try:
            progress = session.query(Progress).filter(Progress.video_id == video_id).first()
            return float(progress.position_seconds) if progress else 0.0
        finally:
            session.close()

    def set_progress(self, video_id: str, position_seconds: float) -> None:
        session: Session = self.session_maker()
        try:
            now = datetime.now(timezone.utc).isoformat()
            progress = session.query(Progress).filter(Progress.video_id == video_id).first()
            
            if progress:
                progress.position_seconds = max(0, position_seconds)
                progress.updated_at = now
            else:
                progress = Progress(
                    video_id=video_id,
                    position_seconds=max(0, position_seconds),
                    updated_at=now
                )
                session.add(progress)
            
            session.commit()
        finally:
            session.close()

    def delete_video(self, video_id: str) -> None:
        """Delete a video file and remove from database"""
        session: Session = self.session_maker()
        try:
            video = session.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError("Video not found")
            
            file_path = Path(video.abs_path)
            if file_path.exists():
                file_path.unlink()
            
            # Delete from database (cascade will handle progress)
            session.delete(video)
            session.commit()
        finally:
            session.close()

    def move_video(self, video_id: str, target_source_id: str, target_rel_path: str) -> dict:
        """Move a video to a different source/path"""
        session: Session = self.session_maker()
        try:
            video = session.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError("Video not found")
            
            # Find target source
            target_source = next((s for s in self.config.library.sources if s.id == target_source_id), None)
            if not target_source:
                raise ValueError("Target source not found")
            
            # Prepare paths
            old_path = Path(video.abs_path)
            if not old_path.exists():
                raise ValueError("Source file not found")
            
            target_dir = Path(target_source.path) / Path(target_rel_path).parent
            target_dir.mkdir(parents=True, exist_ok=True)
            
            new_path = Path(target_source.path) / target_rel_path
            if new_path.exists():
                raise ValueError("Target file already exists")
            
            # Move file
            old_path.rename(new_path)
            
            # Update or create new video entry
            new_id = self.stable_id(target_source_id, target_rel_path)
            stat = new_path.stat()
            
            if new_id != video_id:
                # Copy progress to new ID
                old_progress = session.query(Progress).filter(Progress.video_id == video_id).first()
                if old_progress:
                    new_progress = Progress(
                        video_id=new_id,
                        position_seconds=old_progress.position_seconds,
                        updated_at=old_progress.updated_at
                    )
                    session.add(new_progress)
                
                # Delete old video
                session.delete(video)
                
                # Create new video
                new_video = Video(
                    id=new_id,
                    source_id=target_source.id,
                    source_label=target_source.label,
                    rel_path=target_rel_path,
                    abs_path=str(new_path),
                    title=new_path.stem,
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                )
                session.add(new_video)
            else:
                # Update existing video
                video.source_id = target_source.id
                video.source_label = target_source.label
                video.rel_path = target_rel_path
                video.abs_path = str(new_path)
                video.title = new_path.stem
                video.size = stat.st_size
                video.mtime = stat.st_mtime
            
            session.commit()
            
            # Return updated video
            result_video = session.query(Video).filter(Video.id == new_id).first()
            return result_video.to_dict() if result_video else None
        finally:
            session.close()


class ScanScheduler:
    def __init__(self, index: LibraryIndex, debounce_seconds: int = 3):
        self.index = index
        self.debounce_seconds = debounce_seconds
        self._task = None

    def trigger(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_debounced())

    async def _run_debounced(self) -> None:
        await asyncio.sleep(self.debounce_seconds)
        await self.index.scan()


async def run_periodic_scan(index: LibraryIndex, interval_seconds: int):
    while True:
        await asyncio.sleep(interval_seconds)
        await index.scan()


async def run_file_watcher(config: AppConfig, scheduler: ScanScheduler):
    try:
        from watchfiles import awatch
    except Exception:
        return

    roots = [src.path for src in config.library.sources if Path(src.path).exists()]
    if not roots:
        return

    ignore_suffixes = (".part", ".!qB", ".tmp", ".crdownload")
    async for changes in awatch(*roots, recursive=True):
        should_scan = False
        for _, changed_path in changes:
            if changed_path.endswith(ignore_suffixes):
                continue
            should_scan = True
            break
        if should_scan:
            scheduler.trigger()
