from typing import List, Optional
from datetime import datetime, timezone
from app.communication.models import (
    ProviderType, ProviderCapability, CommunicationProviderStatus,
    CommunicationConversation, CommunicationMessage, CommunicationNotification,
    MessageDirection, MessagePriority, utc_now
)
from app.communication.providers.base import BaseCommunicationProvider

class MockCommunicationProvider(BaseCommunicationProvider):
    """
    Standard mock provider for testing communication workflows (WhatsApp / Telegram / Email mocks).
    """

    def __init__(self, provider_type: ProviderType = ProviderType.MOCK):
        super().__init__(provider_type)
        self._connected = True
        self._can_send = True
        self._conversations = [
            CommunicationConversation(
                id=f"{provider_type.value}_conv_1",
                provider=provider_type,
                title="Client Project Discussion",
                participants=["Alice (Client)", "You"],
                last_message_at=utc_now(),
                unread_count=1,
                recent_messages=[
                    CommunicationMessage(
                        id=f"{provider_type.value}_msg_1",
                        provider=provider_type,
                        conversation_id=f"{provider_type.value}_conv_1",
                        sender="Alice (Client)",
                        recipient="You",
                        text="Can you send the updated architecture proposal by tomorrow?",
                        timestamp=utc_now(),
                        is_read=False,
                        direction=MessageDirection.INCOMING,
                        priority=MessagePriority.IMPORTANT
                    )
                ]
            )
        ]

    def set_send_enabled(self, enabled: bool):
        self._can_send = enabled

    def get_status(self) -> CommunicationProviderStatus:
        return CommunicationProviderStatus(
            provider=self.provider_type,
            connected=self._connected,
            status="CONNECTED" if self._connected else "DISCONNECTED",
            can_read=True,
            can_send=self._can_send,
            can_search=True,
            capabilities=[
                ProviderCapability.READ_MESSAGES,
                ProviderCapability.READ_CONVERSATIONS,
                ProviderCapability.SEARCH_MESSAGES,
                ProviderCapability.DRAFT_MESSAGES,
                ProviderCapability.SEND_MESSAGES,
                ProviderCapability.REPLY_MESSAGES
            ]
        )

    def list_conversations(self) -> List[CommunicationConversation]:
        return self._conversations

    def get_conversation(self, conversation_id: str) -> Optional[CommunicationConversation]:
        for c in self._conversations:
            if c.id == conversation_id:
                return c
        return None

    def get_messages(self, conversation_id: str, limit: int = 50) -> List[CommunicationMessage]:
        conv = self.get_conversation(conversation_id)
        return conv.recent_messages if conv else []

    def search_messages(self, query: str) -> List[CommunicationMessage]:
        res = []
        for c in self._conversations:
            for m in c.recent_messages:
                if query.lower() in m.text.lower():
                    res.append(m)
        return res

    def get_unread(self) -> List[CommunicationMessage]:
        res = []
        for c in self._conversations:
            for m in c.recent_messages:
                if not m.is_read:
                    res.append(m)
        return res

    def get_notifications(self) -> List[CommunicationNotification]:
        return [
            CommunicationNotification(
                id=f"{self.provider_type.value}_notif_1",
                provider=self.provider_type,
                title="New message from Alice",
                body="Can you send the updated architecture proposal by tomorrow?",
                timestamp=utc_now(),
                priority=MessagePriority.IMPORTANT,
                is_read=False
            )
        ]

    def send_message(self, conversation_id: str, recipient: str, text: str) -> bool:
        if not self._can_send:
            raise PermissionError(f"Sending messages is disabled for provider {self.provider_type.value}")

        conv = self.get_conversation(conversation_id)
        if conv:
            msg = CommunicationMessage(
                id=f"{self.provider_type.value}_msg_{len(conv.recent_messages) + 1}",
                provider=self.provider_type,
                conversation_id=conversation_id,
                sender="You",
                recipient=recipient,
                text=text,
                timestamp=utc_now(),
                is_read=True,
                direction=MessageDirection.OUTGOING,
                priority=MessagePriority.NORMAL
            )
            conv.recent_messages.append(msg)
            conv.last_message_at = utc_now()
        return True
