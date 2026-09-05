"""
HMC Admin API
=============
Endpoints für das Admin-Panel (PIN-geschützt im Frontend).

- GET  /admin/settings                  Aktuelle Einstellungen lesen
- POST /admin/settings                  Einstellungen speichern
- POST /admin/verify-pin                PIN prüfen (gibt Token zurück)
- GET  /admin/jellyfin/libraries        Alle Jellyfin-Bibliotheken mit Aktivierungsstatus
- GET  /admin/ota/status                Git-Status des Repos
- POST /admin/ota/update                OTA-Update starten (SSE-Stream)
"""

import asyncio
import json
import logging
import secrets
import subprocess
from pathlib import Path
from typing import Optional

import aiohttp
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .settings_store import get_settings_store, hash_pin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# ------------------------------------------------------------
# Pfade
# ------------------------------------------------------------
_BASE_DIR = Path(__file__).parent.parent
_VENV_PIP = _BASE_DIR / "venv" / "bin" / "pip"

_active_token: Optional[str] = None

# Laufende Instanzen, damit Admin-Änderungen sofort wirksam werden.
# Wird von main.py beim Start per bind_runtime() gesetzt (vermeidet
# einen Zirkularimport zwischen admin.py und main.py).
_jellyfin_client = None
_player = None


def bind_runtime(jellyfin_client, player):
    global _jellyfin_client, _player
    _jellyfin_client = jellyfin_client
    _player = player


# ------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------

def _check_token(token: str):
    if not _active_token or not secrets.compare_digest(token, _active_token):
        raise HTTPException(401, "Ungültiger oder abgelaufener Token")


# ------------------------------------------------------------
# Pydantic Models
# ------------------------------------------------------------

class PinVerifyRequest(BaseModel):
    pin: str


class SettingsUpdate(BaseModel):
    token: str
    device_name:       Optional[str]  = None
    max_volume:        Optional[int]  = None
    allowed_libraries: Optional[list] = None
    jellyfin_url:      Optional[str]  = None
    jellyfin_api_key:  Optional[str]  = None
    audio_device:      Optional[str]  = None
    ota_branch:        Optional[str]  = None
    new_pin:           Optional[str]  = None


class OtaRequest(BaseModel):
    token: str


# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------

@router.post("/verify-pin")
async def verify_pin(body: PinVerifyRequest):
    global _active_token
    data     = get_settings_store().get_all()
    pin_hash = hash_pin(body.pin.strip())
    if not secrets.compare_digest(pin_hash, data.get("admin_pin_hash", "")):
        raise HTTPException(403, "Falscher PIN")
    _active_token = secrets.token_hex(32)
    return {"token": _active_token}


@router.get("/settings")
async def get_settings(token: str):
    _check_token(token)
    return get_settings_store().get_public()


@router.post("/settings")
async def save_settings(body: SettingsUpdate):
    _check_token(body.token)

    payload = body.model_dump(exclude={"token"}, exclude_none=True)
    try:
        get_settings_store().update(payload)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Laufende Instanzen sofort auf die neuen Werte umstellen.
    if body.jellyfin_url is not None or body.jellyfin_api_key is not None:
        data = get_settings_store().get_all()
        if _jellyfin_client is not None:
            await _jellyfin_client.reconfigure(data["jellyfin_url"], data["jellyfin_api_key"])
    if body.audio_device is not None and _player is not None:
        await _player.reconfigure_audio_device(body.audio_device)

    return {"status": "ok"}


