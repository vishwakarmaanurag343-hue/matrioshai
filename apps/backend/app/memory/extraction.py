import uuid
from typing import List, Optional
from app.memory.models import MemoryCandidate, MemoryType, utc_now
from app.security.redaction import redaction_engine
from app.security.threat_defense import threat_defense
from app.security.audit import audit_logger

class MemoryExtractionService:
    """
    Extracts candidate memories from interactions (conversations, notes, decisions).
    Never automatically promotes to CORE without user confirmation.
    """

    @classmethod
    def extract_candidates(cls, text: str, source: str = "conversation") -> List[MemoryCandidate]:
        # 1. Redact secrets
        sanitized_text, redactions = redaction_engine.redact(text)

        # 2. Threat defense
        scan = threat_defense.scan_content(sanitized_text, source_label="memory_extraction")
        if scan["has_threats"]:
            return []

        candidates = []
        lowered = sanitized_text.lower()

        # Rule-based preference/goal detection
        if "i am building" in lowered or "we are building" in lowered:
            candidates.append(MemoryCandidate(
                id=str(uuid.uuid4()),
                proposed_type=MemoryType.SEMANTIC,
                content=sanitized_text.strip(),
                source=source,
                confidence=0.9,
                reason="Detected project statement"
            ))
        elif "i prefer" in lowered or "my goal is" in lowered:
            candidates.append(MemoryCandidate(
                id=str(uuid.uuid4()),
                proposed_type=MemoryType.SEMANTIC,
                content=sanitized_text.strip(),
                source=source,
                confidence=0.85,
                reason="Detected user preference/goal"
            ))

        return candidates

memory_extraction_service = MemoryExtractionService()
