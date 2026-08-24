from typing import List, Optional
from fastapi import APIRouter, HTTPException
from app.knowledge.models import KnowledgeGraphResponse, GraphEntity, EntityType, RelationshipType
from app.knowledge.service import knowledge_graph_service

router = APIRouter(prefix="/knowledge", tags=["Knowledge Graph"])

@router.get("/graph", response_model=KnowledgeGraphResponse)
def get_graph():
    return knowledge_graph_service.get_graph()

@router.get("/search", response_model=List[GraphEntity])
def search_entities(query: str):
    return knowledge_graph_service.search_entities(query)
