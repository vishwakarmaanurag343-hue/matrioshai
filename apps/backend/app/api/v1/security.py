from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.security.privacy_gate import privacy_gatekeeper
from app.security.audit import audit_logger
from app.security.permissions import tool_registry, ToolDefinition, ToolRequest, PermissionDecision
from app.security.confirmation import confirmation_system, ConfirmationRequest
from app.security.secrets import secret_store
from app.security.classification import DataClassification, DestinationType

router = APIRouter(prefix="/security", tags=["Security"])

class EvaluateContextRequest(BaseModel):
    text: str = Field(..., min_length=1)
    classification: DataClassification = DataClassification.PRIVATE
    destination: DestinationType = DestinationType.LOCAL
    source_label: str = "manual_eval"

class ConfirmActionRequest(BaseModel):
    approved: bool

class SecretSetRequest(BaseModel):
    key: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)

@router.post("/evaluate-context")
def evaluate_context(req: EvaluateContextRequest):
    return privacy_gatekeeper.evaluate_and_sanitize(
        text=req.text,
        classification=req.classification,
        destination=req.destination,
        source_label=req.source_label
    )

@router.get("/audit-log")
def get_audit_logs(limit: int = 50):
    events = audit_logger.get_recent_events(limit=limit)
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "event_type": e.event_type,
            "actor": e.actor,
            "action": e.action,
            "resource": e.resource,
            "decision": e.decision,
            "reason": e.reason,
        }
        for e in events
    ]

@router.get("/tools", response_model=List[ToolDefinition])
def list_registered_tools():
    return tool_registry.list_tools()

@router.post("/tools/evaluate", response_model=PermissionDecision)
def evaluate_tool_request(req: ToolRequest):
    return privacy_gatekeeper.evaluate_tool_request(req)

@router.get("/confirmations", response_model=List[ConfirmationRequest])
def list_pending_confirmations():
    return confirmation_system.list_pending()

@router.post("/confirmations/{request_id}/resolve")
def resolve_confirmation(request_id: str, req: ConfirmActionRequest):
    resolved = confirmation_system.resolve_request(request_id=request_id, approved=req.approved)
    if not resolved:
        raise HTTPException(status_code=404, detail="Pending confirmation request not found")
    return resolved

@router.post("/secrets")
def store_secret(req: SecretSetRequest):
    success = secret_store.set_secret(req.key, req.value)
    return {"key": req.key, "stored": success}

@router.get("/secrets/{key}/status")
def check_secret_status(key: str):
    return {"key": key, "exists": secret_store.has_secret(key)}
