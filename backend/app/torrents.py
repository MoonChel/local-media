from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import libtorrent as lt
except ImportError:
    lt = None

from sqlalchemy.orm import Session
from .config import AppConfig
from .library import ScanScheduler
from .models import Download

logger = logging.getLogger(__name__)


class TorrentManager:
    def __init__(self, config: AppConfig, session_maker, scheduler: ScanScheduler):
        self.config = config
        self.session_maker = session_maker
        self.scheduler = scheduler
        self._tasks: dict[str, asyncio.Task] = {}
        self._session = None
        self._handles: dict[str, any] = {}
        
        if lt and self.config.downloads.enabled:
            # Initialize libtorrent session
            self._session = lt.session({'listen_interfaces': '0.0.0.0:6881'})
            logger.info("Libtorrent session initialized")

    def enabled(self) -> bool:
        return self.config.downloads.enabled and lt is not None

    def sources(self) -> list[dict]:
        return [
            {
                "id": src.id,
                "label": src.label,
                "path": src.path,
            }
            for src in self.config.library.sources
        ]

    def list_jobs(self) -> list[dict]:
        session: Session = self.session_maker()
        try:
            downloads = (
                session.query(Download)
                .order_by(Download.updated_at.desc())
                .limit(100)
                .all()
            )
            return [d.to_dict() for d in downloads]
        finally:
            session.close()

    async def start_magnet(self, magnet: str, source_id: str) -> dict:
        if not magnet.startswith("magnet:"):
            raise ValueError("Invalid magnet link")
        return await self._start_job(source_kind="magnet", source_value=magnet, source_id=source_id)

    async def start_torrent_file(self, file_path: str, source_id: str) -> dict:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise ValueError("Torrent file is missing")
        return await self._start_job(source_kind="torrent", source_value=str(path), source_id=source_id)

    async def _start_job(self, source_kind: str, source_value: str, source_id: str) -> dict:
        if not self.enabled():
            raise ValueError("Downloads are disabled or libtorrent not available")

        source = next((s for s in self.config.library.sources if s.id == source_id), None)
        if not source:
            raise ValueError("Invalid target folder")

        Path(source.path).mkdir(parents=True, exist_ok=True)

        job_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        
        session: Session = self.session_maker()
        try:
            download = Download(
                id=job_id,
                source_kind=source_kind,
                source_value=source_value,
                source_id=source.id,
                source_label=source.label,
                target_dir=source.path,
                status='queued',
                created_at=now,
                updated_at=now
            )
            session.add(download)
            session.commit()
        finally:
            session.close()

        loop = asyncio.get_running_loop()
        task = loop.create_task(self._run_job(job_id=job_id, source_kind=source_kind, source_value=source_value, target_dir=source.path))
        self._tasks[job_id] = task
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict:
        session: Session = self.session_maker()
        try:
            download = session.query(Download).filter(Download.id == job_id).first()
            if not download:
                raise ValueError("Job not found")
            return download.to_dict()
        finally:
            session.close()

    async def stop_job(self, job_id: str) -> dict:
        # Remove torrent handle
        if job_id in self._handles:
            handle = self._handles[job_id]
            if self._session:
                self._session.remove_torrent(handle)
            del self._handles[job_id]
        
        # Cancel task
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        now = datetime.now(timezone.utc).isoformat()
        session: Session = self.session_maker()
        try:
            download = session.query(Download).filter(Download.id == job_id).first()
            if download:
                download.status = 'stopped'
                download.updated_at = now
                session.commit()
            return self.get_job(job_id)
        finally:
            session.close()

    async def restart_job(self, job_id: str) -> dict:
        job = self.get_job(job_id)
        if job["status"] == "downloading":
            raise ValueError("Job is already running")
        
        if job_id in self._tasks:
            task = self._tasks[job_id]
            if not task.done():
                raise ValueError("Job is still active")
        
        now = datetime.now(timezone.utc).isoformat()
        session: Session = self.session_maker()
        try:
            download = session.query(Download).filter(Download.id == job_id).first()
            if download:
                download.status = 'queued'
                download.error = None
                download.progress_percent = 0
                download.updated_at = now
                session.commit()
        finally:
            session.close()
        
        loop = asyncio.get_running_loop()
        task = loop.create_task(self._run_job(
            job_id=job_id, 
            source_kind=job["source_kind"],
            source_value=job["source_value"], 
            target_dir=job["target_dir"]
        ))
        self._tasks[job_id] = task
        return self.get_job(job_id)

    def delete_job(self, job_id: str) -> None:
        # Remove torrent handle
        if job_id in self._handles:
            handle = self._handles[job_id]
            if self._session:
                self._session.remove_torrent(handle)
            del self._handles[job_id]
        
        # Cancel task
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
        
        session: Session = self.session_maker()
        try:
            download = session.query(Download).filter(Download.id == job_id).first()
            if download:
                session.delete(download)
                session.commit()
        finally:
            session.close()
        
        self._tasks.pop(job_id, None)

    async def _run_job(self, job_id: str, source_kind: str, source_value: str, target_dir: str) -> None:
        def update_status(status, **kwargs):
            session: Session = self.session_maker()
            try:
                download = session.query(Download).filter(Download.id == job_id).first()
                if download:
                    download.status = status
                    download.updated_at = datetime.now(timezone.utc).isoformat()
                    for key, value in kwargs.items():
                        setattr(download, key, value)
                    session.commit()
            finally:
                session.close()
        
        try:
            update_status('downloading')
            logger.info(f"Starting download job {job_id}: {source_value[:80]}...")
            
            # Add torrent to session
            params = {
                'save_path': target_dir,
                'storage_mode': lt.storage_mode_t.storage_mode_sparse,
            }
            
            if source_kind == "magnet":
                handle = self._session.add_torrent({'url': source_value, **params})
            else:
                info = lt.torrent_info(source_value)
                handle = self._session.add_torrent({'ti': info, **params})
            
            self._handles[job_id] = handle
            logger.info(f"Torrent added to session for job {job_id}")
            
            # Wait for metadata (for magnet links)
            while not handle.status().has_metadata:
                await asyncio.sleep(0.5)
                status = handle.status()
                if status.state == lt.torrent_status.downloading_metadata:
                    logger.debug(f"Job {job_id}: Downloading metadata...")
            
            torrent_info = handle.torrent_file()
            torrent_name = torrent_info.name()
            logger.info(f"Job {job_id} torrent name: {torrent_name}")
            
            update_status('downloading', display_name=torrent_name)
            
            # Monitor progress
            last_progress = -1
            while not handle.status().is_seeding:
                status = handle.status()
                
                # Check for errors (errc is set even on success, check if it's actually an error)
                if status.errc and status.errc.value() != 0:
                    raise RuntimeError(f"Torrent error: {status.errc.message()}")
                
                # Update progress
                progress = status.progress * 100
                if abs(progress - last_progress) >= 1.0:
                    logger.info(f"Job {job_id} progress: {progress:.1f}% - {status.download_rate / 1024:.1f} KB/s - {status.num_peers} peers")
                    update_status('downloading', progress_percent=progress)
                    last_progress = progress
                
                await asyncio.sleep(1)
            
            # Download complete
            logger.info(f"Job {job_id} completed successfully")
            update_status('done', error=None, progress_percent=100)
            self.scheduler.trigger()
            
        except asyncio.CancelledError:
            logger.info(f"Job {job_id} was cancelled")
            raise
        except Exception as e:
            logger.exception(f"Job {job_id} exception: {e}")
            update_status('failed', error=str(e)[:1000])
        finally:
            # Clean up
            if job_id in self._handles:
                del self._handles[job_id]
            self._tasks.pop(job_id, None)
            logger.info(f"Job {job_id} cleanup complete")


async def save_uploaded_torrent(staging_dir: str, upload_filename: str, content: bytes) -> str:
    target_dir = Path(staging_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload_filename or "upload.torrent").suffix or ".torrent"
    file_name = f"{uuid.uuid4().hex}{suffix}"
    out_path = target_dir / file_name
    out_path.write_bytes(content)
    return str(out_path)
