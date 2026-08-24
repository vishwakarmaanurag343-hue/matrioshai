from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class MemoryType(str, Enum):
    TEMPORARY = "TEMPORARY"
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    CORE = "CORE"
    DERIVED = "DERIVED"

class MemoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANDIDATE = "CANDIDATE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"

class MemoryRecord(BaseModel):
    id: str
    memory_type: MemoryType
    status: MemoryStatus = MemoryStatus.ACTIVE
    content: str
    source: str = "user"
    source_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    confidence: float = 1.0
    importance: str = "NORMAL"
    sensitivity: str = "PRIVATE"
    provenance: Optional[str] = None
    user_confirmed: bool = False
    superseded_by: Optional[str] = None
    expires_at: Optional[datetime] = None

class MemoryCandidate(BaseModel):
    id: str
    proposed_type: MemoryType
    content: str
    source: str
    confidence: float
    reason: str
    created_at: datetime = Field(default_factory=utc_now)

class MemoryContradiction(BaseModel):
    id: str
    existing_memory: MemoryRecord
    conflicting_content: str
    source: str
    detected_at: datetime = Field(default_factory=utc_now)

class MemoryConfirmationRequest(BaseModel):
    candidate_id: str
    confirmed: bool
    edited_content: Optional[str] = None
    as_core: bool = False
