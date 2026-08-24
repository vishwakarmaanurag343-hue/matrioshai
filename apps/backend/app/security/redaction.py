import re
from typing import Dict, List, Tuple, Any
from app.security.classification import DataClassification

class RedactionEngine:
    """
    Local PII and Sensitive Data Redaction Engine.
    Detects and masks sensitive identifiers (emails, phone numbers, API keys, credentials, IP addresses, credit cards).
    """

    PATTERNS = {
        "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "PHONE": r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        "API_KEY": r'(?i)\b(?:api[_-]?key|secret|token|bearer|auth[_-]?token)[\s:=]+([A-Za-z0-9_\-]{16,})\b',
        "CREDIT_CARD": r'\b(?:\d{4}[- ]?){3}\d{4}\b',
        "IP_ADDRESS": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "SSH_KEY": r'-----BEGIN [A-Z]+ PRIVATE KEY-----[^-]+-----END [A-Z]+ PRIVATE KEY-----',
    }

    def detect_entities(self, text: str) -> List[Dict[str, Any]]:
        """Detect all sensitive entities in the text."""
        findings = []
        for entity_type, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, text):
                findings.append({
                    "entity_type": entity_type,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(0),
                    "classification": DataClassification.SECRET if entity_type in ("API_KEY", "SSH_KEY") else DataClassification.SENSITIVE
                })
        return findings

    def redact(self, text: str, preserve_types: List[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Redact detected sensitive entities with clean replacement tags like [REDACTED_EMAIL].
        Returns the sanitized text and a list of redaction event records.
        """
        preserve = preserve_types or []
        findings = self.detect_entities(text)
        if not findings:
            return text, []

        # Sort findings in reverse order to replace without invalidating character offsets
        sorted_findings = sorted(findings, key=lambda x: x["start"], reverse=True)
        sanitized = text
        applied_redactions = []

        for item in sorted_findings:
            if item["entity_type"] in preserve:
                continue
            
            tag = f"[REDACTED_{item['entity_type']}]"
            sanitized = sanitized[:item["start"]] + tag + sanitized[item["end"]:]
            applied_redactions.append({
                "entity_type": item["entity_type"],
                "tag": tag,
                "classification": item["classification"]
            })

        return sanitized, applied_redactions

redaction_engine = RedactionEngine()
