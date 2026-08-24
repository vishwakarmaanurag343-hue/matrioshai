from typing import Dict, List, Optional
from app.communication.models import (
    ProviderType, CommunicationProviderStatus, CommunicationConversation,
    CommunicationMessage, CommunicationNotification, CommunicationPrivacyMode,
    SendMessageRequest, SendMessageResponse, SendApprovalRequest, utc_now
)
from app.communication.providers.base import BaseCommunicationProvider
from app.communication.providers.mock import MockCommunicationProvider
from app.communication.reply import reply_service
from app.communication.summarization import summarization_service
from app.communication.send import send_service
from app.security.confirmation import confirmation_system
from app.security.audit import audit_logger
from app.core.logging import logger

class CommunicationService:
    """
    Unified Communication Orchestrator.
    Manages providers (WhatsApp, Telegram, Email), Unified Inbox, Search, and Sending.
    """

    def __init__(self):
        self._providers: Dict[ProviderType, BaseCommunicationProvider] = {
            ProviderType.WHATSAPP: MockCommunicationProvider(ProviderType.WHATSAPP),
            ProviderType.TELEGRAM: MockCommunicationProvider(ProviderType.TELEGRAM),
            ProviderType.EMAIL: MockCommunicationProvider(ProviderType.EMAIL),
        }
        self.privacy_mode = CommunicationPrivacyMode.PRIVATE
        self.emergency_stopped = False

    def get_providers_status(self) -> List[CommunicationProviderStatus]:
        return [p.get_status() for p in self._providers.values()]

    def list_all_conversations(self) -> List[CommunicationConversation]:
        convs = []
        for p in self._providers.values():
            convs.extend(p.list_conversations())
        convs.sort(key=lambda c: c.last_message_at, reverse=True)
        return convs

    def get_conversation(self, conv_id: str) -> Optional[CommunicationConversation]:
        for p in self._providers.values():
            c = p.get_conversation(conv_id)
            if c:
                return c
        return None

    def search_all_messages(self, query: str) -> List[CommunicationMessage]:
        results = []
        for p in self._providers.values():
            results.extend(p.search_messages(query))
        return results

    def get_all_unread(self) -> List[CommunicationMessage]:
        unreads = []
        for p in self._providers.values():
            unreads.extend(p.get_unread())
        return unreads

    def get_all_notifications(self) -> List[CommunicationNotification]:
        notifs = []
        for p in self._providers.values():
            notifs.extend(p.get_notifications())
        return notifs

    def request_send_message(self, req: SendMessageRequest) -> SendMessageResponse:
        if self.emergency_stopped:
            raise PermissionError("Communication is EMERGENCY STOPPED.")

        ok, msg, conf_id = send_service.prepare_send_request(req)
        if not ok:
            raise ValueError(msg)

        msg_hash = send_service.calculate_message_hash(req)
        return SendMessageResponse(
            id=conf_id or "msg_pending",
            provider=req.provider,
            conversation_id=req.conversation_id,
            recipient=req.recipient,
            status="CONFIRMATION_REQUIRED",
            message_hash=msg_hash
        )

    def execute_approved_send(self, req: SendApprovalRequest, send_req: SendMessageRequest) -> SendMessageResponse:
        if self.emergency_stopped:
            raise PermissionError("Communication is EMERGENCY STOPPED.")

        if not req.approved:
            confirmation_system.resolve_request(req.confirmation_id, approved=False)
            return SendMessageResponse(
                id=req.confirmation_id,
                provider=send_req.provider,
                conversation_id=send_req.conversation_id,
                recipient=send_req.recipient,
                status="REJECTED",
                message_hash=send_service.calculate_message_hash(send_req)
            )

        # 1. Resolve confirmation
        conf = confirmation_system.resolve_request(req.confirmation_id, approved=True)
        expected_hash = conf.parameters.get("message_hash", "")

        # 2. Verify hash and record send
        send_service.verify_and_record_send(send_req, expected_hash)

        # 3. Provider dispatch
        provider = self._providers.get(send_req.provider)
        if not provider:
            raise ValueError(f"Unknown provider {send_req.provider}")

        provider.send_message(send_req.conversation_id, send_req.recipient, send_req.text)

        return SendMessageResponse(
            id=req.confirmation_id,
            provider=send_req.provider,
            conversation_id=send_req.conversation_id,
            recipient=send_req.recipient,
            status="SENT",
            message_hash=expected_hash
        )

    def emergency_stop(self):
        logger.warning("EMERGENCY STOP TRIGGERED: Communication sends halted.")
        self.emergency_stopped = True
        send_service.set_enabled(False)
        audit_logger.log_event(
            event_type="EMERGENCY_STOP",
            action="stop_communication",
            decision="ALLOWED",
            reason="User triggered emergency stop for communication"
        )

communication_service = CommunicationService()
