from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class MessageCreate(BaseModel):
    role: str = Field(..., description="Role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text content")
    model: Optional[str] = None
    metadata_json: Optional[str] = None

class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    model: Optional[str] = None
    metadata_json: Optional[str] = None

class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"

class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    archived: Optional[bool] = None

class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    archived: bool
    messages: List[MessageResponse] = []

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    prompt: str = Field(..., min_length=1)
    stream: bool = False
