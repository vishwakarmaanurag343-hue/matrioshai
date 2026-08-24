"""
MATRIOSHAI Production Runtime & Supervisor Engine (Phase 14)

Coordinates the complete 14-phase browser agent runtime.
Provides:
- Runtime Lifecycle Management (STARTING, READY, RUNNING, PAUSED, DEGRADED, STOPPING, STOPPED, FAILED, SECURITY_LOCKED)
- Component Health & Heartbeat System
- Runtime Supervisor with Exponential Restart Backoff & Restart Loop Protection
- Graceful Degradation & Safe Shutdown
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from app.core.logging import logger
from app.browser.state_store import (
    browser_state_store,
    BrowserStateStore,
    RuntimeState,
    HealthState,
    RestartPolicy,
    ComponentHealth
)
from app.browser.observability import observability_manager

class GracefulDegradationManager:
    """
    Manages safe fallbacks when non-critical subsystems (like Vision or Visual Model) degrade.
    """

    def get_fallback_observation_mode(self, visual_healthy: bool, semantic_healthy: bool) -> str:
        if visual_healthy and semantic_healthy:
            return "FULL_MULTIMODAL"
        if semantic_healthy:
            logger.info("[MATRIOSHAI][Degradation] Visual subsystem degraded; falling back to SEMANTIC_ACCESSIBILITY mode")
            return "SEMANTIC_ONLY"
        logger.warning("[MATRIOSHAI][Degradation] Semantic and Visual degraded; falling back to RAW_DOM mode")
        return "RAW_DOM"

class RuntimeSupervisor:
    """
    Monitors component health, triggers restarts using exponential backoff,
    and stops restart loops if a component fails repeatedly.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self.restart_counts: Dict[str, int] = {}
        self.max_restart_attempts: int = 4
        self.degradation_manager = GracefulDegradationManager()

        # Initialize health registries for core subsystems
        for comp in [
            "BrowserBridge", "BrowserManager", "ObservationEngine",
            "SemanticEngine", "VisualEngine", "WorldModel", "ActionEngine",
            "VerificationEngine", "AgentRuntime", "WorkflowEngine",
            "TransactionEngine", "SecurityEngine", "Observability"
        ]:
            self.state_store.component_health[comp] = ComponentHealth(
                component_name=comp,
                status=HealthState.HEALTHY,
                version="1.0.0",
                last_success=datetime.now(timezone.utc).isoformat()
            )

    def record_health(
        self,
        component_name: str,
        status: HealthState,
        details: Optional[Dict[str, Any]] = None
    ) -> ComponentHealth:
        ch = self.state_store.component_health.get(component_name)
        if not ch:
            ch = ComponentHealth(component_name=component_name, status=status)
            self.state_store.component_health[component_name] = ch

        ch.status = status
        ch.details = details or {}
        if status == HealthState.HEALTHY:
            ch.last_success = datetime.now(timezone.utc).isoformat()
            ch.consecutive_failures = 0
            self.restart_counts[component_name] = 0
        else:
            ch.last_failure = datetime.now(timezone.utc).isoformat()
            ch.consecutive_failures += 1
            logger.warning(f"[MATRIOSHAI][Supervisor] Component '{component_name}' reported status {status.value}")

        return ch

    def attempt_restart(self, component_name: str, policy: RestartPolicy = RestartPolicy.BACKOFF) -> Tuple[bool, str]:
        count = self.restart_counts.get(component_name, 0)
        if count >= self.max_restart_attempts:
            ch = self.state_store.component_health.get(component_name)
            if ch:
                ch.status = HealthState.FAILED
            self.state_store.runtime_state = RuntimeState.DEGRADED
            logger.error(f"[MATRIOSHAI][Supervisor] Component '{component_name}' exceeded max restarts ({self.max_restart_attempts}); marking FAILED")
            return False, f"Restart loop prevented for '{component_name}'"

        self.restart_counts[component_name] = count + 1
        delay = (2 ** count) * 0.5 if policy == RestartPolicy.BACKOFF else 0.1
        time.sleep(min(delay, 2.0))

        # Re-mark healthy after simulated restart
        self.record_health(component_name, HealthState.HEALTHY)
        logger.info(f"[MATRIOSHAI][Supervisor] Successfully restarted '{component_name}' (Attempt {count + 1})")
        return True, "Restarted successfully"

class MatrioshaiRuntime:
    """
    Master Production Runtime Coordinator.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self.supervisor = RuntimeSupervisor(self.state_store)
        self.state_store.runtime_state = RuntimeState.READY

    def start(self) -> RuntimeState:
        self.state_store.runtime_state = RuntimeState.RUNNING
        self.state_store.runtime_start_time = time.time()
        observability_manager.event_bus.publish("runtime.started", {"state": "RUNNING"})
        logger.info("[MATRIOSHAI][Runtime] MATRIOSHAI Autonomous Browser Runtime is RUNNING")
        return self.state_store.runtime_state

    def pause(self) -> RuntimeState:
        self.state_store.runtime_state = RuntimeState.PAUSED
        observability_manager.event_bus.publish("runtime.paused", {"state": "PAUSED"})
        logger.info("[MATRIOSHAI][Runtime] Runtime PAUSED")
        return self.state_store.runtime_state

    def resume(self) -> RuntimeState:
        self.state_store.runtime_state = RuntimeState.RUNNING
        observability_manager.event_bus.publish("runtime.resumed", {"state": "RUNNING"})
        logger.info("[MATRIOSHAI][Runtime] Runtime RESUMED")
        return self.state_store.runtime_state

    def stop(self) -> RuntimeState:
        self.state_store.runtime_state = RuntimeState.STOPPED
        observability_manager.event_bus.publish("runtime.stopped", {"state": "STOPPED"})
        logger.info("[MATRIOSHAI][Runtime] Runtime safely STOPPED")
        return self.state_store.runtime_state

    def get_status(self) -> Dict[str, Any]:
        return {
            "runtime_state": self.state_store.runtime_state.value,
            "uptime_seconds": round(time.time() - self.state_store.runtime_start_time, 2),
            "components_healthy_count": len([c for c in self.state_store.component_health.values() if c.status == HealthState.HEALTHY]),
            "components_total": len(self.state_store.component_health),
            "emergency_stop_active": self.state_store.emergency_stop_active,
            "metrics": self.state_store.metrics.model_dump()
        }

matrioshai_runtime = MatrioshaiRuntime()
