from typing import Dict, Any
from app.security.redaction import redaction_engine
from app.security.threat_defense import threat_defense
from app.security.audit import audit_logger

class ObservationPipeline:
    """
    Sanitizes and fences tool execution outputs:
    - Redacts sensitive PII / API keys / tokens.
    - Scans for prompt injection attacks.
    - Demarcates untrusted context.
    """

    @classmethod
    def process_observation(cls, tool_name: str, raw_result: Any) -> str:
        if raw_result is None:
            return "[NO OUTPUT]"

        raw_str = str(raw_result)
        
        # 1. Redact secrets
        sanitized_str, redaction_count = redaction_engine.redact(raw_str)

        # 2. Threat defense check for malicious payloads in tool output
        threat_scan = threat_defense.scan_content(sanitized_str, source_label=f"tool_output:{tool_name}")
        if threat_scan["has_threats"]:
            audit_logger.log_event(
                event_type="OBSERVATION_RECORDED",
                action="process_observation",
                resource=tool_name,
                decision="THREAT_FLAGGED",
                reason=f"Threat detected in observation: {', '.join(threat_scan['threats'])}"
            )
            # Neutralize instruction overrides
            sanitized_str = f"[FLAGGED UNTRUSTED CONTENT: {', '.join(threat_scan['threats'])}]\n" + sanitized_str

        audit_logger.log_event(
            event_type="OBSERVATION_RECORDED",
            action="process_observation",
            resource=tool_name,
            decision="ALLOWED",
            reason=f"Observation recorded ({len(sanitized_str)} chars)"
        )

        return sanitized_str

observation_pipeline = ObservationPipeline()
