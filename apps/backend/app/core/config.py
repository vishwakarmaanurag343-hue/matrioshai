import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "MATRIOSHAI Core"
    APP_ENV: str = "development"
    APP_LOG_LEVEL: str = "INFO"
    
    HOST: str = "127.0.0.1"  # Bind ONLY to localhost for security
    PORT: int = 8000
    
    DATABASE_PATH: str = str(DATA_DIR / "database" / "matrioshai.db")
    NOTES_PATH: str = str(DATA_DIR / "notes")
    MEMORY_PATH: str = str(DATA_DIR / "memory")
    LOGS_PATH: str = str(DATA_DIR / "logs")
    
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "deepseek-r1:8b"

    OPENROUTER_API_KEY: str = "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"
    OPENROUTER_MODEL: str = "stealth/ox-alpha"
    
    NVIDIA_API_KEY: str = "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"
    NVIDIA_MODEL: str = "meta/llama-3.1-8b-instruct"

settings = Settings()

# Ensure data directories exist
for path in [
    Path(settings.DATABASE_PATH).parent,
    Path(settings.NOTES_PATH),
    Path(settings.MEMORY_PATH),
    Path(settings.LOGS_PATH),
]:
    path.mkdir(parents=True, exist_ok=True)
