"""Pydantic schemas for the Notepad capability layer (Slice 1)."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IntentType(str, Enum):
    NOTE = "NOTE"
    TODO = "TODO"
    TASK = "TASK"
    COMMAND = "COMMAND"
    RESEARCH_REQUEST = "RESEARCH_REQUEST"
    DRAFT_REQUEST = "DRAFT_REQUEST"
    AUTOMATION_REQUEST = "AUTOMATION_REQUEST"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"
    MULTI_ACTION_WORKFLOW = "MULTI_ACTION_WORKFLOW"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class IntentStatus(str, Enum):
    DETECTED = "DETECTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"
    ROUTED = "ROUTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DEFERRED = "DEFERRED"


# --- AI request / response ---


class NotepadAIRequest(BaseModel):
    intent_id: str = Field(..., min_length=1, max_length=128)
    note_id: str = Field(..., min_length=1, max_length=128)
    verb: str = Field(..., min_length=1, max_length=32)
    text: str = Field(..., max_length=4000)
    # Slice 1.1: explicit, labeled context sections. All bounded.
    current_note_context: str = Field(default="", max_length=2000)
    intent: str = Field(default="", max_length=4000)
    requested_action: str = Field(default="", max_length=64)
    # Kept for backward compatibility with slice 1 callers; the server merges
    # it into current_note_context if non-empty.
    context_block: str = Field(default="", max_length=1500)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)


class NotepadAIResponse(BaseModel):
    summary: str = Field(..., max_length=2000)
    suggestions: List[str] = Field(default_factory=list, max_length=10)
    confidence: float = Field(..., ge=0.0, le=1.0)
    model: str = Field(..., max_length=128)
    provider: str = Field(..., max_length=64)


class NotepadAIError(BaseModel):
    category: str = Field(..., pattern="^(PROVIDER_UNAVAILABLE|SCHEMA_VIOLATION|TIMEOUT|INTERNAL|UNKNOWN_INTENT|DEFERRED_CAPABILITY)$")
    message: str = Field(..., max_length=500)
    trace_id: Optional[str] = Field(default=None, max_length=128)


# --- Intent DTO (for the /notepad/intent/detect endpoint) ---


class IntentDTO(BaseModel):
    id: str
    note_id: str
    line_number: int
    raw_text: str
    type: IntentType
    entities: Dict[str, str] = Field(default_factory=dict)
    capability_id: Optional[str] = None
    requested_action: str = ""
    risk: RiskLevel = RiskLevel.LOW
    approval_required: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: IntentStatus = IntentStatus.DETECTED
    task_id: Optional[str] = None
    confirmation_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    failure: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class IntentDetectRequest(BaseModel):
    note_id: str = Field(..., min_length=1, max_length=128)
    text: str = Field(..., max_length=20000)


class IntentDetectResponse(BaseModel):
    intents: List[IntentDTO]
    malformed_block: bool = False


# --- Sidecar persistence (Slice 1.1) ---


class IntentPersistenceSaveRequest(BaseModel):
    intents: List[Dict[str, Any]] = Field(default_factory=list)


class IntentPersistenceLoadResponse(BaseModel):
    intents: List[Dict[str, Any]] = Field(default_factory=list)
    malformed: bool = False


class IntentPersistenceResponse(BaseModel):
    saved: int
