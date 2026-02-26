import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from backend.app.core.dependencies import get_index, require_auth
from backend.app.modules.library.service import LibraryIndex

router = APIRouter(prefix="/api", tags=["videos"], dependencies=[Depends(require_auth)])
logger = logging.getLogger(__name__)


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


@router.get("/browse")
def browse_filesystem(path: str = "", index: LibraryIndex = Depends(get_index)):
    """Browse the filesystem starting from /media."""
    from pathlib import Path
    
    # Base path is always /media
    base_path = Path("/media")
    current_path = base_path / path if path else base_path
    
    if not current_path.exists() or not current_path.is_dir():
        return {"folders": [], "files": []}
    
    folders = []
    files = []
    
    try:
        for item in sorted(current_path.iterdir(), key=lambda x: x.name.lower()):
            if item.name.startswith('.'):
                continue
                
            if item.is_dir():
                rel_path = str(item.relative_to(base_path))
                folders.append({
                    "name": item.name,
                    "path": rel_path,
                    "type": "folder"
                })
            elif item.is_file():
                rel_path = str(item.relative_to(base_path))
                
                # Calculate video ID using the same logic as scan()
                parts = rel_path.split('/')
                source_id = parts[0] if len(parts) > 1 else "media"
                video_id = index.stable_id(source_id, rel_path)
                
                # Try to find video in index
                video = index.get_video(video_id)
                
                if video:
                    files.append({
                        "id": video_id,
                        "rel_path": rel_path,
                        "title": video.get("title", item.name),
                        "size": video.get("size", 0),
                        "mtime": video.get("mtime", 0),
                        "position_seconds": video.get("position_seconds", 0),
                        "stream_url": f"/api/stream/{video_id}",
                        "watch_url": f"/watch/{video_id}",
                        "type": "file"
                    })
                else:
                    # File exists but not in video index
                    files.append({
                        "id": None,
                        "rel_path": rel_path,
                        "title": item.name,
                        "size": item.stat().st_size,
                        "mtime": item.stat().st_mtime,
                        "position_seconds": 0,
                        "stream_url": None,
                        "watch_url": None,
                        "type": "file",
                        "is_video": False
                    })
    except PermissionError:
        pass
    
    return {"folders": folders, "files": files}


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
    """Stream video file directly (no transcoding)."""
    logger.info(f"Stream request for video_id: {video_id}")
    
    if not video_id or not isinstance(video_id, str):
        logger.error(f"Invalid video_id: {video_id}")
        raise HTTPException(status_code=400, detail="Invalid video ID")
    
    try:
        video = index.get_video(video_id)
    except Exception as e:
        logger.exception(f"Error getting video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    if not video:
        logger.error(f"Video not found: {video_id}")
        raise HTTPException(status_code=404, detail="Video not found")

    file_path = Path(video["abs_path"])
    if not file_path.exists() or not file_path.is_file():
        logger.error(f"File missing: {file_path}")
        raise HTTPException(status_code=404, detail="File missing")

    # Check if format is directly playable
    supported_formats = {'.mp4', '.webm', '.ogg', '.ogv'}
    if file_path.suffix.lower() not in supported_formats:
        logger.info(f"Unsupported format: {file_path.suffix}")
        raise HTTPException(
            status_code=415, 
            detail=f"Format {file_path.suffix} not supported. Supported formats: MP4, WebM, OGG. Use Jellyfin for other formats."
        )
    
    # Direct file response for supported formats
    logger.info(f"Direct streaming {file_path.name} (format: {file_path.suffix})")
    return FileResponse(path=file_path, filename=file_path.name)


@router.delete("/videos/{video_id}")
def delete_video(video_id: str, index: LibraryIndex = Depends(get_index)):
    try:
        index.delete_video(video_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/videos/{video_id}/convert-ios")
async def convert_video_for_ios(video_id: str, index: LibraryIndex = Depends(get_index)):
    """Re-encode video to H.264+AAC MP4 for iOS compatibility."""
    import subprocess
    
    video = index.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    source_path = Path(video["abs_path"])
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # Create iOS-compatible output file
    output_path = source_path.parent / f"{source_path.stem}_ios.mp4"
    
    if output_path.exists():
        return {"message": "iOS-compatible version already exists", "output_path": str(output_path)}
    
    try:
        # Re-encode to H.264+AAC with iOS-compatible settings
        cmd = [
            "ffmpeg", "-i", str(source_path),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-profile:v", "high",
            "-level", "4.0",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-y",
            str(output_path)
        ]
        
        # Run in background
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return {"message": "iOS conversion started in background. The file will appear as '{filename}_ios.mp4' when complete.", "output_path": str(output_path)}
    except Exception as e:
        logger.exception(f"iOS conversion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/videos/{video_id}/move")
def move_video(video_id: str, payload: MoveVideoPayload, index: LibraryIndex = Depends(get_index)):
    try:
        result = index.move_video(video_id, payload.target_source_id, payload.target_rel_path)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/folders/move")
def move_folder(payload: dict, index: LibraryIndex = Depends(get_index)):
    """Move a folder and all its contents."""
    import shutil
    
    source_id = payload.get('source_id')
    folder_path = payload.get('folder_path')
    target_source_id = payload.get('target_source_id')
    target_path = payload.get('target_path')
    
    if not all([source_id, folder_path, target_source_id, target_path]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Find sources
    source = next((s for s in index.config.library.sources if s.id == source_id), None)
    target_source = next((s for s in index.config.library.sources if s.id == target_source_id), None)
    
    if not source or not target_source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    src_path = Path(source.path) / folder_path
    dst_path = Path(target_source.path) / target_path
    
    if not src_path.exists():
        raise HTTPException(status_code=404, detail="Source folder not found")
    
    if dst_path.exists():
        raise HTTPException(status_code=400, detail="Target already exists")
    
    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        return {"success": True, "message": f"Moved {src_path.name}"}
    except Exception as e:
        logger.exception(f"Error moving folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/browse/create-folder")
def create_folder(payload: dict, index: LibraryIndex = Depends(get_index)):
    """Create a new folder in /media."""
    path = payload.get('path', '')
    
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    base_path = Path("/media")
    target = base_path / path
    
    if target.exists():
        raise HTTPException(status_code=400, detail="Folder already exists")
    
    try:
        target.mkdir(parents=True, exist_ok=False)
        return {"success": True, "message": f"Created folder {target.name}"}
    except Exception as e:
        logger.exception(f"Error creating folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/browse")
def delete_folder_or_file(path: str, index: LibraryIndex = Depends(get_index)):
    """Delete a folder or file from /media."""
    import shutil
    
    if not path:
        raise HTTPException(status_code=400, detail="Cannot delete /media root")
    
    base_path = Path("/media")
    target = base_path / path
    
    # If doesn't exist, treat as success (idempotent)
    if not target.exists():
        return {"success": True, "message": "Already deleted"}
    
    try:
        if target.is_dir():
            shutil.rmtree(target)
            return {"success": True, "message": f"Deleted folder {target.name}"}
        else:
            target.unlink()
            return {"success": True, "message": f"Deleted file {target.name}"}
    except Exception as e:
        logger.exception(f"Error deleting {target}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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
