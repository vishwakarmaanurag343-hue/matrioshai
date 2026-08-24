import json
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.db_models import MemoryItem
from app.schemas.memory import MemoryItemCreate, MemoryItemUpdate
from app.memory.base_embedding import EmbeddingProvider
from app.memory.local_embedding import LocalEmbeddingProvider
from app.core.logging import logger

class MemoryService:
    def __init__(self, db: Session, embedding_provider: Optional[EmbeddingProvider] = None):
        self.db = db
        self.embedding_provider = embedding_provider or LocalEmbeddingProvider()

    def add_memory(
        self,
        content: str,
        memory_tier: str = "RECALL",
        source_type: str = "user_fact",
        source_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryItem:
        tier_upper = memory_tier.upper()
        if tier_upper not in ("CORE", "RECALL", "ARCHIVAL"):
            raise ValueError(f"Invalid memory tier '{memory_tier}'. Must be CORE, RECALL, or ARCHIVAL.")

        meta_json = json.dumps(metadata) if metadata else None
        item = MemoryItem(
            content=content.strip(),
            memory_tier=tier_upper,
            source_type=source_type,
            source_id=source_id,
            metadata_json=meta_json
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        logger.info(f"Added memory item [{item.id}] in tier {tier_upper}")
        return item

    def get_memory_by_id(self, memory_id: str) -> Optional[MemoryItem]:
        return self.db.query(MemoryItem).filter(MemoryItem.id == memory_id).first()

    def get_core_memory(self) -> List[MemoryItem]:
        """Retrieve all CORE memory facts."""
        return self.db.query(MemoryItem).filter(MemoryItem.memory_tier == "CORE").all()

    def set_core_memory(self, user_preferences: Optional[str], active_goals: Optional[str], important_facts: Optional[str]) -> List[MemoryItem]:
        """Convenience method to set or update core memory entries."""
        results = []
        mapping = {
            "user_preferences": user_preferences,
            "active_goals": active_goals,
            "important_facts": important_facts
        }
        for key, val in mapping.items():
            if val is not None:
                existing = (
                    self.db.query(MemoryItem)
                    .filter(MemoryItem.memory_tier == "CORE", MemoryItem.source_type == key)
                    .first()
                )
                if existing:
                    existing.content = val
                    self.db.commit()
                    self.db.refresh(existing)
                    results.append(existing)
                else:
                    new_item = self.add_memory(
                        content=val,
                        memory_tier="CORE",
                        source_type=key
                    )
                    results.append(new_item)
        return results

    def search_memory(self, query: str, tier: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search memory items using SQLite keyword search combined with vector similarity preparation.
        """
        q = self.db.query(MemoryItem)
        if tier:
            q = q.filter(MemoryItem.memory_tier == tier.upper())
        
        # Keyword filter
        query_terms = [t for t in query.lower().split() if len(t) > 2]
        all_items = q.all()

        scored_items = []
        query_vector = self.embedding_provider.embed(query)

        for item in all_items:
            content_lower = item.content.lower()
            keyword_score = sum(1.0 for term in query_terms if term in content_lower)
            
            # Simple vector similarity score calculation
            item_vector = self.embedding_provider.embed(item.content)
            dot_product = sum(a * b for a, b in zip(query_vector, item_vector))
            vector_score = round(max(0.0, dot_product / len(query_vector)), 4)
            
            total_score = keyword_score + (vector_score * 0.5)
            if query_terms and keyword_score == 0 and vector_score < 0.2:
                continue

            metadata = json.loads(item.metadata_json) if item.metadata_json else {}
            scored_items.append({
                "id": item.id,
                "content": item.content,
                "memory_tier": item.memory_tier,
                "source_type": item.source_type,
                "source_id": item.source_id,
                "relevance_score": round(total_score, 4),
                "created_at": item.created_at,
                "metadata": metadata
            })

        scored_items.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored_items[:limit]

    def update_memory(self, memory_id: str, content: Optional[str] = None, memory_tier: Optional[str] = None) -> Optional[MemoryItem]:
        item = self.get_memory_by_id(memory_id)
        if not item:
            return None
        if content:
            item.content = content.strip()
        if memory_tier:
            tier_upper = memory_tier.upper()
            if tier_upper in ("CORE", "RECALL", "ARCHIVAL"):
                item.memory_tier = tier_upper
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_memory(self, memory_id: str) -> bool:
        item = self.get_memory_by_id(memory_id)
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True
