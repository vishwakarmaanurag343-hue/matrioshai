import time
from typing import Dict, Any, Optional

class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreaker:
    """
    Circuit Breaker pattern for external providers (LLM, Telegram, WhatsApp, Email).
    States: CLOSED (normal), OPEN (tripped/failing), HALF_OPEN (probing).
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = 0.0

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout_seconds:
                self.state = "HALF_OPEN"
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return False

class IdempotencyEngine:
    """
    Ensures consequential actions with consumed idempotency keys are not executed twice.
    """

    def __init__(self):
        self._consumed_keys: Dict[str, Dict[str, Any]] = {}

    def register_and_check(self, key: str, payload_summary: str) -> bool:
        """
        Returns True if fresh/valid key; Returns False if duplicate consumed key.
        """
        if key in self._consumed_keys:
            return False
        self._consumed_keys[key] = {
            "payload": payload_summary,
            "consumed_at": time.time()
        }
        return True

idempotency_engine = IdempotencyEngine()
