from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class AgentEventType(str, Enum):
    TASK_CREATED = "TASK_CREATED"
    AGENT_STARTED = "AGENT_STARTED"
    PLAN_CREATED = "PLAN_CREATED"
    MODEL_REQUEST = "MODEL_REQUEST"
    MODEL_RESPONSE = "MODEL_RESPONSE"
    TOOL_REQUEST = "TOOL_REQUEST"
    TOOL_RESULT = "TOOL_RESULT"
    SUBAGENT_STARTED = "SUBAGENT_STARTED"
    SUBAGENT_COMPLETED = "SUBAGENT_COMPLETED"
    SANDBOX_STARTED = "SANDBOX_STARTED"
    SANDBOX_COMPLETED = "SANDBOX_COMPLETED"
    PERMISSION_REQUESTED = "PERMISSION_REQUESTED"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    ERROR = "ERROR"
    RETRY = "RETRY"
    AGENT_PAUSED = "AGENT_PAUSED"
    AGENT_RESUMED = "AGENT_RESUMED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"
    MEMORY_UPDATED = "MEMORY_UPDATED"

class AgentEvent(BaseModel):
    id: str
    session_id: str
    task_id: str
    type: AgentEventType
    timestamp: datetime = Field(default_factory=utc_now)
    source: str = "deepseek_harness"  # or "native", "subagent"
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: str = "SUCCESS"  # SUCCESS, FAILED, PENDING, BLOCKED
    parent_event_id: Optional[str] = None
    correlation_id: Optional[str] = None

class RuntimeSessionConfig(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    workspace_root: Optional[str] = None
    model_name: Optional[str] = None
    temperature: float = 0.2
    max_steps: int = 20
    context_data: Dict[str, Any] = Field(default_factory=dict)

class TrajectoryStep(BaseModel):
    step_id: str
    sequence: int
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    status: str = "COMPLETED"
    timestamp: datetime = Field(default_factory=utc_now)

class TrajectoryResponse(BaseModel):
    session_id: str
    task_id: str
    steps: List[TrajectoryStep] = Field(default_factory=list)
    total_steps: int = 0
    duration_ms: float = 0.0
