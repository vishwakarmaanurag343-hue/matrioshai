from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class ProactiveSignalType(str, Enum):
    DEADLINE_UPCOMING = "DEADLINE_UPCOMING"
    UNANSWERED_COMMUNICATION = "UNANSWERED_COMMUNICATION"
    UNRESOLVED_DECISION = "UNRESOLVED_DECISION"
    STALE_TASK = "STALE_TASK"
    PROJECT_BLOCKER = "PROJECT_BLOCKER"

class ProactivePriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    IMPORTANT = "IMPORTANT"
    URGENT = "URGENT"

class ProactiveSuggestion(BaseModel):
    id: str
    signal_type: ProactiveSignalType
    priority: ProactivePriority
    title: str
    reason: str
    evidence: str
    suggested_action: str
    created_at: datetime = Field(default_factory=utc_now)
    is_dismissed: bool = False
    is_snoozed: bool = False
