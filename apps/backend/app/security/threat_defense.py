import re
from typing import Dict, Any, List
from app.security.audit import audit_logger

class ThreatDefense:
    """
    Prompt Injection and Adversarial Content Detection Engine.
    Detects attempts to override system instructions or exfiltrate private credentials.
    """

    ADVERSARIAL_PATTERNS = [
        (r'(?i)ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions', "Instruction override attempt"),
        (r'(?i)reveal\s+(?:system\s+)?(?:instructions|prompt|keys)', "System prompt exfiltration attempt"),
        (r'(?i)(?:send|exfiltrate|post|upload)\s+.*(?:api[_-]?key|password|secret|token|credentials)', "Credential exfiltration attempt"),
        (r'(?i)read\s+(?:~/\.ssh|/etc/passwd|id_rsa)', "Sensitive filesystem probing attempt"),
        (r'(?i)override\s+(?:the\s+)?(?:security|privacy)\s+policy', "Security policy override attempt"),
        (r'(?i)delete\s+all\s+files', "Destructive payload attempt"),
    ]

    @classmethod
    def scan_content(cls, text: str, source_label: str = "untrusted_input") -> Dict[str, Any]:
        threats_found = []
        for pattern, desc in cls.ADVERSARIAL_PATTERNS:
            if re.search(pattern, text):
                threats_found.append(desc)

        if threats_found:
            audit_logger.log_event(
                event_type="BLOCKED_ACTION",
                action="prompt_injection_detection",
                resource=source_label,
                decision="TAGGED_UNTRUSTED",
                reason=f"Detected potential adversarial instructions: {', '.join(threats_found)}"
            )

        return {
            "has_threats": len(threats_found) > 0,
            "threats": threats_found,
            "source_label": source_label
        }

threat_defense = ThreatDefense()
