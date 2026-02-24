from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from slugify import slugify
from sqlalchemy.orm import Session
from backend.app.core.config import AppConfig
from backend.app.modules.library.service import ScanScheduler
from backend.app.core.models import YouTubeDownload

logger = logging.getLogger(__name__)


class YouTubeDownloadManager:
    def __init__(self, config: AppConfig, session_maker, scheduler: ScanScheduler):
        self.config = config
        self.session_maker = session_maker
        self.scheduler = scheduler
        self._tasks: dict[str, asyncio.Task] = {}

    def enabled(self) -> bool:
        return yt_dlp is not None

    def list_jobs(self) -> list[dict]:
        session: Session = self.session_maker()
        try:
            downloads = (
                session.query(YouTubeDownload)
                .order_by(YouTubeDownload.updated_at.desc())
                .limit(100)
                .all()
            )
            return [d.to_dict() for d in downloads]
        finally:
            session.close()

    async def start_download(self, url: str, path: str = "") -> dict:
        if not self.enabled():
            raise ValueError("YouTube downloads are disabled or yt-dlp not available")

        # Build target directory from path
        base_path = Path("/media")
        target_dir = base_path / path if path else base_path
        target_dir.mkdir(parents=True, exist_ok=True)

        job_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        
        # Get folder label from path
        folder_label = path.split('/')[-1] if path else 'media'
        
        session: Session = self.session_maker()
        try:
            download = YouTubeDownload(
                id=job_id,
                url=url,
                source_id=path or "media",  # Use path as identifier
                source_label=folder_label,
                target_dir=str(target_dir),
                status='queued',
                created_at=now,
                updated_at=now
            )
            session.add(download)
            session.commit()
        finally:
            session.close()

        loop = asyncio.get_running_loop()
        task = loop.create_task(self._run_job(job_id=job_id, url=url, target_dir=str(target_dir)))
        self._tasks[job_id] = task
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict:
        session: Session = self.session_maker()
        try:
            download = session.query(YouTubeDownload).filter(YouTubeDownload.id == job_id).first()
            if not download:
                raise ValueError("Job not found")
            return download.to_dict()
        finally:
            session.close()

    async def delete_job(self, job_id: str) -> None:
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
        
        session: Session = self.session_maker()
        try:
            download = session.query(YouTubeDownload).filter(YouTubeDownload.id == job_id).first()
            if download:
                session.delete(download)
                session.commit()
        finally:
            session.close()
        
        self._tasks.pop(job_id, None)
    async def retry_job(self, job_id: str) -> dict:
        """Retry a failed download job"""
        session: Session = self.session_maker()
        try:
            download = session.query(YouTubeDownload).filter(YouTubeDownload.id == job_id).first()
            if not download:
                raise ValueError(f"Job {job_id} not found")

            if download.status != 'failed':
                raise ValueError(f"Job {job_id} is not in failed state (current: {download.status})")

            # Reset the job state
            download.status = 'queued'
            download.error = None
            download.progress_percent = 0
            download.video_id = None
            download.updated_at = datetime.now(timezone.utc).isoformat()
            session.commit()

            # Restart the download task
            url = download.url
            source_id = download.source_id

            # Find target directory
            source = next((s for s in self.config.library.sources if s.id == source_id), None)
            if not source:
                raise ValueError(f"Source {source_id} not found")

            target_dir = source.path

            # Start the download task
            task = asyncio.create_task(self._run_job(job_id, url, target_dir))
            self._tasks[job_id] = task

            logger.info(f"Retrying job {job_id}")
            return self.get_job(job_id)
        finally:
            session.close()


    async def _run_job(self, job_id: str, url: str, target_dir: str) -> None:
        def update_download(**kwargs):
            session: Session = self.session_maker()
            try:
                download = session.query(YouTubeDownload).filter(YouTubeDownload.id == job_id).first()
                if download:
                    download.updated_at = datetime.now(timezone.utc).isoformat()
                    for key, value in kwargs.items():
                        setattr(download, key, value)
                    session.commit()
            finally:
                session.close()
        
        try:
            update_download(status='downloading')
            logger.info(f"Starting YouTube download job {job_id}: {url}")

            # Progress hook
            def progress_hook(d):
                if d['status'] == 'downloading':
                    # Extract progress
                    if 'downloaded_bytes' in d and 'total_bytes' in d:
                        progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    elif '_percent_str' in d:
                        progress_str = d['_percent_str'].strip().replace('%', '')
                        try:
                            progress = float(progress_str)
                        except:
                            progress = 0
                    else:
                        progress = 0
                    
                    update_download(progress_percent=progress)
                    logger.info(f"Job {job_id} progress: {progress:.1f}%")
                
                elif d['status'] == 'finished':
                    logger.info(f"Job {job_id} download finished, processing...")

            # yt-dlp options
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': f'{target_dir}/%(title)s.%(ext)s',
                'progress_hooks': [progress_hook],
                'quiet': False,
                'no_warnings': False,
            }

            # Download video
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._download_with_ytdlp, ydl_opts, url, job_id)

            # Download complete - find the video in library
            logger.info(f"Job {job_id} completed successfully, finding video in library...")
            
            # Trigger library scan and wait
            self.scheduler.trigger()
            await asyncio.sleep(3)
            
            # Try to find the video by matching the filename
            job = self.get_job(job_id)
            video_title = job.get('display_name')
            video_id = None
            
            logger.info(f"Job {job_id} job data: {job}")
            
            if video_title:
                # Find video by title in the target source
                from backend.app.modules.library.service import LibraryIndex
                index = LibraryIndex(self.config, self.session_maker)
                videos = index.list_videos()
                
                logger.info(f"Job {job_id} searching for video with title: '{video_title}'")
                logger.info(f"Job {job_id} target source: '{job['source_id']}'")
                logger.info(f"Job {job_id} total videos in library: {len(videos)}")
                
                # Use slugify for robust title matching
                slugified_search = slugify(video_title)
                logger.info(f"Job {job_id} slugified search title: '{slugified_search}'")
                
                # Try exact match first
                for video in videos:
                    if video['source_id'] == job['source_id']:
                        slugified_video = slugify(video['title'])
                        logger.info(f"Job {job_id} comparing: '{slugified_video}' vs '{slugified_search}'")
                        if slugified_video == slugified_search:
                            video_id = video['id']
                            logger.info(f"Job {job_id} found video_id (exact match): {video_id}")
                            break
                
                # Try partial match if exact didn't work
                if not video_id:
                    for video in videos:
                        if video['source_id'] == job['source_id']:
                            slugified_video = slugify(video['title'])
                            if slugified_search in slugified_video or slugified_video in slugified_search:
                                video_id = video['id']
                                logger.info(f"Job {job_id} found video_id (partial match): {video_id} - {video['title']}")
                                break
                
                if not video_id:
                    logger.warning(f"Job {job_id} could not find video in library. Title: {video_title}")
                    # Log some videos from the target source for debugging
                    source_videos = [v for v in videos if v['source_id'] == job['source_id']]
                    logger.info(f"Job {job_id} found {len(source_videos)} videos in target source")
                    if source_videos:
                        recent_videos = sorted(source_videos, key=lambda v: v.get('mtime', 0), reverse=True)[:3]
                        logger.info(f"Job {job_id} most recent titles: {[v['title'] for v in recent_videos]}")
            
            update_download(status='done', error=None, progress_percent=100, video_id=video_id)

        except asyncio.CancelledError:
            logger.info(f"Job {job_id} was cancelled")
            raise
        except Exception as e:
            logger.exception(f"Job {job_id} exception: {e}")
            update_download(status='failed', error=str(e)[:1000])
        finally:
            self._tasks.pop(job_id, None)
            logger.info(f"Job {job_id} cleanup complete")

    def _download_with_ytdlp(self, ydl_opts: dict, url: str, job_id: str):
        """Synchronous download function to run in executor"""
        def update_title(title):
            session: Session = self.session_maker()
            try:
                download = session.query(YouTubeDownload).filter(YouTubeDownload.id == job_id).first()
                if download:
                    download.display_name = title
                    download.updated_at = datetime.now(timezone.utc).isoformat()
                    session.commit()
            finally:
                session.close()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to get title
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            
            update_title(title)
            logger.info(f"Job {job_id} video title: {title}")
            
            # Download
            ydl.download([url])
