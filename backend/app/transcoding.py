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
    Transcode video to HLS on-the-fly using FFmpeg.
    Yields chunks of the transcoded video.
    """
    if not check_ffmpeg():
        raise HTTPException(status_code=500, detail="FFmpeg not installed")
    
    # FFmpeg command for HLS transcoding
    # -re: read input at native frame rate (for streaming)
    # -i: input file
    # -c:v libx264: H.264 video codec
    # -preset ultrafast: fastest encoding (lower quality but faster)
    # -c:a aac: AAC audio codec
    # -f mpegts: MPEG-TS format (streamable)
    # pipe:1: output to stdout
    cmd = [
        'ffmpeg',
        '-i', str(file_path),
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-f', 'mpegts',
        '-movflags', 'frag_keyframe+empty_moov',
        'pipe:1'
    ]
    
    logger.info(f"Starting transcode: {' '.join(cmd)}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Stream the output
        while True:
            chunk = await process.stdout.read(8192)
            if not chunk:
                break
            yield chunk
        
        await process.wait()
        
        if process.returncode != 0:
            stderr = await process.stderr.read()
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise HTTPException(status_code=500, detail="Transcoding failed")
            
    except Exception as e:
        logger.exception(f"Transcoding error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcoding error: {str(e)}")

def create_transcode_response(file_path: Path) -> StreamingResponse:
    """Create a streaming response for transcoded video."""
    return StreamingResponse(
        transcode_to_hls(file_path),
        media_type='video/mp2t',
        headers={
            'Accept-Ranges': 'none',
            'Cache-Control': 'no-cache',
        }
    )
