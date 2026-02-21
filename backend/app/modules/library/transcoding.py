import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# Formats that need transcoding
NEEDS_TRANSCODING = {'.mkv', '.avi', '.wmv', '.flv', '.mov', '.m4v'}

def check_ffmpeg() -> bool:
    """Check if FFmpeg is available."""
    return shutil.which('ffmpeg') is not None

def needs_transcoding(file_path: Path) -> bool:
    """Check if file needs transcoding based on extension."""
    return file_path.suffix.lower() in NEEDS_TRANSCODING

async def transcode_to_hls(file_path: Path):
    """
    Remux video to MP4 on-the-fly using FFmpeg.
    Yields chunks of the remuxed video.
    """
    if not check_ffmpeg():
        raise HTTPException(status_code=500, detail="FFmpeg not installed")
    
    # Simple remux command - just change container, don't re-encode
    # -i: input file
    # -c copy: copy all streams without re-encoding
    # -f matroska: output as Matroska/WebM (better streaming support)
    # pipe:1: output to stdout
    cmd = [
        'ffmpeg',
        '-i', str(file_path),
        '-c', 'copy',
        '-f', 'matroska',
        '-loglevel', 'error',
        'pipe:1'
    ]
    
    logger.info(f"Starting remux: {file_path.name}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Stream the output
        chunk_count = 0
        while True:
            chunk = await process.stdout.read(65536)
            if not chunk:
                break
            chunk_count += 1
            yield chunk
        
        await process.wait()
        logger.info(f"Remux completed: {chunk_count} chunks")
        
        if process.returncode != 0:
            stderr = await process.stderr.read()
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise HTTPException(status_code=500, detail="Remux failed")
            
    except Exception as e:
        logger.exception(f"Remux error: {e}")
        raise HTTPException(status_code=500, detail=f"Remux error: {str(e)}")


async def transcode_with_encoding(file_path: Path):
    """Transcode with re-encoding (slower but more compatible)."""
    cmd = [
        'ffmpeg',
        '-i', str(file_path),
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-f', 'matroska',
        '-loglevel', 'error',
        'pipe:1'
    ]
    
    logger.info(f"Starting transcode with encoding: {file_path.name}")
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    while True:
        chunk = await process.stdout.read(65536)
        if not chunk:
            break
        yield chunk
    
    await process.wait()

def create_transcode_response(file_path: Path) -> StreamingResponse:
    """Create a streaming response for transcoded video."""
    return StreamingResponse(
        transcode_to_hls(file_path),
        media_type='video/x-matroska',
        headers={
            'Accept-Ranges': 'none',
            'Cache-Control': 'no-cache',
        }
    )
