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

    GROQ_API_KEY: str = "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"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    OPENROUTER_API_KEY: str = "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"
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"
    
    NVIDIA_API_KEY: str = "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"
    NVIDIA_MODEL: str = "meta/llama3-70b-instruct"

settings = Settings()

# Ensure data directories exist
for path in [
    Path(settings.DATABASE_PATH).parent,
    Path(settings.NOTES_PATH),
    Path(settings.MEMORY_PATH),
    Path(settings.LOGS_PATH),
]:
    path.mkdir(parents=True, exist_ok=True)
