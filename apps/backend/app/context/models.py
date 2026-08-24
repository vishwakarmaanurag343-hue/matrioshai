from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class ContextTier(str, Enum):
    TIER_1_CRITICAL = "TIER_1_CRITICAL"      # Full content: modified files, errors, failing tests, direct interfaces
    TIER_2_SUPPORTING = "TIER_2_SUPPORTING"  # Selective: direct imports, type definitions, neighboring config
    TIER_3_BACKGROUND = "TIER_3_BACKGROUND"  # On-demand: documentation, distant modules
    TIER_4_IRRELEVANT = "TIER_4_IRRELEVANT"  # Omitted: unrelated packages, binaries, logs

class CodeSymbolType(str, Enum):
    FUNCTION = "FUNCTION"
    CLASS = "CLASS"
    INTERFACE = "INTERFACE"
    TYPE_ALIAS = "TYPE_ALIAS"
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"

class CodeSymbol(BaseModel):
    name: str
    symbol_type: CodeSymbolType
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None

class FileContextItem(BaseModel):
    file_path: str
    tier: ContextTier
    relevance_score: float = 1.0
    content: str
    is_truncated: bool = False
    symbols: List[CodeSymbol] = Field(default_factory=list)

class TaskContextBundle(BaseModel):
    task_id: str
    user_goal: str
    tier_1_files: List[FileContextItem] = Field(default_factory=list)
    tier_2_files: List[FileContextItem] = Field(default_factory=list)
    relevant_errors: List[str] = Field(default_factory=list)
    git_status_summary: Optional[str] = None
    total_estimated_tokens: int = 0
    created_at: datetime = Field(default_factory=utc_now)

class TokenBudgetReport(BaseModel):
    task_id: str
    context_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    tool_tokens: int = 0
    retry_tokens: int = 0
    total_task_tokens: int = 0
    estimated_cost_usd: float = 0.0
    reduction_percentage: float = 0.0
