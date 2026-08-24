from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class EntityType(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    PROJECT = "PROJECT"
    PRODUCT = "PRODUCT"
    TECHNOLOGY = "TECHNOLOGY"
    DOCUMENT = "DOCUMENT"
    CONVERSATION = "CONVERSATION"
    DECISION = "DECISION"
    TASK = "TASK"
    GOAL = "GOAL"
    EVENT = "EVENT"

class RelationshipType(str, Enum):
    WORKS_WITH = "WORKS_WITH"
    OWNS = "OWNS"
    MANAGES = "MANAGES"
    PART_OF = "PART_OF"
    DEPENDS_ON = "DEPENDS_ON"
    RELATED_TO = "RELATED_TO"
    DECIDED_BY = "DECIDED_BY"
    MENTIONED_IN = "MENTIONED_IN"
    CREATED_BY = "CREATED_BY"
    USES = "USES"
    BLOCKS = "BLOCKS"
    SUPPORTS = "SUPPORTS"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    ASSIGNED_TO = "ASSIGNED_TO"
    DEADLINE_FOR = "DEADLINE_FOR"

class GraphEntity(BaseModel):
    id: str
    name: str
    entity_type: EntityType
    canonical_name: str
    aliases: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    provenance: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

class GraphRelationship(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    confidence: float = 1.0
    provenance: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

class KnowledgeGraphResponse(BaseModel):
    entities: List[GraphEntity] = Field(default_factory=list)
    relationships: List[GraphRelationship] = Field(default_factory=list)
