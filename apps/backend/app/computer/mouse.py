from typing import Tuple
from app.computer.models import MouseAction
from app.computer.policy import computer_policy
from app.security.audit import audit_logger
from app.core.logging import logger

class MouseService:
    """
    Controlled Mouse Dispatcher.
    Enforces screen coordinate validation and action policy.
    """

    def __init__(self):
        self._enabled = True

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def execute_mouse_action(self, action: MouseAction) -> Tuple[bool, str]:
        if not self._enabled:
            return False, "Mouse control is currently DISABLED by user."

        allowed, reason, risk = computer_policy.validate_mouse_action(action)
        if not allowed:
            return False, f"Blocked by ComputerPolicy: {reason}"

        logger.info(f"Executing mouse {action.action} at ({action.x}, {action.y})...")

        audit_logger.log_event(
            event_type="MOUSE_EXECUTED",
            action=f"mouse_{action.action}",
            resource=f"x={action.x},y={action.y},btn={action.button}",
            decision="ALLOWED",
            reason=f"Executed {action.action}"
        )
        return True, f"Mouse {action.action} executed at ({action.x}, {action.y})"

mouse_service = MouseService()
