"""Shared dependencies for FastAPI routers"""
import secrets
from typing import Optional, TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

if TYPE_CHECKING:
    from backend.app.modules.library.service import LibraryIndex
    from backend.app.modules.settings.service import SettingsStore
    from backend.app.modules.torrents.service import TorrentManager
    from backend.app.modules.youtube.service import YouTubeDownloadManager

security = HTTPBasic(auto_error=False)


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


def get_index(request: Request):
    return request.app.state.index


def get_torrents(request: Request):
    return request.app.state.torrents


def get_youtube(request: Request):
    return request.app.state.youtube


def get_settings(request: Request):
    return request.app.state.settings
