from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from .core.config import get_config_path, load_config
from .core.db import get_engine, get_session_maker, init_db
from .modules.library.service import LibraryIndex, ScanScheduler, run_file_watcher, run_periodic_scan
from .modules.library import router as library_router
from .modules.settings.service import SettingsStore
from .modules.settings import router as settings_router
from .modules.torrents.service import TorrentManager
from .modules.torrents import router as torrents_router
from .modules.youtube.service import YouTubeDownloadManager
from .modules.youtube import router as youtube_router
from .modules.pastebin import router as pastebin_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

security = HTTPBasic(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .modules.library.transcoding import check_ffmpeg
    
    logger.info("Starting Video Player application...")
    config = load_config()
    logger.info(f"Config loaded from: {get_config_path()}")
    
    # Check FFmpeg availability
    if check_ffmpeg():
        logger.info("FFmpeg detected - transcoding enabled for unsupported formats")
    else:
        logger.warning("FFmpeg not found - MKV/AVI files may not play. Install FFmpeg for transcoding support.")
    
    # Initialize SQLAlchemy
    engine = get_engine(config.state.db_path)
    init_db(engine)
    session_maker = get_session_maker(engine)
    
    index = LibraryIndex(config, session_maker)
    scheduler = ScanScheduler(index=index, debounce_seconds=config.watcher.debounce_seconds)
    torrents_manager = TorrentManager(config=config, session_maker=session_maker, scheduler=scheduler)
    youtube_manager = YouTubeDownloadManager(config=config, session_maker=session_maker, scheduler=scheduler)
    settings_store = SettingsStore(get_config_path())
    
    logger.info(f"Torrent downloads enabled: {torrents_manager.enabled()}")
    logger.info(f"YouTube downloads enabled: {youtube_manager.enabled()}")

    await index.scan()

    periodic_task = asyncio.create_task(run_periodic_scan(index, config.library.scan_interval_seconds))
    watcher_task = None
    if config.watcher.enabled:
        watcher_task = asyncio.create_task(run_file_watcher(config, scheduler))

    app.state.config = config
    app.state.session_maker = session_maker
    app.state.index = index
    app.state.scheduler = scheduler
    app.state.torrents = torrents_manager
    app.state.youtube = youtube_manager
    app.state.settings = settings_store
    app.state.periodic_task = periodic_task
    app.state.watcher_task = watcher_task
    
    logger.info("Application startup complete")

    try:
        yield
    finally:
        logger.info("Shutting down application...")
        periodic_task.cancel()
        if watcher_task:
            watcher_task.cancel()
        engine.dispose()
        logger.info("Application shutdown complete")


app = FastAPI(title="Video Player", lifespan=lifespan)

# Register routers based on configuration
config = load_config()

# Core routers (always enabled)
app.include_router(library_router.router)
app.include_router(settings_router.router)

# Optional module routers
if config.modules.torrents:
    logger.info("Registering torrents module")
    app.include_router(torrents_router.router)

if config.modules.youtube:
    logger.info("Registering YouTube module")
    app.include_router(youtube_router.router)

if config.modules.pastebin:
    logger.info("Registering pastebin module")
    app.include_router(pastebin_router.router)


def require_auth(request: Request, credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    config = request.app.state.config
    if not config.auth.enabled:
        return True
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")
    user_ok = secrets.compare_digest(credentials.username, config.auth.username)
    pass_ok = secrets.compare_digest(credentials.password, config.auth.password)
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return True


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/modules")
def get_enabled_modules(request: Request):
    """Return which modules are enabled."""
    config = request.app.state.config
    return {
        "torrents": config.modules.torrents,
        "youtube": config.modules.youtube,
        "pastebin": config.modules.pastebin,
    }


@app.get("/api/sources")
def list_sources(
    _: bool = Depends(require_auth),
    request: Request = None,
):
    torrents_manager: TorrentManager = request.app.state.torrents
    return torrents_manager.sources()


@app.get("/watch/{video_id}", response_class=HTMLResponse)
def watch_page(video_id: str):
    index_file = Path("/app/frontend/dist/index.html")
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return "Frontend not built. Build frontend and restart."


frontend_dist = Path("/app/frontend/dist")
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}", response_class=HTMLResponse)
def spa_fallback(path: str):
    index_file = Path("/app/frontend/dist/index.html")
    if index_file.exists() and not path.startswith("api/"):
        return index_file.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail="Not found")
