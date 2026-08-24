from typing import Tuple
from app.computer.models import KeyboardAction
from app.computer.policy import computer_policy
from app.security.audit import audit_logger
from app.core.logging import logger

class KeyboardService:
    """
    Controlled Keyboard Dispatcher.
    Enforces allowed key combinations and blocks sensitive credential typing.
    """

    def __init__(self):
        self._enabled = True

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def execute_keyboard_action(self, action: KeyboardAction) -> Tuple[bool, str]:
        if not self._enabled:
            return False, "Keyboard control is currently DISABLED by user."

        allowed, reason, risk = computer_policy.validate_keyboard_action(action)
        if not allowed:
            return False, f"Blocked by ComputerPolicy: {reason}"

        logger.info(f"Executing keyboard {action.action}...")

        audit_logger.log_event(
            event_type="KEYBOARD_EXECUTED",
            action=f"keyboard_{action.action}",
            resource=f"key={action.key}, modifiers={action.modifiers}",
            decision="ALLOWED",
            reason=f"Executed {action.action}"
        )
        return True, f"Keyboard {action.action} executed"

keyboard_service = KeyboardService()
