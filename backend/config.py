import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Jellyfin ---
    JELLYFIN_URL: str
    JELLYFIN_API_KEY: str

    # --- HMC ---
    HMC_USER: str = "hmc_user"
    AUDIO_DEVICE: str = "hw:1,0"
    ALLOWED_LIBRARIES: str = ""

    # --- MQTT ---
    # Broker-Adresse des Mosquitto im LAN (IP oder Hostname)
    MQTT_BROKER: str = "192.168.178.XX"   # <-- anpassen!
    MQTT_PORT: int = 1883
    MQTT_USER: str = ""
    MQTT_PASSWORD: str = ""

    # Eindeutige ID dieser HMC-Instanz.
    # Bei mehreren Playern im Netz muss jede Instanz einen anderen Wert haben.
    # Beispiele: "hmc_wohnzimmer", "hmc_kinderzimmer_amelie", "hmc_kueche"
    # Erlaubte Zeichen: a-z, 0-9, Unterstrich (kein Leerzeichen, kein Bindestrich)
    MQTT_DEVICE_ID: str = "hmc_player"

    # Anzeigename in Home Assistant (darf Leerzeichen und Umlaute enthalten)
    MQTT_DEVICE_NAME: str = "HMC Player"

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
