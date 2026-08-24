import pytest
from app.observability.models import SubsystemStatus
from app.observability.metrics import metrics_collector
from app.observability.resilience import CircuitBreaker, idempotency_engine
from app.database.backup import database_backup_service

def test_metrics_collection_and_uptime():
    metrics_collector.record_request(15.5)
    metrics_collector.record_llm_call(250.0)
    metrics_collector.record_tool_execution()
    metrics_collector.record_confirmation()

    m = metrics_collector.get_metrics()
    assert m.request_count >= 1
    assert m.llm_request_count >= 1
    assert m.tool_execution_count >= 1
    assert m.confirmation_count >= 1
    assert metrics_collector.get_uptime_seconds() > 0

def test_circuit_breaker_transitions():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.1)
    assert cb.state == "CLOSED"
    assert cb.can_execute() is True

    # 1st failure -> still CLOSED
    cb.record_failure()
    assert cb.state == "CLOSED"

    # 2nd failure -> trips to OPEN
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.can_execute() is False

    # Success resets to CLOSED
    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb.can_execute() is True

def test_idempotency_key_consumption():
    key = "idemp_test_key_123"
    # 1st registration -> fresh (True)
    is_fresh = idempotency_engine.register_and_check(key, "send message payload")
    assert is_fresh is True

    # 2nd registration -> duplicate consumed (False)
    is_duplicate = idempotency_engine.register_and_check(key, "send message payload")
    assert is_duplicate is False

def test_database_backup_and_integrity_check():
    integrity = database_backup_service.check_integrity()
    assert integrity in ("OK", "CORRUPTED")

    backup_meta = database_backup_service.create_backup()
    assert backup_meta.backup_id is not None
    assert backup_meta.filename.endswith(".db")

    backups = database_backup_service.list_backups()
    assert len(backups) >= 1
