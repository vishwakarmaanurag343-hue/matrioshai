"""
MATRIOSHAI Chaos Testing & Fault Injection Engine (Phase 14)

Provides deterministic fault simulation for:
- Browser Disconnects
- Network Timeouts
- Model Failures
- Price / Terms Drift
- DOM Mutations
"""

import random
from typing import Dict, List, Optional, Any
from app.core.logging import logger

class FaultInjectionEngine:
    """
    Simulates real-world transient and hard failures in a controlled test environment.
    """

    def __init__(self):
        self.active_faults: Dict[str, Any] = {}

    def inject_fault(self, fault_type: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        self.active_faults[fault_type] = parameters or {}
        logger.warning(f"[MATRIOSHAI][Chaos] Injected fault '{fault_type}': {parameters}")

    def clear_fault(self, fault_type: str) -> None:
        self.active_faults.pop(fault_type, None)
        logger.info(f"[MATRIOSHAI][Chaos] Cleared fault '{fault_type}'")

    def clear_all_faults(self) -> None:
        self.active_faults.clear()

    def should_fail(self, operation: str) -> bool:
        if operation in self.active_faults:
            config = self.active_faults[operation]
            rate = config.get("failure_rate", 1.0)
            return random.random() < rate
        return False

fault_injection = FaultInjectionEngine()
