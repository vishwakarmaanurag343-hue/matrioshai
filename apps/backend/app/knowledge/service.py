import uuid
from typing import Dict, List, Optional
from app.knowledge.models import GraphEntity, GraphRelationship, EntityType, RelationshipType, KnowledgeGraphResponse, utc_now
from app.security.redaction import redaction_engine
from app.security.audit import audit_logger

class KnowledgeGraphService:
    """
    In-memory / SQLite Graph engine for managing entities and typed relationships.
    Redacts secrets prior to ingestion.
    """

    def __init__(self):
        self._entities: Dict[str, GraphEntity] = {}
        self._relationships: Dict[str, GraphRelationship] = {}

        # Default foundational nodes
        self.add_entity("MATRIOSHAI", EntityType.PRODUCT, canonical_name="MATRIOSHAI")
        self.add_entity("FastAPI", EntityType.TECHNOLOGY, canonical_name="FastAPI")
        self.add_entity("React", EntityType.TECHNOLOGY, canonical_name="React")
        self.add_entity("5C Executive System", EntityType.PRODUCT, canonical_name="5C Executive")
        
        # Link default relationships
        self.add_relationship("MATRIOSHAI", "FastAPI", RelationshipType.USES)
        self.add_relationship("MATRIOSHAI", "React", RelationshipType.USES)
        self.add_relationship("MATRIOSHAI", "5C Executive System", RelationshipType.PART_OF)

    def add_entity(self, name: str, entity_type: EntityType, canonical_name: Optional[str] = None, provenance: Optional[str] = None) -> GraphEntity:
        sanitized_name, _ = redaction_engine.redact(name)
        c_name = canonical_name or sanitized_name

        # Check existing by canonical name
        for e in self._entities.values():
            if e.canonical_name.lower() == c_name.lower():
                if sanitized_name not in e.aliases:
                    e.aliases.append(sanitized_name)
                return e

        ent = GraphEntity(
            id=str(uuid.uuid4()),
            name=sanitized_name,
            entity_type=entity_type,
            canonical_name=c_name,
            aliases=[sanitized_name],
            provenance=provenance,
            created_at=utc_now()
        )
        self._entities[ent.id] = ent
        audit_logger.log_event(
            event_type="GRAPH_ENTITY_CREATED",
            action="add_entity",
            resource=f"{ent.entity_type.value}:{ent.canonical_name}",
            decision="ALLOWED"
        )
        return ent

    def add_relationship(self, source_name_or_id: str, target_name_or_id: str, rel_type: RelationshipType, provenance: Optional[str] = None) -> Optional[GraphRelationship]:
        src_id = None
        tgt_id = None

        for e in self._entities.values():
            if e.id == source_name_or_id or e.name.lower() == source_name_or_id.lower() or e.canonical_name.lower() == source_name_or_id.lower():
                src_id = e.id
            if e.id == target_name_or_id or e.name.lower() == target_name_or_id.lower() or e.canonical_name.lower() == target_name_or_id.lower():
                tgt_id = e.id

        if not src_id or not tgt_id:
            return None

        rel = GraphRelationship(
            id=str(uuid.uuid4()),
            source_entity_id=src_id,
            target_entity_id=tgt_id,
            relationship_type=rel_type,
            provenance=provenance,
            created_at=utc_now()
        )
        self._relationships[rel.id] = rel
        audit_logger.log_event(
            event_type="GRAPH_RELATIONSHIP_CREATED",
            action="add_relationship",
            resource=f"{src_id}->{rel_type.value}->{tgt_id}",
            decision="ALLOWED"
        )
        return rel

    def get_graph(self) -> KnowledgeGraphResponse:
        return KnowledgeGraphResponse(
            entities=list(self._entities.values()),
            relationships=list(self._relationships.values())
        )

    def search_entities(self, query: str) -> List[GraphEntity]:
        res = []
        q = query.lower()
        for e in self._entities.values():
            if q in e.name.lower() or q in e.canonical_name.lower() or any(q in a.lower() for a in e.aliases):
                res.append(e)
        return res

knowledge_graph_service = KnowledgeGraphService()
