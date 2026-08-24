"""
MATRIOSHAI Resilience, Circuit Breakers & Fault Tolerance Engine (Phase 14)

Provides:
- Circuit Breaker (CLOSED, OPEN, HALF_OPEN)
- Risk-Classified Retry Engine (SAFE vs NO BLIND RETRY)
- Loop & Stall Detector (Oscillation & repeated action prevention)
- Dead Letter Queue for failed unrecoverable events
"""

import time
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from app.core.logging import logger
from app.browser.state_store import (
    browser_state_store,
    BrowserStateStore,
    CircuitBreakerState,
    DeadLetterItem
)

class CircuitBreaker:
    """
    Protects downstream systems (Model Providers, External Websites, Bridge)
    from cascading failure loops.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        state_store: Optional[BrowserStateStore] = None
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.state_store = state_store or browser_state_store

        self.state: CircuitBreakerState = CircuitBreakerState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: float = 0.0

    def can_execute(self) -> bool:
        if self.state == CircuitBreakerState.CLOSED:
            return True
        if self.state == CircuitBreakerState.OPEN:
            # Check if cooldown has elapsed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"[MATRIOSHAI][CircuitBreaker] '{self.name}' transitioned from OPEN -> HALF_OPEN (Trial call permitted)")
                return True
            return False
        # HALF_OPEN allows single trial call
        return True

    def record_success(self) -> None:
        if self.state in [CircuitBreakerState.OPEN, CircuitBreakerState.HALF_OPEN]:
            logger.info(f"[MATRIOSHAI][CircuitBreaker] '{self.name}' recovered: CLOSED")
            if self.state_store:
                self.state_store.metrics.circuit_breakers_open = max(0, self.state_store.metrics.circuit_breakers_open - 1)
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == CircuitBreakerState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            if self.state != CircuitBreakerState.OPEN:
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"[MATRIOSHAI][CircuitBreaker] '{self.name}' tripped: OPEN (threshold={self.failure_threshold})")
                if self.state_store:
                    self.state_store.metrics.circuit_breakers_open += 1

class RetryEngine:
    """
    Evaluates whether an operation is safe to retry.
    Strictly forbids blind retries on mutating commit or financial operations.
    """

    SAFE_ACTIONS = {"OBSERVE", "NAVIGATE", "READ", "SCROLL", "HEALTH", "STATUS"}
    MUTATING_ACTIONS = {"PAY", "PURCHASE", "BOOK", "DELETE", "SUBMIT", "SEND_MESSAGE"}

    def can_retry(self, action_type: str, attempt: int, max_attempts: int = 3) -> Tuple[bool, str]:
        if attempt >= max_attempts:
            return False, f"Maximum retry attempts reached ({max_attempts})"

        act_upper = action_type.upper()
        if any(m in act_upper for m in self.MUTATING_ACTIONS):
            return False, f"Action '{action_type}' is mutating/high-consequence; blind retries are forbidden"

        return True, "Action is idempotent/safe to retry"

    def compute_backoff(self, attempt: int, base_delay: float = 1.0, max_delay: float = 10.0) -> float:
        import random
        delay = min(max_delay, base_delay * (2 ** attempt))
        jitter = random.uniform(0.1, 0.5)
        return delay + jitter

class LoopDetector:
    """
    Detects action and navigation oscillation loops.
    """

    def __init__(self, history_window: int = 6):
        self.history_window = history_window
        self.recent_actions: List[str] = []
        self.recent_urls: List[str] = []

    def record_step(self, action_signature: str, url: str) -> bool:
        """
        Returns True if an oscillation loop is detected.
        """
        self.recent_actions.append(action_signature)
        self.recent_urls.append(url)

        if len(self.recent_actions) > self.history_window:
            self.recent_actions.pop(0)
            self.recent_urls.pop(0)

        # Check for 3 repeated identical actions in a row
        if len(self.recent_actions) >= 3 and len(set(self.recent_actions[-3:])) == 1:
            logger.warning(f"[MATRIOSHAI][LoopDetector] Action repetition loop detected: {self.recent_actions[-1]}")
            return True

        # Check for URL ping-pong (A -> B -> A -> B)
        if len(self.recent_urls) >= 4:
            if self.recent_urls[-1] == self.recent_urls[-3] and self.recent_urls[-2] == self.recent_urls[-4] and self.recent_urls[-1] != self.recent_urls[-2]:
                logger.warning(f"[MATRIOSHAI][LoopDetector] Navigation ping-pong loop detected: {self.recent_urls[-2]} <-> {self.recent_urls[-1]}")
                return True

        return False

class DeadLetterQueue:
    """
    Captures permanently failed operations without silently dropping them.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store

    def push(self, source: str, payload: Dict[str, Any], error_message: str, attempts: int = 1) -> DeadLetterItem:
        item = DeadLetterItem(
            item_id=f"dlq_{secrets.token_hex(6)}",
            source=source,
            payload=payload,
            error_message=error_message,
            attempts=attempts,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        self.state_store.dead_letter_queue.append(item)
        if len(self.state_store.dead_letter_queue) > self.state_store.MAX_DEAD_LETTER_ITEMS:
            self.state_store.dead_letter_queue.pop(0)
        logger.warning(f"[MATRIOSHAI][DLQ] Enqueued failed job from '{source}': {error_message}")
        return item

    def get_items(self, limit: int = 50) -> List[DeadLetterItem]:
        return self.state_store.dead_letter_queue[-limit:]

dead_letter_queue = DeadLetterQueue()
retry_engine = RetryEngine()
