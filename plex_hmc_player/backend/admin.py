import secrets
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .config import settings
from .plex_client import PlexClient
from .runtime_settings import RuntimeSettingsStore, hash_pin


router = APIRouter(prefix="/admin", tags=["admin"])
runtime_settings = RuntimeSettingsStore(Path(__file__).parent / "admin_settings.json", settings)
_active_token: Optional[str] = None


class PinVerifyRequest(BaseModel):
    pin: str


class PlexSettingsUpdate(BaseModel):
    token: str
    device_name: Optional[str] = None
    plex_url: Optional[str] = None
    plex_token: Optional[str] = None
    allowed_sections: Optional[List[str]] = None
    audio_device: Optional[str] = None
    max_volume: Optional[int] = None
    new_pin: Optional[str] = None


def get_runtime_settings() -> RuntimeSettingsStore:
    return runtime_settings


def _check_token(token: str) -> None:
    if not _active_token or not secrets.compare_digest(token, _active_token):
        raise HTTPException(401, "Ungueltiger oder abgelaufener Token")


@router.post("/verify-pin")
async def verify_pin(body: PinVerifyRequest):
    global _active_token
    data = runtime_settings.get_all()
    if not secrets.compare_digest(hash_pin(body.pin.strip()), data.get("admin_pin_hash", "")):
        raise HTTPException(403, "Falscher PIN")
    _active_token = secrets.token_hex(32)
    return {"token": _active_token}


@router.get("/settings")
async def get_settings(token: str):
    _check_token(token)
    return runtime_settings.get_public()


@router.post("/settings")
async def save_settings(body: PlexSettingsUpdate):
    _check_token(body.token)

    if body.plex_url is not None:
        url = body.plex_url.strip()
        if url and not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(400, "PLEX_URL muss mit http:// oder https:// beginnen")

    try:
        runtime_settings.update(body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    return {"status": "ok"}


@router.get("/plex/sections")
async def get_plex_sections(token: str):
    _check_token(token)
    data = runtime_settings.get_all()
    plex_url = data.get("plex_url", "").rstrip("/")
    plex_token = data.get("plex_token", "")
    allowed = set(data.get("allowed_sections", []))

    if not plex_url:
        raise HTTPException(503, "Plex URL nicht konfiguriert")
    if not plex_token:
        raise HTTPException(503, "Plex Token nicht konfiguriert")

    client = PlexClient(plex_url, plex_token)
    try:
        await client.start()
        sections = await client.get_sections()
    except Exception as exc:
        raise HTTPException(502, f"Plex nicht erreichbar: {exc}")
    finally:
        await client.close()

    out = []
    for section in sections:
        out.append(
            {
                "id": section.get("id", ""),
                "name": section.get("name", ""),
                "type": section.get("type", "unknown"),
                "enabled": section.get("id", "") in allowed,
            }
        )
    return out
