import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.core.dependencies import get_torrents, require_auth
from backend.app.modules.torrents.service import TorrentManager, save_uploaded_torrent

router = APIRouter(prefix="/api/torrents", tags=["torrents"], dependencies=[Depends(require_auth)])
logger = logging.getLogger(__name__)


class MagnetPayload(BaseModel):
    magnet: str
    source_id: str


@router.get("/meta")
def torrents_meta(manager: TorrentManager = Depends(get_torrents)):
    return {
        "enabled": manager.enabled(),
        "sources": manager.sources(),
    }


@router.get("")
def list_torrents(manager: TorrentManager = Depends(get_torrents)):
    return manager.list_jobs()


@router.post("/magnet")
async def start_magnet(payload: MagnetPayload, manager: TorrentManager = Depends(get_torrents)):
    logger.info(f"Received magnet link request: {payload.magnet[:50]}... for source: {payload.source_id}")
    try:
        result = await manager.start_magnet(payload.magnet, payload.source_id)
        logger.info(f"Magnet job created: {result.get('id')}")
        return result
    except ValueError as e:
        logger.error(f"Magnet validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        logger.error(f"Magnet runtime error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/upload")
async def upload_torrent(
    source_id: str = Form(...),
    torrent_file: UploadFile = File(...),
    manager: TorrentManager = Depends(get_torrents),
):
    try:
        content = await torrent_file.read()
        saved_path = await save_uploaded_torrent(
            manager.config.downloads.torrent_staging_dir,
            torrent_file.filename or "upload.torrent",
            content,
        )
        return await manager.start_torrent_file(saved_path, source_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{job_id}/stop")
async def stop_torrent(job_id: str, manager: TorrentManager = Depends(get_torrents)):
    try:
        return await manager.stop_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{job_id}/restart")
async def restart_torrent(job_id: str, manager: TorrentManager = Depends(get_torrents)):
    try:
        return await manager.restart_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{job_id}")
async def delete_torrent(job_id: str, manager: TorrentManager = Depends(get_torrents)):
    try:
        manager.delete_job(job_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
