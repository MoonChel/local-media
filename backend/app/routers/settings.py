from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..config import MediaSource
from ..dependencies import get_settings, require_auth
from ..settings import SettingsStore

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_auth)])


class SourcePayload(BaseModel):
    id: str
    label: str
    path: str
    create_if_missing: bool = False


class PlayerSettingsPayload(BaseModel):
    seek_time: int


async def apply_runtime_config(request: Request) -> None:
    """Helper to reload config and restart background tasks"""
    from contextlib import suppress
    import asyncio
    from ..config import load_config
    from ..library import run_file_watcher, run_periodic_scan
    
    config = load_config()
    app = request.app

    old_periodic = app.state.periodic_task
    old_watcher = app.state.watcher_task
    if old_periodic:
        old_periodic.cancel()
        with suppress(asyncio.CancelledError):
            await old_periodic
    if old_watcher:
        old_watcher.cancel()
        with suppress(asyncio.CancelledError):
            await old_watcher

    app.state.config = config
    app.state.index.config = config
    app.state.torrents.config = config
    app.state.scheduler.debounce_seconds = config.watcher.debounce_seconds

    await app.state.index.scan()
    app.state.periodic_task = asyncio.create_task(run_periodic_scan(app.state.index, config.library.scan_interval_seconds))
    app.state.watcher_task = (
        asyncio.create_task(run_file_watcher(config, app.state.scheduler)) if config.watcher.enabled else None
    )


@router.get("")
def get_settings_api(settings: SettingsStore = Depends(get_settings)):
    return settings.get_settings()


@router.post("/sources")
async def add_or_update_source(payload: SourcePayload, request: Request, settings: SettingsStore = Depends(get_settings)):
    source = MediaSource(
        id=payload.id.strip(),
        label=payload.label.strip() or payload.id.strip(),
        path=payload.path.strip(),
    )
    if not source.id or not source.path:
        raise HTTPException(status_code=400, detail="id and path are required")
    try:
        settings.upsert_source(source, create_if_missing=payload.create_if_missing)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await apply_runtime_config(request)
    return {"ok": True}


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: str,
    request: Request,
    remove_from_disk: bool = True,
    settings: SettingsStore = Depends(get_settings),
):
    try:
        settings.delete_source(source_id, remove_from_disk=remove_from_disk)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await apply_runtime_config(request)
    return {"ok": True}


@router.post("/player")
async def update_player_settings(payload: PlayerSettingsPayload, request: Request, settings: SettingsStore = Depends(get_settings)):
    try:
        settings.update_player_settings(payload.seek_time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await apply_runtime_config(request)
    return {"ok": True}
