from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from app.communication.models import (
    CommunicationProviderStatus, CommunicationConversation, CommunicationMessage,
    CommunicationNotification, SendMessageRequest, SendMessageResponse,
    SendApprovalRequest, ReplySuggestionResponse, ConversationSummaryResponse
)
from app.communication.service import communication_service
from app.communication.reply import reply_service
from app.communication.summarization import summarization_service

router = APIRouter(prefix="/communication", tags=["Communication Intelligence"])

@router.get("/providers", response_model=List[CommunicationProviderStatus])
def get_providers():
    return communication_service.get_providers_status()

@router.get("/conversations", response_model=List[CommunicationConversation])
def list_conversations():
    return communication_service.list_all_conversations()

@router.get("/conversations/{conversation_id}", response_model=CommunicationConversation)
def get_conversation(conversation_id: str):
    conv = communication_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.get("/unread", response_model=List[CommunicationMessage])
def get_unread_messages():
    return communication_service.get_all_unread()

@router.get("/notifications", response_model=List[CommunicationNotification])
def get_notifications():
    return communication_service.get_all_notifications()

@router.post("/search", response_model=List[CommunicationMessage])
def search_messages(query: str):
    return communication_service.search_all_messages(query)

@router.post("/summarize/{conversation_id}", response_model=ConversationSummaryResponse)
async def summarize_conversation(conversation_id: str):
    conv = communication_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await summarization_service.summarize_conversation(conv)

@router.post("/reply/{conversation_id}", response_model=ReplySuggestionResponse)
async def generate_replies(conversation_id: str):
    conv = communication_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await reply_service.generate_replies(conv)

@router.post("/send", response_model=SendMessageResponse)
def request_send_message(req: SendMessageRequest):
    try:
        return communication_service.request_send_message(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/approve", response_model=SendMessageResponse)
def approve_send_message(approval_req: SendApprovalRequest, send_req: SendMessageRequest):
    try:
        return communication_service.execute_approved_send(approval_req, send_req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/stop", response_model=dict)
def emergency_stop():
    communication_service.emergency_stop()
    return {"status": "EMERGENCY_STOPPED"}
