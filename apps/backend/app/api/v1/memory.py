from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.memory.memory_service import MemoryService
from app.schemas.memory import (
    MemoryItemCreate, MemoryItemUpdate, MemoryItemResponse, MemorySearchQuery, CoreMemorySetRequest
)

router = APIRouter(prefix="/memory", tags=["Memory"])

@router.post("", response_model=MemoryItemResponse, status_code=status.HTTP_201_CREATED)
def create_memory(req: MemoryItemCreate, db: Session = Depends(get_db)):
    service = MemoryService(db)
    try:
        item = service.add_memory(
            content=req.content,
            memory_tier=req.memory_tier,
            source_type=req.source_type,
            source_id=req.source_id,
            metadata=req.metadata
        )
        return MemoryItemResponse(
            id=item.id,
            source_type=item.source_type,
            source_id=item.source_id,
            content=item.content,
            memory_tier=item.memory_tier,
            created_at=item.created_at,
            updated_at=item.updated_at,
            metadata=req.metadata
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/core", response_model=List[MemoryItemResponse])
def get_core_memory(db: Session = Depends(get_db)):
    service = MemoryService(db)
    items = service.get_core_memory()
    return items

@router.post("/core", response_model=List[MemoryItemResponse])
def set_core_memory(req: CoreMemorySetRequest, db: Session = Depends(get_db)):
    service = MemoryService(db)
    return service.set_core_memory(
        user_preferences=req.user_preferences,
        active_goals=req.active_goals,
        important_facts=req.important_facts
    )

@router.post("/search")
def search_memory(req: MemorySearchQuery, db: Session = Depends(get_db)):
    service = MemoryService(db)
    return service.search_memory(query=req.query, tier=req.tier, limit=req.limit)

@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(memory_id: str, db: Session = Depends(get_db)):
    service = MemoryService(db)
    success = service.delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory item not found")
    return None