@router.get("/jellyfin/libraries")
async def get_jellyfin_libraries(token: str):
    """
    Fragt alle Jellyfin-Bibliotheken live ab und gibt zurück welche
    aktuell erlaubt (enabled) sind. Wird im Admin-Panel für die
    Bibliotheks-Auswahl mit Checkboxen verwendet.

    Antwort:
      [{ "id": "...", "name": "Hörbücher", "type": "books", "enabled": true }, ...]
    """
    _check_token(token)

    data         = get_settings_store().get_all()
    jellyfin_url = data.get("jellyfin_url", "").rstrip("/")
    api_key      = data.get("jellyfin_api_key", "")
    allowed      = set(data.get("allowed_libraries", []))

    if not jellyfin_url:
        raise HTTPException(503, "Jellyfin URL nicht konfiguriert")
    if not api_key:
        raise HTTPException(503, "Jellyfin API-Key nicht konfiguriert")

    headers = {"X-Emby-Token": api_key, "Accept": "application/json"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                f"{jellyfin_url}/Library/MediaFolders", timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                if resp.status != 200:
                    raise HTTPException(502, f"Jellyfin antwortet mit {resp.status}")
                data = await resp.json()
    except aiohttp.ClientError as e:
        raise HTTPException(502, f"Jellyfin nicht erreichbar: {e}")

    libraries = [
        {
            "id":      item["Id"],
            "name":    item["Name"],
            "type":    item.get("CollectionType", "unknown"),
            "enabled": item["Id"] in allowed,
        }
        for item in data.get("Items", [])
    ]

    return libraries


@router.get("/ota/status")
async def ota_status(token: str):
    _check_token(token)
    try:
        def _run(cmd):
            return subprocess.check_output(
                cmd, cwd=_BASE_DIR, stderr=subprocess.DEVNULL, text=True
            ).strip()

        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        local  = _run(["git", "rev-parse", "--short", "HEAD"])
        msg    = _run(["git", "log", "-1", "--pretty=%s"])
        date   = _run(["git", "log", "-1", "--pretty=%ci"])

        subprocess.run(
            ["git", "fetch", "--quiet"],
            cwd=_BASE_DIR, timeout=10,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        remote = _run(["git", "rev-parse", "--short", f"origin/{branch}"])
        behind = int(_run(["git", "rev-list", "--count", f"HEAD..origin/{branch}"]))

        return {
            "branch":            branch,
            "local_commit":      local,
            "remote_commit":     remote,
            "commit_message":    msg,
            "commit_date":       date,
            "updates_available": behind > 0,
            "commits_behind":    behind,
        }
    except Exception as e:
        return {"error": str(e), "updates_available": False}


@router.post("/ota/update")
async def ota_update(body: OtaRequest):
    _check_token(body.token)

    async def _stream():
        def _msg(text: str, level: str = "info") -> str:
            return f"data: {json.dumps({'text': text, 'level': level})}\n\n"

        yield _msg("🔄 Starte OTA-Update...")
        yield _msg("📥 Lade Updates von Git...")

        proc = await asyncio.create_subprocess_exec(
            "git", "pull", "--rebase",
            cwd=_BASE_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in proc.stdout:
            yield _msg(line.decode().rstrip())
        await proc.wait()
        if proc.returncode != 0:
            yield _msg("❌ git pull fehlgeschlagen – Update abgebrochen", "error")
            yield _msg("done")
            return

        yield _msg("📦 Aktualisiere Python-Pakete...")
        proc = await asyncio.create_subprocess_exec(
            str(_VENV_PIP), "install", "-q", "-r",
            str(_BASE_DIR / "backend" / "requirements.txt"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in proc.stdout:
            yield _msg(line.decode().rstrip())
        await proc.wait()
        if proc.returncode != 0:
            yield _msg("⚠️  pip install mit Warnungen beendet", "warn")

        yield _msg("🔁 Starte HMC-Service neu...")
        proc = await asyncio.create_subprocess_exec(
            "sudo", "systemctl", "restart", "hmc",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await proc.wait()
        if proc.returncode == 0:
            yield _msg("✅ Update erfolgreich! System startet neu...", "success")
        else:
            yield _msg("⚠️  systemctl restart schlug fehl – bitte manuell neustarten", "warn")

        yield _msg("done")

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
