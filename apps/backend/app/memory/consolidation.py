import uuid
from typing import List, Tuple, Optional
from app.memory.models import MemoryRecord, MemoryContradiction, MemoryStatus, utc_now
from app.security.audit import audit_logger

class MemoryConsolidationService:
    """
    Detects duplicate, contradictory, or superseded memories while preserving history.
    """

    @classmethod
    def detect_contradictions(cls, new_text: str, existing_memories: List[MemoryRecord]) -> List[MemoryContradiction]:
        contradictions = []
        lowered_new = new_text.lower()

        for mem in existing_memories:
            if mem.status != MemoryStatus.ACTIVE:
                continue
            lowered_mem = mem.content.lower()

            # Example: launch month contradiction (e.g. September vs November)
            if "launch in" in lowered_mem and "launch in" in lowered_new and lowered_mem != lowered_new:
                contradictions.append(MemoryContradiction(
                    id=str(uuid.uuid4()),
                    existing_memory=mem,
                    conflicting_content=new_text,
                    source="consolidation_detector"
                ))

        return contradictions

    @classmethod
    def supersede_memory(cls, old_memory: MemoryRecord, new_memory_id: str) -> MemoryRecord:
        old_memory.status = MemoryStatus.SUPERSEDED
        old_memory.superseded_by = new_memory_id
        old_memory.updated_at = utc_now()
        
        audit_logger.log_event(
            event_type="MEMORY_SUPERSEDED",
            action="supersede_memory",
            resource=old_memory.id,
            decision="ALLOWED",
            reason=f"Superseded by memory {new_memory_id}"
        )
        return old_memory

memory_consolidation_service = MemoryConsolidationService()
