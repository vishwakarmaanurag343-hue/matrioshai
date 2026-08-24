import uuid
from typing import Dict, Any, Optional
from app.computer.models import (
    ComputerPrivacyMode, ComputerSessionStatus, ComputerStatusResponse,
    ComputerSessionResponse, MouseAction, KeyboardAction, utc_now
)
from app.computer.screen import screen_service
from app.computer.vision import vision_service
from app.computer.ocr import ocr_service
from app.computer.applications import application_service
from app.computer.mouse import mouse_service
from app.computer.keyboard import keyboard_service
from app.security.audit import audit_logger
from app.core.logging import logger

class ComputerService:
    """
    Central Computer Orchestration Service.
    Manages active sessions, privacy modes, emergency stop, and action validation.
    """

    def __init__(self):
        self.control_enabled = True
        self.privacy_mode = ComputerPrivacyMode.LOCAL_ONLY
        self.active_session: Optional[ComputerSessionResponse] = None

    def get_status(self) -> ComputerStatusResponse:
        return ComputerStatusResponse(
            computer_control_enabled=self.control_enabled,
            screen_recording_permission="GRANTED",
            accessibility_permission="GRANTED",
            privacy_mode=self.privacy_mode,
            active_session=self.active_session.id if self.active_session else None
        )

    def emergency_stop(self):
        logger.warning("EMERGENCY STOP TRIGGERED: Halting all computer interactions.")
        self.control_enabled = False
        mouse_service.set_enabled(False)
        keyboard_service.set_enabled(False)
        if self.active_session:
            self.active_session.status = ComputerSessionStatus.CANCELLED
            self.active_session.ended_at = utc_now()
        
        audit_logger.log_event(
            event_type="EMERGENCY_STOP",
            action="emergency_stop",
            decision="ALLOWED",
            reason="User triggered emergency stop for computer control"
        )

    def set_control_enabled(self, enabled: bool):
        self.control_enabled = enabled
        mouse_service.set_enabled(enabled)
        keyboard_service.set_enabled(enabled)

    def set_privacy_mode(self, mode: ComputerPrivacyMode):
        self.privacy_mode = mode
        audit_logger.log_event(
            event_type="PRIVACY_MODE_CHANGED",
            action="set_privacy_mode",
            resource=mode.value,
            decision="ALLOWED"
        )

    def start_session(self, task_id: Optional[str] = None) -> ComputerSessionResponse:
        sess = ComputerSessionResponse(
            id=str(uuid.uuid4()),
            task_id=task_id,
            status=ComputerSessionStatus.ACTIVE,
            privacy_mode=self.privacy_mode,
            active_application=application_service.get_active_application().application,
            screens_observed=0,
            actions_executed=0,
            started_at=utc_now()
        )
        self.active_session = sess
        audit_logger.log_event(
            event_type="COMPUTER_SESSION_STARTED",
            action="start_session",
            resource=sess.id,
            decision="ALLOWED"
        )
        return sess

    def stop_session(self) -> Optional[ComputerSessionResponse]:
        if self.active_session:
            self.active_session.status = ComputerSessionStatus.COMPLETED
            self.active_session.ended_at = utc_now()
            sess = self.active_session
            self.active_session = None
            return sess
        return None

computer_service = ComputerService()
