from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class UserIntent(str, Enum):
    GENERAL_CHAT = "GENERAL_CHAT"
    EXECUTIVE_REASONING = "EXECUTIVE_REASONING"
    DECISION = "DECISION"
    DEVELOPER_TASK = "DEVELOPER_TASK"
    COMPUTER_USE = "COMPUTER_USE"
    COMMUNICATION = "COMMUNICATION"
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"
    MEMORY_QUERY = "MEMORY_QUERY"
    PROACTIVE_TASK = "PROACTIVE_TASK"
    MULTI_DOMAIN = "MULTI_DOMAIN"

class OrchestrationTaskStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class ActionStep(BaseModel):
    id: str
    sequence: int = 1
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    reason: str
    risk_level: str = "MEDIUM"
    autonomy_tier: str = "TIER_2"
    approval_required: bool = True
    approval_id: Optional[str] = None
    status: str = "PENDING"
    result: Optional[str] = None
    verification_status: Optional[str] = None

class ActionPlan(BaseModel):
    plan_id: str
    goal: str
    reason: str
    intent: UserIntent
    steps: List[ActionStep] = Field(default_factory=list)
    risk_level: str = "MEDIUM"
    autonomy_tier: str = "TIER_2"
    expected_outcome: str

class OrchestrationTask(BaseModel):
    id: str
    user_prompt: str
    intent: UserIntent
    status: OrchestrationTaskStatus = OrchestrationTaskStatus.CREATED
    plan: Optional[ActionPlan] = None
    current_step: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    result: Optional[str] = None

class DailyBriefingResponse(BaseModel):
    greeting: str
    priorities: List[str] = Field(default_factory=list)
    important_messages: int = 0
    open_decisions: int = 0
    upcoming_deadlines: int = 0
    pending_approvals: int = 0
    top_recommendation: str
    executive_insight: str

class GlobalSearchResultItem(BaseModel):
    id: str
    source: str  # memory, knowledge, note, conversation, decision
    title: str
    snippet: str
    confidence: float = 1.0
    timestamp: datetime = Field(default_factory=utc_now)

class GlobalSearchResponse(BaseModel):
    query: str
    results: List[GlobalSearchResultItem] = Field(default_factory=list)
