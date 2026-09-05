import hashlib
import json
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List


def hash_pin(pin: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), b"plex-hmc-salt", 100_000).hex()


class RuntimeSettingsStore:
    def __init__(self, file_path: Path, env_settings: Any):
        self.file_path = file_path
        self.env_settings = env_settings
        self._lock = RLock()
        self._data = self._load_or_initialize()

    def _defaults(self) -> Dict[str, Any]:
        return {
            "admin_pin_hash": hash_pin("1234"),
            "device_name": "Plex HMC Player",
            "plex_url": self.env_settings.PLEX_URL.rstrip("/"),
            "plex_token": self.env_settings.PLEX_TOKEN,
            "allowed_sections": self._parse_list(self.env_settings.PLEX_ALLOWED_SECTIONS),
            "audio_device": self.env_settings.AUDIO_DEVICE,
            "max_volume": max(0, min(100, int(self.env_settings.MAX_VOLUME))),
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
        with self._lock:
            data = dict(self._data)
        data.pop("admin_pin_hash", None)
        token = data.pop("plex_token", "")
        data["plex_token_present"] = bool(token)
        return data

    def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            data = dict(self._data)

            if "device_name" in payload and payload["device_name"] is not None:
                data["device_name"] = str(payload["device_name"]).strip() or "Plex HMC Player"
            if "plex_url" in payload and payload["plex_url"] is not None:
                data["plex_url"] = str(payload["plex_url"]).strip().rstrip("/")
            if "plex_token" in payload and payload["plex_token"] is not None:
                token = str(payload["plex_token"]).strip()
                if token:
                    data["plex_token"] = token
            if "allowed_sections" in payload and payload["allowed_sections"] is not None:
                data["allowed_sections"] = self._parse_list(payload["allowed_sections"])
            if "audio_device" in payload and payload["audio_device"] is not None:
                data["audio_device"] = str(payload["audio_device"]).strip() or "hw:1,0"
            if "max_volume" in payload and payload["max_volume"] is not None:
                data["max_volume"] = max(0, min(100, int(payload["max_volume"])))
            if payload.get("new_pin"):
                new_pin = str(payload["new_pin"]).strip()
                if len(new_pin) < 4:
                    raise ValueError("PIN muss mindestens 4 Zeichen haben")
                data["admin_pin_hash"] = hash_pin(new_pin)

            self._data = data
            self._save(self._data)
            return dict(self._data)
