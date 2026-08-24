from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class ProviderType(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    EMAIL = "email"
    MOCK = "mock"

class ProviderCapability(str, Enum):
    READ_MESSAGES = "READ_MESSAGES"
    READ_CONVERSATIONS = "READ_CONVERSATIONS"
    SEARCH_MESSAGES = "SEARCH_MESSAGES"
    READ_NOTIFICATIONS = "READ_NOTIFICATIONS"
    DRAFT_MESSAGES = "DRAFT_MESSAGES"
    SEND_MESSAGES = "SEND_MESSAGES"
    REPLY_MESSAGES = "REPLY_MESSAGES"
    MARK_READ = "MARK_READ"

class CommunicationPrivacyMode(str, Enum):
    PRIVATE = "PRIVATE"
    LOCAL_ONLY = "LOCAL_ONLY"
    CLOUD_ALLOWED = "CLOUD_ALLOWED"
    PAUSED = "PAUSED"

class MessageDirection(str, Enum):
    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"

class MessagePriority(str, Enum):
    URGENT = "URGENT"
    IMPORTANT = "IMPORTANT"
    NORMAL = "NORMAL"
    LOW_VALUE = "LOW_VALUE"
    NOISE = "NOISE"

class CommunicationMessage(BaseModel):
    id: str
    provider: ProviderType
    conversation_id: str
    sender: str
    recipient: str
    text: str
    timestamp: datetime
    is_read: bool = False
    direction: MessageDirection = MessageDirection.INCOMING
    priority: MessagePriority = MessagePriority.NORMAL
    sensitivity: str = "PRIVATE"

class CommunicationConversation(BaseModel):
    id: str
    provider: ProviderType
    title: str
    participants: List[str] = Field(default_factory=list)
    last_message_at: datetime
    unread_count: int = 0
    is_muted: bool = False
    is_archived: bool = False
    recent_messages: List[CommunicationMessage] = Field(default_factory=list)

class CommunicationNotification(BaseModel):
    id: str
    provider: ProviderType
    title: str
    body: str
    timestamp: datetime
    priority: MessagePriority = MessagePriority.NORMAL
    is_read: bool = False

class CommunicationProviderStatus(BaseModel):
    provider: ProviderType
    connected: bool
    status: str  # CONNECTED, DISCONNECTED, AUTH_REQUIRED, READ_ONLY, SEND_DISABLED
    can_read: bool = True
    can_send: bool = False
    can_search: bool = True
    capabilities: List[ProviderCapability] = Field(default_factory=list)

class ReplyOption(BaseModel):
    style: str  # Professional, Friendly, Concise, Detailed
    reply_text: str

class ReplySuggestionResponse(BaseModel):
    conversation_id: str
    options: List[ReplyOption] = Field(default_factory=list)

class ConversationSummaryResponse(BaseModel):
    conversation_id: str
    summary: str
    important_points: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    confidence: str = "HIGH"

class SendMessageRequest(BaseModel):
    provider: ProviderType
    conversation_id: str
    recipient: str
    text: str
    reply_to_id: Optional[str] = None

class SendMessageResponse(BaseModel):
    id: str
    provider: ProviderType
    conversation_id: str
    recipient: str
    status: str  # SENT, FAILED, CONFIRMATION_REQUIRED
    message_hash: str
    timestamp: datetime = Field(default_factory=utc_now)

class SendApprovalRequest(BaseModel):
    confirmation_id: str
    approved: bool
    rejection_reason: Optional[str] = None
