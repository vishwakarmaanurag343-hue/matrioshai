from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class TaskComplexity(str, Enum):
    TRIVIAL = "TRIVIAL"                  # Simple greetings, basic definitions, small lookups
    STANDARD = "STANDARD"                # Standard summarization, chat responses
    DEEP_REASONING = "DEEP_REASONING"    # 5C Executive, financial logic, multi-step code analysis
    AUTONOMOUS_AGENT = "AUTONOMOUS_AGENT"# Multi-step planning, file editing, computer use

class ModelCapability(str, Enum):
    COMPLETION = "COMPLETION"
    REASONING = "REASONING"
    VISION = "VISION"
    TOOL_CALLING = "TOOL_CALLING"
    EMBEDDING = "EMBEDDING"

class ModelSpec(BaseModel):
    id: str
    name: str
    provider: str                        # "ollama", "deepseek", "qwen", "glm", "openai_compatible"
    capabilities: List[ModelCapability] = Field(default_factory=list)
    context_window: int = 8192
    cost_per_1k_input: float = 0.0       # USD (0.0 for local)
    cost_per_1k_output: float = 0.0
    latency_tier: str = "FAST"           # "FAST", "MEDIUM", "REASONING"
    is_local: bool = True
    active: bool = True

class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0

class LLMResponse(BaseModel):
    content: str
    model: str
    provider: str
    usage: LLMUsage
    finish_reason: str = "stop"
    timestamp: datetime = Field(default_factory=utc_now)
