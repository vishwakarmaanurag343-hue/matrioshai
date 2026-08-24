from typing import Dict, Any, Optional
from pydantic import BaseModel

class ComponentStatus(BaseModel):
    name: str
    status: str  # 'Connected', 'Ready', 'Unavailable', 'Missing', 'Active', 'Restricted'
    details: Optional[str] = None

class SystemStatusResponse(BaseModel):
    app_name: str
    app_version: str = "0.2.0"
    backend: ComponentStatus
    database: ComponentStatus
    ollama: ComponentStatus
    model: ComponentStatus
    memory: ComponentStatus
    notes: ComponentStatus
    privacy_gate: ComponentStatus
    secret_store: ComponentStatus
    audit_log: ComponentStatus
    tool_execution: ComponentStatus
