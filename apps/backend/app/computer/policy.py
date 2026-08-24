from typing import Tuple, List, Optional
from app.computer.models import MouseAction, KeyboardAction
from app.security.redaction import redaction_engine
from app.security.audit import audit_logger

class ComputerPolicy:
    """
    Validates and classifies all computer interactions:
    - Screen coordinate containment checks
    - Allowed keyboard key allowlist
    - Sensitive text input detection before typing
    - Risk classification (LOW, MEDIUM, HIGH, CRITICAL)
    """

    ALLOWED_KEYS = {
        "ENTER", "RETURN", "TAB", "SPACE", "ESCAPE", "ESC", "BACKSPACE", "DELETE",
        "UP", "DOWN", "LEFT", "RIGHT", "HOME", "END", "PAGEUP", "PAGEDOWN",
        "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"
    }

    ALLOWED_MODIFIERS = {"CMD", "COMMAND", "CTRL", "CONTROL", "ALT", "OPTION", "SHIFT"}

    DEFAULT_SCREEN_WIDTH = 1920
    DEFAULT_SCREEN_HEIGHT = 1080

    @classmethod
    def validate_mouse_action(
        cls,
        action: MouseAction,
        screen_width: int = DEFAULT_SCREEN_WIDTH,
        screen_height: int = DEFAULT_SCREEN_HEIGHT
    ) -> Tuple[bool, str, str]:
        """
        Validates mouse action.
        Returns: (allowed: bool, reason: str, risk_level: str)
        """
        # Coordinate bounds check
        if action.x < 0 or action.x > screen_width or action.y < 0 or action.y > screen_height:
            audit_logger.log_event(
                event_type="BLOCKED_ACTION",
                action=f"mouse_{action.action}",
                resource=f"x={action.x}, y={action.y}",
                decision="BLOCKED",
                reason=f"Coordinates out of bounds (max: {screen_width}x{screen_height})"
            )
            return False, f"Coordinates ({action.x}, {action.y}) are outside active screen ({screen_width}x{screen_height})", "HIGH"

        if action.action in ("click", "double_click", "right_click", "scroll"):
            return True, "Mouse action authorized", "MEDIUM"
        elif action.action == "move":
            return True, "Mouse movement authorized", "LOW"

        return False, f"Unknown mouse action '{action.action}'", "HIGH"

    @classmethod
    def validate_keyboard_action(cls, action: KeyboardAction) -> Tuple[bool, str, str]:
        """
        Validates keyboard action.
        Returns: (allowed: bool, reason: str, risk_level: str)
        """
        if action.action == "type_text":
            if not action.text:
                return False, "Empty text to type", "LOW"

            # Check if text contains sensitive secrets/credentials
            sanitized, redactions = redaction_engine.redact(action.text)
            if len(redactions) > 0 or any(term in action.text.lower() for term in ("password", "secret_key", "api_key")):
                audit_logger.log_event(
                    event_type="BLOCKED_ACTION",
                    action="keyboard_type_text",
                    resource="[SENSITIVE_TEXT_DETECTED]",
                    decision="BLOCKED",
                    reason="Attempt to type sensitive credential automatically without explicit approval."
                )
                return False, "Automated typing of detected credentials/passwords is prohibited.", "CRITICAL"

            return True, "Typing authorized", "MEDIUM"

        elif action.action == "press_key":
            key_name = (action.key or "").upper()
            if key_name not in cls.ALLOWED_KEYS and len(key_name) != 1:
                return False, f"Key '{key_name}' is not in allowed keys list.", "HIGH"
            return True, "Key press authorized", "MEDIUM"

        elif action.action == "hotkey":
            key_name = (action.key or "").upper()
            for mod in action.modifiers:
                if mod.upper() not in cls.ALLOWED_MODIFIERS:
                    return False, f"Modifier '{mod}' is not allowed.", "HIGH"
            return True, "Hotkey authorized", "MEDIUM"

        return False, f"Unknown keyboard action '{action.action}'", "HIGH"

computer_policy = ComputerPolicy()
