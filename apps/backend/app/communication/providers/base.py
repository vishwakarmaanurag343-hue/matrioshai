from abc import ABC, abstractmethod
from typing import List, Optional
from app.communication.models import (
    ProviderType, ProviderCapability, CommunicationProviderStatus,
    CommunicationConversation, CommunicationMessage, CommunicationNotification
)

class BaseCommunicationProvider(ABC):
    """
    Abstract communication provider interface.
    Allows WhatsApp, Telegram, Email, and custom integrations to plug in seamlessly.
    """

    def __init__(self, provider_type: ProviderType):
        self.provider_type = provider_type

    @abstractmethod
    def get_status(self) -> CommunicationProviderStatus:
        pass

    @abstractmethod
    def list_conversations(self) -> List[CommunicationConversation]:
        pass

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> Optional[CommunicationConversation]:
        pass

    @abstractmethod
    def get_messages(self, conversation_id: str, limit: int = 50) -> List[CommunicationMessage]:
        pass

    @abstractmethod
    def search_messages(self, query: str) -> List[CommunicationMessage]:
        pass

    @abstractmethod
    def get_unread(self) -> List[CommunicationMessage]:
        pass

    @abstractmethod
    def get_notifications(self) -> List[CommunicationNotification]:
        pass

    @abstractmethod
    def send_message(self, conversation_id: str, recipient: str, text: str) -> bool:
        pass
