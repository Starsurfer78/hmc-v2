from typing import Optional
from pydantic import BaseModel
from .settings_store import get_settings_store


class UserPolicy(BaseModel):
    allowed_libraries: list[str]
    max_volume: int


def get_policy(user_id: Optional[str] = None) -> UserPolicy:
    """
    Liefert die aktuell gültige Policy direkt aus dem Settings-Store.
    HMC ist Single-User (ein Kind pro Gerät) — `user_id` wird nur der
    API-Kompatibilität wegen noch angenommen, aber nicht ausgewertet.
    """
    data = get_settings_store().get_all()
    return UserPolicy(
        allowed_libraries=data.get("allowed_libraries", []),
        max_volume=data.get("max_volume", 0),
    )
