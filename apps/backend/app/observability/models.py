from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class SubsystemStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"

class SubsystemHealth(BaseModel):
    name: str
    status: SubsystemStatus
    latency_ms: float = 0.0
    details: Optional[str] = None
    last_checked: datetime = Field(default_factory=utc_now)

class HealthStatusResponse(BaseModel):
    overall_status: SubsystemStatus
    app_version: str = "0.1.0"
    uptime_seconds: float
    subsystems: List[SubsystemHealth] = Field(default_factory=list)

class SystemMetricsResponse(BaseModel):
    request_count: int = 0
    request_latency_ms: float = 0.0
    llm_request_count: int = 0
    llm_latency_ms: float = 0.0
    tool_execution_count: int = 0
    confirmation_count: int = 0
    memory_records_count: int = 0
    knowledge_entities_count: int = 0
    active_proactive_signals: int = 0
    circuit_breaker_open_count: int = 0

class StructuredEvent(BaseModel):
    event_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    correlation_id: str
    component: str
    operation: str
    status: str  # SUCCESS, FAILED, WARNING, BLOCKED
    duration_ms: float = 0.0
    details: Optional[str] = None

class DatabaseBackupMetadata(BaseModel):
    backup_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    filename: str
    size_bytes: int
    integrity_status: str  # OK, CORRUPTED

class DiagnosticsReport(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    overall_health: SubsystemStatus
    checks_passed: int
    checks_failed: int
    diagnostics: List[Dict[str, Any]] = Field(default_factory=list)
