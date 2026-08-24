from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

class AppSettingsResponse(BaseModel):
    ollama_base_url: str
    ollama_model: str
    database_path: str
    notes_path: str
    memory_path: str
    claude_code_configured: bool = False
    claude_code_last_verified: Optional[datetime] = None
    custom_settings: Dict[str, str] = {}

class AppSettingsUpdate(BaseModel):
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    claude_code_api_key: Optional[str] = None
    custom_settings: Optional[Dict[str, str]] = None

class ClaudeConnectionTestResponse(BaseModel):
    connected: bool
    message: str
    tested_at: datetime
