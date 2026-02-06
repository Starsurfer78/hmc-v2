from typing import List, Dict, Optional
from pydantic import BaseModel
from .config import settings

class UserPolicy(BaseModel):
    allowed_libraries: List[str]
    max_volume: int

# In-memory store for policies (can be expanded to file/db later)
_POLICIES: Dict[str, UserPolicy] = {}

def load_policies():
    """Initializes policies from configuration"""
    # Default policy from env
    libs = [lid.strip() for lid in settings.ALLOWED_LIBRARIES.split(",") if lid.strip()]
    _POLICIES[settings.HMC_USER] = UserPolicy(
        allowed_libraries=libs,
        max_volume=60
    )
    print(f"Loaded policies for: {list(_POLICIES.keys())}")

def get_policy(user_id: Optional[str] = None) -> UserPolicy:
    """Get policy for a specific user"""
    if user_id is None:
        user_id = settings.HMC_USER
    return _POLICIES.get(user_id, UserPolicy(allowed_libraries=[], max_volume=0))
