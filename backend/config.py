from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # AssemblyAI
    assemblyai_api_key: str
    assemblyai_webhook_url: str

    # Modem
    modem_port: str = "COM3"
    modem_baudrate: int = 115200
    modem_timeout: int = 5

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # CORS
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()