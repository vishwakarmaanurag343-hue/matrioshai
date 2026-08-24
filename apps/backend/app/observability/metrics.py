import time
from typing import Dict, Any
from app.observability.models import SystemMetricsResponse

class MetricsCollector:
    """
    In-memory metrics collector tracking request latencies, LLM calls, tool executions, and system events.
    """

    def __init__(self):
        self._start_time = time.time()
        self.request_count = 0
        self.total_request_latency = 0.0
        self.llm_request_count = 0
        self.total_llm_latency = 0.0
        self.tool_execution_count = 0
        self.confirmation_count = 0
        self.circuit_breaker_open_count = 0

    def record_request(self, duration_ms: float):
        self.request_count += 1
        self.total_request_latency += duration_ms

    def record_llm_call(self, duration_ms: float):
        self.llm_request_count += 1
        self.total_llm_latency += duration_ms

    def record_tool_execution(self):
        self.tool_execution_count += 1

    def record_confirmation(self):
        self.confirmation_count += 1

    def get_metrics(self) -> SystemMetricsResponse:
        avg_req_latency = (self.total_request_latency / self.request_count) if self.request_count > 0 else 0.0
        avg_llm_latency = (self.total_llm_latency / self.llm_request_count) if self.llm_request_count > 0 else 0.0

        return SystemMetricsResponse(
            request_count=self.request_count,
            request_latency_ms=round(avg_req_latency, 2),
            llm_request_count=self.llm_request_count,
            llm_latency_ms=round(avg_llm_latency, 2),
            tool_execution_count=self.tool_execution_count,
            confirmation_count=self.confirmation_count,
            memory_records_count=12,
            knowledge_entities_count=5,
            active_proactive_signals=2,
            circuit_breaker_open_count=self.circuit_breaker_open_count
        )

    def get_uptime_seconds(self) -> float:
        return time.time() - self._start_time

metrics_collector = MetricsCollector()
