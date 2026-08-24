"""
MATRIOSHAI Model Gateway & Context Management Engine (Phase 14)

Provides:
- Multi-Model Routing (Primary, Fallback, Vision, Specialized)
- Context Budgeting & Compaction
- Circuit-Breaker Protected Model Dispatch
- Decision Confidence Scoring
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from app.core.logging import logger
from app.browser.state_store import DecisionConfidence
from app.browser.resilience import CircuitBreaker
from app.browser.observability import observability_manager

class ModelProvider:
    """
    Abstract Model Provider definition.
    """

    def __init__(self, name: str, is_vision_capable: bool = False, cost_per_1k_tokens: float = 0.002):
        self.name = name
        self.is_vision_capable = is_vision_capable
        self.cost_per_1k = cost_per_1k
        self.circuit_breaker = CircuitBreaker(f"model_{name}", failure_threshold=3, recovery_timeout_seconds=20.0)

    async def generate_response(self, prompt: str, image_data: Optional[str] = None, timeout_seconds: float = 10.0) -> Tuple[bool, str, Dict[str, Any]]:
        if not self.circuit_breaker.can_execute():
            return False, f"Model '{self.name}' circuit breaker is OPEN", {}

        start_time = time.time()
        try:
            # Simulated model execution
            latency_ms = (time.time() - start_time) * 1000.0
            observability_manager.record_model_request(latency_ms, success=True)
            self.circuit_breaker.record_success()
            return True, f"Response from {self.name}", {"latency_ms": latency_ms, "tokens_used": len(prompt.split())}
        except Exception as e:
            self.circuit_breaker.record_failure()
            return False, f"Model error: {str(e)}", {}

class ModelRouter:
    """
    Routes requests dynamically to the best available model with fallback chains.
    """

    def __init__(self):
        self.providers: Dict[str, ModelProvider] = {
            "primary": ModelProvider("primary_fast_llm", is_vision_capable=False),
            "fallback": ModelProvider("fallback_stable_llm", is_vision_capable=False),
            "vision": ModelProvider("multimodal_vision_llm", is_vision_capable=True)
        }

    def select_model(self, requires_vision: bool = False) -> ModelProvider:
        if requires_vision:
            return self.providers["vision"]
        if self.providers["primary"].circuit_breaker.can_execute():
            return self.providers["primary"]
        logger.warning("[MATRIOSHAI][ModelRouter] Primary model degraded/tripped; routing to fallback")
        return self.providers["fallback"]

class ContextManager:
    """
    Budgets and compacts prompt context to avoid token exhaustion while preserving critical state.
    """

    def __init__(self, max_context_chars: int = 16000):
        self.max_context_chars = max_context_chars

    def compact_context(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        compacted = {}
        for k, v in context_data.items():
            if isinstance(v, list) and len(v) > 10:
                compacted[k] = v[-10:]  # Keep recent 10 items
            elif isinstance(v, str) and len(v) > 2000:
                compacted[k] = v[:1000] + "... [TRUNCATED] ..." + v[-500:]
            else:
                compacted[k] = v
        return compacted

model_router = ModelRouter()
context_manager = ContextManager()
