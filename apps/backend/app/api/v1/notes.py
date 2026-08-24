from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.notes_service import NotesService
from app.schemas.notes import NoteCreate, NoteUpdate, NoteResponse

router = APIRouter(prefix="/notes", tags=["Notes"])

@router.get("", response_model=List[NoteResponse])
def list_notes(query: Optional[str] = None, tag: Optional[str] = None, db: Session = Depends(get_db)):
    service = NotesService(db)
    return service.list_notes(query=query, tag=tag)

@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(req: NoteCreate, db: Session = Depends(get_db)):
    service = NotesService(db)
    try:
        note_obj = service.create_note(title=req.title, content=req.content, tags=req.tags)
        full_note = service.get_note(note_obj.id)
        return full_note
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{note_id}", response_model=NoteResponse)
def get_note(note_id: str, db: Session = Depends(get_db)):
    service = NotesService(db)
    note = service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note

@router.patch("/{note_id}", response_model=NoteResponse)
def update_note(note_id: str, req: NoteUpdate, db: Session = Depends(get_db)):
    service = NotesService(db)
    try:
        updated = service.update_note(note_id, title=req.title, content=req.content, tags=req.tags)
        if not updated:
            raise HTTPException(status_code=404, detail="Note not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: str, db: Session = Depends(get_db)):
    service = NotesService(db)
    success = service.delete_note(note_id)
    if not success:
        raise HTTPException(status_code=404, detail="Note not found")
    return None
