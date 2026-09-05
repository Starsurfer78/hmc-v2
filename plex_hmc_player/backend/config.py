import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PLEX_URL: str
    PLEX_TOKEN: str

    PLEX_ALLOWED_SECTIONS: str = ""
    AUDIO_DEVICE: str = "hw:1,0"
    MAX_VOLUME: int = 60

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
