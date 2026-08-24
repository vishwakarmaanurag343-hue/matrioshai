from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., description="Markdown note text content")
    tags: List[str] = Field(default_factory=list)

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None

class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_path: str
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    source: str
    tags: List[str] = []
