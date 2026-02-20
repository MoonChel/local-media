from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..dependencies import get_index, require_auth
from ..library import LibraryIndex

router = APIRouter(prefix="/api", tags=["videos"], dependencies=[Depends(require_auth)])


class ProgressPayload(BaseModel):
    position_seconds: float


class MoveVideoPayload(BaseModel):
    target_source_id: str
    target_rel_path: str


@router.get("/videos")
def list_videos(index: LibraryIndex = Depends(get_index)):
    items = index.list_videos()
    out = []
    for row in items:
        out.append(
            {
                "id": row["id"],
                "source_id": row.get("source_id"),
                "source_label": row.get("source_label"),
                "rel_path": row["rel_path"],
                "title": row["title"],
                "size": row["size"],
                "mtime": row["mtime"],
                "position_seconds": row["position_seconds"],
                "stream_url": f"/api/stream/{row['id']}",
                "watch_url": f"/watch/{row['id']}",
            }
        )
    return out


@router.post("/rescan")
async def rescan(index: LibraryIndex = Depends(get_index)):
    await index.scan()
    return {"ok": True}


@router.get("/progress/{video_id}")
def get_progress(video_id: str, index: LibraryIndex = Depends(get_index)):
    return {"video_id": video_id, "position_seconds": index.get_progress(video_id)}


@router.put("/progress/{video_id}")
def put_progress(video_id: str, payload: ProgressPayload, index: LibraryIndex = Depends(get_index)):
    if index.get_video(video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found")
    index.set_progress(video_id, payload.position_seconds)
    return {"ok": True}


@router.get("/stream/{video_id}")
async def stream_video(video_id: str, index: LibraryIndex = Depends(get_index)):
    import logging
    from ..transcoding import needs_transcoding, create_transcode_response
    
    logger = logging.getLogger(__name__)
    logger.info(f"Stream request for video_id: {video_id} (type: {type(video_id)})")
    
    if not video_id or not isinstance(video_id, str):
        logger.error(f"Invalid video_id: {video_id}")
        raise HTTPException(status_code=400, detail="Invalid video ID")
    
    try:
        video = index.get_video(video_id)
    except Exception as e:
        logger.exception(f"Error getting video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    file_path = Path(video["abs_path"])
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File missing")

    # Check if transcoding is needed
    if needs_transcoding(file_path):
        logger.info(f"Transcoding {file_path.name} on-the-fly")
        return create_transcode_response(file_path)
    
    # Direct file response for supported formats
    return FileResponse(path=file_path, filename=file_path.name)


@router.delete("/videos/{video_id}")
def delete_video(video_id: str, index: LibraryIndex = Depends(get_index)):
    try:
        index.delete_video(video_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/videos/{video_id}/move")
def move_video(video_id: str, payload: MoveVideoPayload, index: LibraryIndex = Depends(get_index)):
    try:
        result = index.move_video(video_id, payload.target_source_id, payload.target_rel_path)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/videos/upload")
async def upload_video(
    source_id: str = Form(...),
    rel_path: str = Form(...),
    video_file: UploadFile = File(...),
    index: LibraryIndex = Depends(get_index),
):
    try:
        # Find source
        source = next((s for s in index.config.library.sources if s.id == source_id), None)
        if not source:
            raise ValueError("Source not found")
        
        # Prepare target path
        target_path = Path(source.path) / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        if target_path.exists():
            raise ValueError("File already exists")
        
        # Save file
        content = await video_file.read()
        target_path.write_bytes(content)
        
        # Trigger rescan
        await index.scan()
        
        # Return the new video
        video_id = index.stable_id(source_id, rel_path)
        video = index.get_video(video_id)
        if not video:
            raise ValueError("Failed to add video to library")
        
        return video
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
