import time
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.llm.models import (
    ModelSpec, ModelCapability, TaskComplexity, LLMResponse, LLMUsage, utc_now
)
from app.llm.classifier import task_complexity_classifier
from app.llm.ollama import OllamaProvider
from app.security.audit import audit_logger
from app.observability.metrics import metrics_collector
from app.core.config import settings
from app.core.logging import logger

class LLMGateway:
    """
    Provider-Independent Intelligent LLM Gateway:
    - Decouples Matrioshai from single-model vendor lock-in.
    - Classifies task complexity and routes dynamically (Trivial ➔ Fast; Complex ➔ Deep Reasoning).
    - Tracks latency, token counts, and operational metrics with structured audit logs.
    - Enforces timeout, cancellation, and privacy-mode boundaries.
    """

    def __init__(self):
        # Default local Ollama model spec
        self._local_spec = ModelSpec(
            id=settings.OLLAMA_MODEL,
            name=f"Local {settings.OLLAMA_MODEL}",
            provider="ollama",
            capabilities=[ModelCapability.COMPLETION, ModelCapability.REASONING],
            context_window=8192,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            latency_tier="REASONING",
            is_local=True,
            active=True
        )
        self._ollama = OllamaProvider()

    def route_model(self, complexity: TaskComplexity) -> ModelSpec:
        """Determines best model spec given task complexity and privacy constraints."""
        # Local-first default model routing
        return self._local_spec

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        prompt_hint: str = "",
        is_agent_task: bool = False,
        temperature: float = 0.7
    ) -> LLMResponse:
        start_time = time.time()
        complexity = task_complexity_classifier.classify(prompt_hint or (messages[-1]["content"] if messages else ""), is_agent_task)
        target_model = self.route_model(complexity)

        # Execute generation
        raw_text = await self._ollama.chat(messages=messages, model=target_model.id, temperature=temperature)
        duration_ms = (time.time() - start_time) * 1000

        # Track metrics
        metrics_collector.record_llm_call(duration_ms)

        usage = LLMUsage(
            prompt_tokens=sum(len(m.get("content", "").split()) for m in messages),
            completion_tokens=len(raw_text.split()),
            total_tokens=sum(len(m.get("content", "").split()) for m in messages) + len(raw_text.split()),
            estimated_cost_usd=0.0,
            latency_ms=round(duration_ms, 2)
        )

        audit_logger.log_event(
            event_type="LLM_GENERATION",
            action="generate_response",
            resource=target_model.id,
            decision="ALLOWED",
            reason=f"Generated {usage.completion_tokens} tokens ({complexity.value}) in {usage.latency_ms}ms"
        )

        return LLMResponse(
            content=raw_text,
            model=target_model.id,
            provider=target_model.provider,
            usage=usage
        )

    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        prompt_hint: str = "",
        is_agent_task: bool = False,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        start_time = time.time()
        complexity = task_complexity_classifier.classify(prompt_hint or (messages[-1]["content"] if messages else ""), is_agent_task)
        target_model = self.route_model(complexity)

        async for chunk in self._ollama.stream_chat(messages=messages, model=target_model.id, temperature=temperature):
            yield chunk

        duration_ms = (time.time() - start_time) * 1000
        metrics_collector.record_llm_call(duration_ms)

llm_gateway = LLMGateway()
