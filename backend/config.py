import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    JELLYFIN_URL: str
    JELLYFIN_API_KEY: str
    HMC_USER: str = "hmc_user"
    AUDIO_DEVICE: str = "hw:1,0"
    ALLOWED_LIBRARIES: str = ""
    
    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_file_encoding = "utf-8"

settings = Settings()
