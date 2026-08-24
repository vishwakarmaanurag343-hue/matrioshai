from typing import Tuple
from app.communication.models import CommunicationMessage, CommunicationNotification
from app.security.redaction import redaction_engine
from app.security.threat_defense import threat_defense
from app.security.audit import audit_logger

class CommunicationPrivacyGate:
    """
    Sanitizes and fences incoming/outgoing communication:
    - Wraps text in [UNTRUSTED COMMUNICATION CONTENT]
    - Redacts sensitive credentials
    - Scans for prompt injection attacks
    """

    @classmethod
    def sanitize_message_content(cls, raw_text: str, source_label: str = "communication_message") -> Tuple[str, bool]:
        # 1. Redact secrets
        sanitized_text, redactions = redaction_engine.redact(raw_text)

        # 2. Check for threat/prompt injection
        threat_scan = threat_defense.scan_content(sanitized_text, source_label=source_label)
        has_threat = threat_scan["has_threats"]

        fenced_text = f"[UNTRUSTED COMMUNICATION CONTENT]\n{sanitized_text}\n[END UNTRUSTED COMMUNICATION CONTENT]"
        if has_threat:
            audit_logger.log_event(
                event_type="THREAT_FLAGGED",
                action="sanitize_message",
                resource=source_label,
                decision="TAGGED_UNTRUSTED",
                reason=f"Detected potential prompt injection in message: {', '.join(threat_scan['threats'])}"
            )

        return fenced_text, (len(redactions) > 0 or has_threat)

communication_privacy = CommunicationPrivacyGate()
