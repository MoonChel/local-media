"""Shared dependencies for FastAPI routers"""
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .library import LibraryIndex
from .settings import SettingsStore
from .torrents import TorrentManager
from .youtube import YouTubeDownloadManager

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


def get_index(request: Request) -> LibraryIndex:
    return request.app.state.index


def get_torrents(request: Request) -> TorrentManager:
    return request.app.state.torrents


def get_youtube(request: Request) -> YouTubeDownloadManager:
    return request.app.state.youtube


def get_settings(request: Request) -> SettingsStore:
    return request.app.state.settings
