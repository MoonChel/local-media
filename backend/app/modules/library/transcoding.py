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
    Transcode video to MP4 on-the-fly using FFmpeg.
    Yields chunks of the transcoded video.
    """
    if not check_ffmpeg():
        raise HTTPException(status_code=500, detail="FFmpeg not installed")
    
    # FFmpeg command for streaming MP4
    # Try to copy streams if possible (much faster), otherwise transcode
    # -i: input file
    # -c copy: try to copy streams without re-encoding
    # -c:v libx264: fallback to H.264 if copy fails
    # -c:a aac: fallback to AAC if copy fails
    # -movflags frag_keyframe+empty_moov+default_base_moof: fragmented MP4 for streaming
    # -f mp4: MP4 format
    # pipe:1: output to stdout
    cmd = [
        'ffmpeg',
        '-i', str(file_path),
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
        '-f', 'mp4',
        '-loglevel', 'error',
        'pipe:1'
    ]
    
    logger.info(f"Starting stream (copy mode): {file_path.name}")
    
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
        logger.info(f"Stream completed: {chunk_count} chunks")
        
        if process.returncode != 0:
            stderr = await process.stderr.read()
            logger.error(f"FFmpeg error: {stderr.decode()}")
            # If copy failed, try transcoding
            logger.info("Copy failed, trying transcode...")
            async for chunk in transcode_with_encoding(file_path):
                yield chunk
            
    except Exception as e:
        logger.exception(f"Streaming error: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")


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
        '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
        '-f', 'mp4',
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
        media_type='video/mp4',
        headers={
            'Accept-Ranges': 'none',
            'Cache-Control': 'no-cache',
        }
    )
