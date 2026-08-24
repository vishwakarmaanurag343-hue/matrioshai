from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.conversation_service import ConversationService
from app.schemas.conversation import (
    ConversationCreate, ConversationUpdate, ConversationResponse, MessageCreate, MessageResponse
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])

@router.get("", response_model=List[ConversationResponse])
def list_conversations(include_archived: bool = False, db: Session = Depends(get_db)):
    service = ConversationService(db)
    return service.list_conversations(include_archived=include_archived)

@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(req: ConversationCreate, db: Session = Depends(get_db)):
    service = ConversationService(db)
    return service.create_conversation(title=req.title)

@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    service = ConversationService(db)
    conv = service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(conversation_id: str, req: ConversationUpdate, db: Session = Depends(get_db)):
    service = ConversationService(db)
    conv = service.update_conversation(conversation_id, title=req.title, archived=req.archived)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    service = ConversationService(db)
    success = service.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return None

@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def get_messages(conversation_id: str, db: Session = Depends(get_db)):
    service = ConversationService(db)
    conv = service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv.messages

@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def add_message(conversation_id: str, req: MessageCreate, db: Session = Depends(get_db)):
    service = ConversationService(db)
    try:
        return service.add_message(
            conversation_id=conversation_id,
            role=req.role,
            content=req.content,
            model=req.model,
            metadata=None
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
