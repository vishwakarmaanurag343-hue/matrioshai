import hashlib
import time
from typing import Dict, Any, Tuple, Optional
from app.communication.models import SendMessageRequest, SendMessageResponse, utc_now
from app.security.confirmation import confirmation_system
from app.security.redaction import redaction_engine
from app.security.audit import audit_logger
from app.core.logging import logger

class SendService:
    """
    Message Send Controller.
    Enforces:
    - Tier 2 Exact confirmation hash binding
    - Secret & credential detection before sending
    - Duplicate send prevention
    - Rate limiting (max 5 sends / session)
    """

    MAX_SENDS_PER_SESSION = 5

    def __init__(self):
        self._recent_hashes: Dict[str, float] = {}  # hash -> timestamp
        self._session_send_count: int = 0
        self._enabled = True

    def reset_session(self):
        self._session_send_count = 0
        self._recent_hashes.clear()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def calculate_message_hash(self, req: SendMessageRequest) -> str:
        payload = f"{req.provider.value}:{req.conversation_id}:{req.recipient}:{req.text.strip()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def prepare_send_request(self, req: SendMessageRequest) -> Tuple[bool, str, Optional[str]]:
        if not self._enabled:
            return False, "Message sending is currently DISABLED.", None

        # 1. Secret detection
        sanitized, redactions = redaction_engine.redact(req.text)
        if len(redactions) > 0 or any(t in req.text.lower() for t in ("password", "api_key", "secret_key")):
            audit_logger.log_event(
                event_type="BLOCKED_ACTION",
                action="send_message",
                resource=req.recipient,
                decision="BLOCKED",
                reason="Attempt to send message containing sensitive credentials/secrets."
            )
            return False, "Security error: Message contains detected credentials or secret keys.", None

        # 2. Rate limit check
        if self._session_send_count >= self.MAX_SENDS_PER_SESSION:
            return False, f"Rate limit reached ({self.MAX_SENDS_PER_SESSION} sends per session). User review required.", None

        # 3. Duplicate check (within last 60 seconds)
        msg_hash = self.calculate_message_hash(req)
        last_sent = self._recent_hashes.get(msg_hash)
        if last_sent and (time.time() - last_sent) < 60:
            return False, "Duplicate message detected: identical message was recently sent.", None

        # 4. Create Tier 2 Confirmation
        conf_req = confirmation_system.create_request(
            tool_name="send_message",
            action_summary=f"Send message to {req.recipient} via {req.provider.value}",
            affected_resource=f"{req.provider.value}:{req.recipient}",
            risk_level="MEDIUM",
            parameters={
                "provider": req.provider.value,
                "conversation_id": req.conversation_id,
                "recipient": req.recipient,
                "text": req.text,
                "message_hash": msg_hash
            }
        )
        return True, "Confirmation required", conf_req.id

    def verify_and_record_send(self, req: SendMessageRequest, expected_hash: str) -> bool:
        current_hash = self.calculate_message_hash(req)
        if current_hash != expected_hash:
            audit_logger.log_event(
                event_type="BLOCKED_ACTION",
                action="send_message",
                resource=req.recipient,
                decision="BLOCKED",
                reason="Message content changed after approval (approval invalidated)."
            )
            raise ValueError("Approval invalid: Message content changed after approval was granted.")

        self._session_send_count += 1
        self._recent_hashes[current_hash] = time.time()

        audit_logger.log_event(
            event_type="COMMUNICATION_MESSAGE_SENT",
            action="send_message",
            resource=f"{req.provider.value}:{req.recipient}",
            decision="ALLOWED",
            reason=f"Sent message to {req.recipient} (hash: {current_hash[:8]})"
        )
        return True

send_service = SendService()
