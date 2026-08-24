from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from app.executive.roles import ExecutiveRole

def utc_now():
    return datetime.now(timezone.utc)

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class DecisionStatus(str, Enum):
    OPEN = "OPEN"
    DECIDED = "DECIDED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"
    REVISIT = "REVISIT"

class ExecutiveResponse(BaseModel):
    role: ExecutiveRole
    summary: str = Field(..., description="Executive summary from this role's perspective")
    key_findings: List[str] = Field(default_factory=list, description="Core analytical findings")
    assumptions: List[str] = Field(default_factory=list, description="Explicit assumptions made in analysis")
    risks: List[str] = Field(default_factory=list, description="Domain-specific risks identified")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM, description="Structured confidence level based on data completeness")
    confidence_reason: Optional[str] = Field(None, description="Explanation for confidence rating")
    missing_information: List[str] = Field(default_factory=list, description="Required data that was missing from context")

class SynthesisResponse(BaseModel):
    question: str
    summary: str
    agreements: List[str] = Field(default_factory=list, description="Points of cross-functional executive alignment")
    conflicts: List[str] = Field(default_factory=list, description="Direct strategic, operational, financial, or technical disagreements")
    critical_risks: List[str] = Field(default_factory=list, description="Primary blockers or existential risks highlighted")
    missing_information: List[str] = Field(default_factory=list, description="Global missing context needed for a high-confidence decision")
    final_recommendation: str = Field(..., description="Synthesized executive recommendation")
    next_actions: List[str] = Field(default_factory=list, description="Concrete next steps")
    executive_assessments: Dict[ExecutiveRole, ExecutiveResponse] = Field(default_factory=dict)

class AnalyzeRequest(BaseModel):
    role: ExecutiveRole
    prompt: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    save_as_decision: bool = False
    decision_title: Optional[str] = None

class Council5CRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    save_as_decision: bool = True
    decision_title: Optional[str] = None

class DecisionInputItem(BaseModel):
    id: str
    role: ExecutiveRole
    summary: str
    key_findings: List[str]
    assumptions: List[str]
    risks: List[str]
    recommendations: List[str]
    confidence: ConfidenceLevel
    missing_information: List[str]

class DecisionResponse(BaseModel):
    id: str
    title: str
    question: str
    status: DecisionStatus
    final_recommendation: Optional[str]
    reasoning_summary: Optional[str]
    agreements: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    critical_risks: List[str] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)
    executive_inputs: List[DecisionInputItem] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
