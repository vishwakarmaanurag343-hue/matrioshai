import pytest
from app.browser.state_store import (
    BrowserStateStore,
    RuntimeState,
    HealthState,
    RestartPolicy,
    CircuitBreakerState
)
from app.browser.runtime import MatrioshaiRuntime, RuntimeSupervisor, GracefulDegradationManager
from app.browser.resilience import CircuitBreaker, RetryEngine, LoopDetector, DeadLetterQueue
from app.browser.observability import ObservabilityManager, RuntimeEventBus
from app.browser.chaos import FaultInjectionEngine

@pytest.fixture
def mock_store():
    return BrowserStateStore()

def test_runtime_lifecycle_transitions(mock_store):
    """Test runtime state machine transitions."""
    runtime = MatrioshaiRuntime(mock_store)
    assert mock_store.runtime_state == RuntimeState.READY

    runtime.start()
    assert mock_store.runtime_state == RuntimeState.RUNNING

    runtime.pause()
    assert mock_store.runtime_state == RuntimeState.PAUSED

    runtime.resume()
    assert mock_store.runtime_state == RuntimeState.RUNNING

    runtime.stop()
    assert mock_store.runtime_state == RuntimeState.STOPPED

def test_component_health_tracking_and_supervisor_restart(mock_store):
    """Test component health reporting and restart with loop protection."""
    supervisor = RuntimeSupervisor(mock_store)

    # Record component degradation
    ch = supervisor.record_health("ObservationEngine", HealthState.DEGRADED)
    assert ch.status == HealthState.DEGRADED
    assert ch.consecutive_failures == 1

    # Restart attempt 1: Success
    success, msg = supervisor.attempt_restart("ObservationEngine", RestartPolicy.IMMEDIATE)
    assert success is True
    assert mock_store.component_health["ObservationEngine"].status == HealthState.HEALTHY

    # Simulate repeated failures exceeding threshold
    supervisor.restart_counts["ObservationEngine"] = 4
    success_loop, msg_loop = supervisor.attempt_restart("ObservationEngine")
    assert success_loop is False
    assert "restart loop prevented" in msg_loop.lower()
    assert mock_store.component_health["ObservationEngine"].status == HealthState.FAILED
    assert mock_store.runtime_state == RuntimeState.DEGRADED

def test_graceful_degradation():
    """Test fallback strategy when visual or semantic engines degrade."""
    gdm = GracefulDegradationManager()
    assert gdm.get_fallback_observation_mode(visual_healthy=True, semantic_healthy=True) == "FULL_MULTIMODAL"
    assert gdm.get_fallback_observation_mode(visual_healthy=False, semantic_healthy=True) == "SEMANTIC_ONLY"
    assert gdm.get_fallback_observation_mode(visual_healthy=False, semantic_healthy=False) == "RAW_DOM"

def test_circuit_breaker_state_machine(mock_store):
    """Test circuit breaker transitions from CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    cb = CircuitBreaker("test_model", failure_threshold=2, recovery_timeout_seconds=0.1, state_store=mock_store)
    assert cb.can_execute() is True
    assert cb.state == CircuitBreakerState.CLOSED

    # Trip the breaker
    cb.record_failure()
    assert cb.state == CircuitBreakerState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.can_execute() is False

    # Wait for cooldown to transition to HALF_OPEN
    import time
    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Success in HALF_OPEN resets to CLOSED
    cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.can_execute() is True

def test_retry_engine_classification():
    """Test that safe operations can be retried but mutating actions are blocked from blind retries."""
    re = RetryEngine()

    # Safe read-only actions
    can_retry_obs, _ = re.can_retry("OBSERVE", attempt=1)
    assert can_retry_obs is True

    can_retry_nav, _ = re.can_retry("NAVIGATE", attempt=1)
    assert can_retry_nav is True

    # Mutating actions must NEVER be blindly retried
    can_retry_pay, msg_pay = re.can_retry("PAY", attempt=1)
    assert can_retry_pay is False
    assert "blind retries are forbidden" in msg_pay.lower()

    can_retry_book, msg_book = re.can_retry("BOOK", attempt=1)
    assert can_retry_book is False

def test_loop_and_oscillation_detection():
    """Test detecting action loops and ping-pong navigation loops."""
    ld = LoopDetector(history_window=6)

    # Normal distinct actions
    assert ld.record_step("click_search", "https://site.com/search") is False
    assert ld.record_step("select_filter", "https://site.com/search") is False

    # Repeated identical actions in a row
    assert ld.record_step("click_btn", "https://site.com/search") is False
    assert ld.record_step("click_btn", "https://site.com/search") is False
    assert ld.record_step("click_btn", "https://site.com/search") is True

    # Navigation ping-pong loop (A -> B -> A -> B)
    ld2 = LoopDetector(history_window=6)
    assert ld2.record_step("nav_a", "https://site.com/a") is False
    assert ld2.record_step("nav_b", "https://site.com/b") is False
    assert ld2.record_step("nav_a", "https://site.com/a") is False
    assert ld2.record_step("nav_b", "https://site.com/b") is True

def test_dead_letter_queue_push_and_retrieval(mock_store):
    """Test capturing unrecoverable errors into DLQ."""
    dlq = DeadLetterQueue(mock_store)
    item = dlq.push(
        source="action_engine",
        payload={"action_id": "act_fail_1"},
        error_message="Fatal unrecoverable bridge exception",
        attempts=3
    )
    assert item.item_id.startswith("dlq_")
    assert len(dlq.get_items()) == 1
    assert dlq.get_items()[0].error_message == "Fatal unrecoverable bridge exception"

def test_distributed_tracing_and_event_bus(mock_store):
    """Test distributed trace propagation and event bus publishing."""
    obs = ObservabilityManager(mock_store)

    trace_id = obs.start_trace("browser_action_click", correlation_id="corr_user_123")
    assert trace_id.startswith("trc_")
    assert obs.active_traces[trace_id]["correlation_id"] == "corr_user_123"

    trace_res = obs.end_trace(trace_id, status="SUCCESS")
    assert trace_res["status"] == "SUCCESS"
    assert "duration_ms" in trace_res
    assert mock_store.metrics.actions_successful == 1

    # Test Event Bus
    published_events = []
    obs.event_bus.subscribe("custom.test.event", lambda evt: published_events.append(evt))
    evt = obs.event_bus.publish("custom.test.event", {"msg": "hello"}, correlation_id="corr_user_123")

    assert len(published_events) == 1
    assert published_events[0].event_type == "custom.test.event"
    assert published_events[0].correlation_id == "corr_user_123"

def test_fault_injection_chaos_engine():
    """Test chaos testing fault injection."""
    fie = FaultInjectionEngine()
    assert fie.should_fail("browser_bridge_disconnect") is False

    fie.inject_fault("browser_bridge_disconnect", {"failure_rate": 1.0})
    assert fie.should_fail("browser_bridge_disconnect") is True

    fie.clear_fault("browser_bridge_disconnect")
    assert fie.should_fail("browser_bridge_disconnect") is False
