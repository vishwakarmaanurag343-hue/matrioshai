from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class ProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1)
    root_path: str = Field(..., min_length=1)

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    root_path: str
    project_type: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None
    package_manager: Optional[str] = None
    is_git: bool = False
    git_branch: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ProjectTreeNode(BaseModel):
    name: str
    path: str  # relative path from workspace root
    is_dir: bool
    size: Optional[int] = None
    is_sensitive: bool = False
    children: Optional[List['ProjectTreeNode']] = None

class FileContentResponse(BaseModel):
    path: str
    size: int
    content: str
    is_truncated: bool = False
    is_binary: bool = False

class SearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    max_results: int = 50

class SearchResultItem(BaseModel):
    file_path: str
    line_number: int
    line_content: str

class GitStatusResponse(BaseModel):
    branch: str
    is_clean: bool
    modified: List[str] = Field(default_factory=list)
    staged: List[str] = Field(default_factory=list)
    untracked: List[str] = Field(default_factory=list)

class GitDiffResponse(BaseModel):
    diff: str
    files_changed: List[str] = Field(default_factory=list)

class CommandExecutionRequest(BaseModel):
    command: str = Field(..., min_length=1)
    timeout_seconds: Optional[int] = 30

class CommandExecutionResponse(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    is_truncated: bool = False
    execution_time_ms: float

class CreateProposalRequest(BaseModel):
    title: str
    reason: str
    files: List[str]
    diff_content: str
    risk_level: str = "LOW"

class CodeChangeProposalResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    reason: str
    risk_level: str
    diff_content: str
    files: List[str]
    status: ProposalStatus
    backup_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class DiagnosticRequest(BaseModel):
    error_log: str = Field(..., min_length=1)
    command: Optional[str] = None

class DiagnosticResult(BaseModel):
    error_summary: str
    likely_causes: List[str]
    evidence: List[str]
    confidence: str
    recommended_actions: List[str]
    suggested_files_to_inspect: List[str]
