from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class AgentTaskStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

class AgentStepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class TaskCreateRequest(BaseModel):
    user_goal: str = Field(..., min_length=3)
    workspace_id: Optional[str] = None
    max_steps: Optional[int] = 20

class StepDefinition(BaseModel):
    sequence: int
    objective: str
    action_type: str = "TOOL_CALL"
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "LOW"
    approval_required: bool = False

class PlanDefinition(BaseModel):
    goal_summary: str
    steps: List[StepDefinition]
    estimated_risk: str = "LOW"

class StepResponse(BaseModel):
    id: str
    task_id: str
    sequence: int
    objective: str
    action_type: str
    tool_name: str
    arguments: Dict[str, Any]
    status: AgentStepStatus
    risk_level: str
    approval_required: bool
    approval_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None

class TaskResponse(BaseModel):
    id: str
    workspace_id: Optional[str] = None
    user_goal: str
    status: AgentTaskStatus
    risk_level: str
    current_step: int
    max_steps: int
    steps_completed: int
    retry_count: int
    max_retries: int
    requires_approval: bool
    result: Optional[str] = None
    failure_reason: Optional[str] = None
    steps: List[StepResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

class StepApprovalRequest(BaseModel):
    approved: bool
    rejection_reason: Optional[str] = None
