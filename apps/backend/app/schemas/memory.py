import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

class MemoryItemCreate(BaseModel):
    source_type: str = Field(default="user_fact")
    source_id: Optional[str] = None
    content: str = Field(..., min_length=1)
    memory_tier: str = Field(..., description="CORE, RECALL, or ARCHIVAL")
    metadata: Optional[Dict[str, Any]] = None

class MemoryItemUpdate(BaseModel):
    content: Optional[str] = None
    memory_tier: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class MemoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_type: str
    source_id: Optional[str] = None
    content: str
    memory_tier: str
    created_at: datetime
    updated_at: datetime
    metadata_json: Optional[str] = None

class MemorySearchQuery(BaseModel):
    query: str = Field(..., min_length=1)
    tier: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=100)

class CoreMemorySetRequest(BaseModel):
    user_preferences: Optional[str] = None
    active_goals: Optional[str] = None
    important_facts: Optional[str] = None
