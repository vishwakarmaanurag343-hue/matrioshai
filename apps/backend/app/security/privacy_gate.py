from typing import Dict, Any, List, Optional
from app.security.classification import DataClassification, DestinationType, DEFAULT_POLICY_MATRIX
from app.security.redaction import redaction_engine
from app.security.audit import audit_logger
from app.security.threat_defense import threat_defense
from app.security.permissions import tool_registry, ToolRequest, PermissionDecision

class PrivacyGatekeeper:
    """
    Central Privacy & Context Gatekeeper.
    Evaluates context, performs PII/sensitive data redaction, enforces cloud vs local policies,
    and logs all privacy decisions into the security audit trail.
    """

    def __init__(self, default_destination: DestinationType = DestinationType.LOCAL):
        self.destination = default_destination

    def evaluate_and_sanitize(
        self,
        text: str,
        classification: DataClassification = DataClassification.PRIVATE,
        destination: Optional[DestinationType] = None,
        source_label: str = "context"
    ) -> Dict[str, Any]:
        target_dest = destination or self.destination
        policy_allowed = DEFAULT_POLICY_MATRIX[target_dest].get(classification, False)

        # 1. Scan for adversarial injection patterns
        threat_check = threat_defense.scan_content(text, source_label=source_label)

        # 2. Check for secrets/credentials (never allowed to leave as raw text)
        sanitized_text, redactions = redaction_engine.redact(text)

        # If sending to cloud and classification is SENSITIVE or PRIVATE, redaction is enforced
        is_redacted = len(redactions) > 0
        if target_dest == DestinationType.CLOUD and not policy_allowed:
            sanitized_text, redactions = redaction_engine.redact(text)
            is_redacted = True

        decision = "REDACTED" if is_redacted else "ALLOWED"
        reason = f"Evaluated for {target_dest.value} dispatch with classification {classification.value}"
        if is_redacted:
            reason += f" ({len(redactions)} PII/secret entities masked)"

        audit_logger.log_event(
            event_type="PRIVACY_EVALUATION",
            action="evaluate_context",
            resource=source_label,
            decision=decision,
            reason=reason,
            metadata={"destination": target_dest.value, "redaction_count": len(redactions)}
        )

        return {
            "sanitized_text": sanitized_text,
            "decision": decision,
            "redactions": redactions,
            "has_threats": threat_check["has_threats"],
            "destination": target_dest.value
        }

    def evaluate_tool_request(self, request: ToolRequest) -> PermissionDecision:
        """Evaluate permission and autonomy rules for a tool execution request."""
        return tool_registry.evaluate_request(request)

privacy_gatekeeper = PrivacyGatekeeper()
