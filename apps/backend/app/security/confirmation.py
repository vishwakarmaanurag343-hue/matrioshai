import uuid
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.security.audit import audit_logger

def utc_now():
    return datetime.now(timezone.utc)

class ConfirmationRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str
    action_summary: str
    affected_resource: str
    risk_level: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    parameters_hash: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    approved: Optional[bool] = None

class ConfirmationSystem:
    """Manages pending confirmation requests for Tier 2 operations."""

    def __init__(self):
        self._pending_requests: Dict[str, ConfirmationRequest] = {}
        self._resolved_requests: set = set()

    @staticmethod
    def _compute_hash(params: Dict[str, Any]) -> str:
        serialized = json.dumps(params, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def create_request(
        self,
        tool_name: str,
        action_summary: str,
        affected_resource: str,
        risk_level: str,
        parameters: Dict[str, Any]
    ) -> ConfirmationRequest:
        param_hash = self._compute_hash(parameters)
        req = ConfirmationRequest(
            tool_name=tool_name,
            action_summary=action_summary,
            affected_resource=affected_resource,
            risk_level=risk_level,
            parameters=parameters,
            parameters_hash=param_hash
        )
        self._pending_requests[req.id] = req
        audit_logger.log_event(
            event_type="TOOL_CONFIRMATION",
            action=f"request_approval:{tool_name}",
            resource=affected_resource,
            decision="CONFIRMATION_REQUIRED",
            reason=f"Action requires user approval: {action_summary}"
        )
        return req

    def resolve_request(
        self,
        request_id: str,
        approved: bool,
        verified_parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[ConfirmationRequest]:
        if request_id in self._resolved_requests:
            audit_logger.log_event(
                event_type="BLOCKED_ACTION",
                action="resolve_approval",
                resource=request_id,
                decision="BLOCKED",
                reason="Replay attack detected: approval request was already resolved."
            )
            raise ValueError("Security error: Replay attempt detected. Request already resolved.")

        req = self._pending_requests.get(request_id)
        if not req:
            return None

        # Verify parameter integrity against tampering
        if verified_parameters is not None:
            current_hash = self._compute_hash(verified_parameters)
            if current_hash != req.parameters_hash:
                audit_logger.log_event(
                    event_type="BLOCKED_ACTION",
                    action=f"tamper_detected:{req.tool_name}",
                    resource=req.affected_resource,
                    decision="BLOCKED",
                    reason="Parameter tampering detected during approval resolution"
                )
                raise ValueError("Security error: Action parameters were modified after approval was requested.")

        req.approved = approved
        self._resolved_requests.add(request_id)
        decision_str = "ALLOWED" if approved else "REJECTED"
        audit_logger.log_event(
            event_type="TOOL_CONFIRMATION",
            action=f"resolve_approval:{req.tool_name}",
            resource=req.affected_resource,
            decision=decision_str,
            reason=f"User {'approved' if approved else 'denied'} tool action"
        )
        del self._pending_requests[request_id]
        return req

    def list_pending(self) -> list[ConfirmationRequest]:
        return list(self._pending_requests.values())

confirmation_system = ConfirmationSystem()
