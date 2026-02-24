import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.dependencies import get_youtube, require_auth
from backend.app.modules.youtube.service import YouTubeDownloadManager

router = APIRouter(prefix="/api/youtube", tags=["youtube"], dependencies=[Depends(require_auth)])
logger = logging.getLogger(__name__)


class YouTubePayload(BaseModel):
    url: str
    path: str = ""  # Path relative to /media


@router.get("")
def list_youtube_downloads(manager: YouTubeDownloadManager = Depends(get_youtube)):
    return manager.list_jobs()


@router.post("/download")
async def start_youtube_download(payload: YouTubePayload, manager: YouTubeDownloadManager = Depends(get_youtube)):
    logger.info(f"Received YouTube download request: {payload.url} for path: {payload.path}")
    try:
        result = await manager.start_download(payload.url, payload.path)
        logger.info(f"YouTube job created: {result.get('id')}")
        return result
    except ValueError as e:
        logger.error(f"YouTube validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{job_id}/retry")
async def retry_youtube_download(job_id: str, manager: YouTubeDownloadManager = Depends(get_youtube)):
    try:
        result = await manager.retry_job(job_id)
        logger.info(f"YouTube job retried: {job_id}")
        return result
    except ValueError as e:
        logger.error(f"YouTube retry error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{job_id}")
async def delete_youtube_download(job_id: str, manager: YouTubeDownloadManager = Depends(get_youtube)):
    try:
        await manager.delete_job(job_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
