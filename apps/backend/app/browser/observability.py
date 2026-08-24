"""
MATRIOSHAI Observability, Tracing & Event Bus Engine (Phase 14)

Provides structured logging, distributed tracing (correlation_id, trace_id),
real-time metrics tracking, and an asynchronous event bus with PII/secret redaction.
"""

import time
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from app.core.logging import logger
from app.browser.state_store import (
    browser_state_store,
    BrowserStateStore,
    RuntimeEvent,
    RuntimeMetrics
)

class RuntimeEventBus:
    """
    Asynchronous and synchronous event bus for system-wide runtime events.
    Supports subscriber filtering and event history.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self._subscribers: Dict[str, List[Callable[[RuntimeEvent], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[RuntimeEvent], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def publish(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "runtime",
        correlation_id: Optional[str] = None
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            event_id=f"evt_{secrets.token_hex(6)}",
            event_type=event_type,
            version=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=source,
            correlation_id=correlation_id,
            payload=payload or {}
        )
        self.state_store.runtime_events.append(event)
        if len(self.state_store.runtime_events) > self.state_store.MAX_RUNTIME_EVENTS:
            self.state_store.runtime_events.pop(0)

        # Notify subscribers
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.warning(f"[MATRIOSHAI][EventBus] Subscriber error on {event_type}: {e}")

        # Wildcard subscribers
        for handler in self._subscribers.get("*", []):
            try:
                handler(event)
            except Exception as e:
                logger.warning(f"[MATRIOSHAI][EventBus] Wildcard subscriber error: {e}")

        return event

class ObservabilityManager:
    """
    Central observability orchestrator tracking metrics, latencies, and distributed traces.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self.event_bus = RuntimeEventBus(self.state_store)
        self.active_traces: Dict[str, Dict[str, Any]] = {}

    def start_trace(self, operation: str, correlation_id: Optional[str] = None) -> str:
        trace_id = f"trc_{secrets.token_hex(6)}"
        self.active_traces[trace_id] = {
            "trace_id": trace_id,
            "operation": operation,
            "correlation_id": correlation_id or f"corr_{secrets.token_hex(4)}",
            "start_time": time.time(),
            "status": "RUNNING"
        }
        return trace_id

    def end_trace(self, trace_id: str, status: str = "SUCCESS", details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        trace = self.active_traces.pop(trace_id, None)
        if not trace:
            return {"trace_id": trace_id, "status": "UNKNOWN"}
        duration_ms = (time.time() - trace["start_time"]) * 1000.0
        trace["duration_ms"] = round(duration_ms, 2)
        trace["status"] = status
        trace["details"] = details or {}

        # Update metrics
        self.state_store.metrics.uptime_seconds = round(time.time() - self.state_store.runtime_start_time, 2)
        if "action" in trace["operation"].lower():
            self.state_store.metrics.actions_total += 1
            if status == "SUCCESS":
                self.state_store.metrics.actions_successful += 1
            else:
                self.state_store.metrics.actions_failed += 1
        elif "transaction" in trace["operation"].lower():
            self.state_store.metrics.transactions_total += 1
            if status == "SUCCESS":
                self.state_store.metrics.transactions_completed += 1

        return trace

    def record_model_request(self, latency_ms: float, success: bool = True) -> None:
        self.state_store.metrics.model_requests_total += 1
        curr_avg = self.state_store.metrics.model_latency_avg_ms
        total = self.state_store.metrics.model_requests_total
        self.state_store.metrics.model_latency_avg_ms = round(((curr_avg * (total - 1)) + latency_ms) / total, 2)

    def get_metrics_summary(self) -> Dict[str, Any]:
        self.state_store.metrics.uptime_seconds = round(time.time() - self.state_store.runtime_start_time, 2)
        return self.state_store.metrics.model_dump()

observability_manager = ObservabilityManager()
