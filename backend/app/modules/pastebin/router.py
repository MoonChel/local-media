import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/pastebin", tags=["pastebin"])


class PastebinPayload(BaseModel):
    content: str
    ttl_minutes: int = 60


# In-memory pastebin storage
pastebin_data = {
    "content": "",
    "expires_at": None,
    "ttl_minutes": 60,
}
pastebin_lock = asyncio.Lock()


@router.get("")
async def get_pastebin():
    async with pastebin_lock:
        now = datetime.now(timezone.utc)
        # Check if expired
        if pastebin_data["expires_at"] and now.timestamp() > pastebin_data["expires_at"]:
            pastebin_data["content"] = ""
            pastebin_data["expires_at"] = None
        
        return {
            "content": pastebin_data["content"],
            "expires_at": pastebin_data["expires_at"],
            "ttl_minutes": pastebin_data["ttl_minutes"],
        }


@router.post("")
async def set_pastebin(payload: PastebinPayload):
    async with pastebin_lock:
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(minutes=payload.ttl_minutes)).timestamp()
        
        pastebin_data["content"] = payload.content
        pastebin_data["expires_at"] = expires_at
        pastebin_data["ttl_minutes"] = payload.ttl_minutes
        
        return {
            "content": pastebin_data["content"],
            "expires_at": pastebin_data["expires_at"],
            "ttl_minutes": pastebin_data["ttl_minutes"],
        }


@router.delete("")
async def clear_pastebin():
    async with pastebin_lock:
        pastebin_data["content"] = ""
        pastebin_data["expires_at"] = None
        return {"ok": True}
