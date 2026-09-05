"""
HMC Runtime Settings Store
==========================
`backend/.env` dient nur noch als Bootstrap-Quelle für den allerersten Start.
Danach ist ausschließlich diese Datei (backend/admin_settings.json), gepflegt
über den Admin-Bereich, die laufende Konfigurationsquelle für Jellyfin-Zugang,
freigegebene Bibliotheken, Max-Lautstärke, Audio-Device, Gerätename und den
Admin-PIN.
"""

import hashlib
import json
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional


def hash_pin(pin: str) -> str:
    # Salt unverändert gegenüber der bisherigen Implementierung in admin.py,
    # damit bereits gesetzte PINs auf bestehenden Installationen gültig bleiben.
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), b"hmc-salt", 100_000).hex()


class RuntimeSettingsStore:
    def __init__(self, file_path: Path, env_settings: Any):
        self.file_path = file_path
        self.env_settings = env_settings
        self._lock = RLock()
        self._data = self._load_or_initialize()

    def _defaults(self) -> Dict[str, Any]:
        return {
            "admin_pin_hash": hash_pin("1234"),
            "device_name": self.env_settings.MQTT_DEVICE_NAME or "HMC Player",
            "jellyfin_url": self.env_settings.JELLYFIN_URL.rstrip("/"),
            "jellyfin_api_key": self.env_settings.JELLYFIN_API_KEY,
            "allowed_libraries": self._parse_list(self.env_settings.ALLOWED_LIBRARIES),
            "audio_device": self.env_settings.AUDIO_DEVICE,
            "max_volume": 60,
            "ota_branch": "main",
        }

    def _load_or_initialize(self) -> Dict[str, Any]:
        if self.file_path.exists():
            try:
                return json.loads(self.file_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        data = self._defaults()
        self._save(data)
        return data

    def _save(self, data: Dict[str, Any]) -> None:
        self.file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _parse_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        return []

    def get_all(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def get_public(self) -> Dict[str, Any]:
        """Wie get_all(), aber ohne Geheimnisse (für die Admin-API)."""
        with self._lock:
            data = dict(self._data)
        data.pop("admin_pin_hash", None)
        api_key = data.pop("jellyfin_api_key", "")
        data["jellyfin_api_key_present"] = bool(api_key)
        return data

    def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = dict(self._data)

            if payload.get("device_name") is not None:
                data["device_name"] = str(payload["device_name"]).strip() or "HMC Player"
            if payload.get("jellyfin_url") is not None:
                data["jellyfin_url"] = str(payload["jellyfin_url"]).strip().rstrip("/")
            if payload.get("jellyfin_api_key"):
                data["jellyfin_api_key"] = str(payload["jellyfin_api_key"]).strip()
            if payload.get("allowed_libraries") is not None:
                data["allowed_libraries"] = self._parse_list(payload["allowed_libraries"])
            if payload.get("audio_device") is not None:
                data["audio_device"] = str(payload["audio_device"]).strip() or "hw:1,0"
            if payload.get("max_volume") is not None:
                data["max_volume"] = max(0, min(100, int(payload["max_volume"])))
            if payload.get("ota_branch") is not None:
                data["ota_branch"] = str(payload["ota_branch"]).strip() or "main"
            if payload.get("new_pin"):
                new_pin = str(payload["new_pin"]).strip()
                if len(new_pin) != 4 or not new_pin.isdigit():
                    raise ValueError("PIN muss genau 4 Ziffern haben")
                data["admin_pin_hash"] = hash_pin(new_pin)

            self._data = data
            self._save(self._data)
            return dict(self._data)


_store: Optional[RuntimeSettingsStore] = None


def get_settings_store() -> RuntimeSettingsStore:
    global _store
    if _store is None:
        from .config import settings as env_settings
        file_path = Path(__file__).parent / "admin_settings.json"
        _store = RuntimeSettingsStore(file_path, env_settings)
    return _store
