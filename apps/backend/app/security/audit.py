import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Text, DateTime, Index
from app.core.database import Base, SessionLocal
from app.core.logging import logger

def utc_now():
    return datetime.now(timezone.utc)

class SecurityAuditEvent(Base):
    __tablename__ = "security_audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    event_type = Column(String(50), nullable=False)  # PRIVACY_EVALUATION, REDACTION, SECRET_ACCESS, PERMISSION_CHECK, TOOL_CONFIRMATION, BLOCKED_ACTION
    actor = Column(String(50), default="system", nullable=False)
    action = Column(String(100), nullable=False)
    resource = Column(String(255), nullable=True)
    decision = Column(String(50), nullable=False)   # ALLOWED, REDACTED, CONFIRMATION_REQUIRED, BLOCKED, REJECTED
    reason = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)     # Redacted metadata only

Index("idx_audit_timestamp", SecurityAuditEvent.timestamp)
Index("idx_audit_event_type", SecurityAuditEvent.event_type)

class AuditLogger:
    """
    Security Audit System.
    Logs structured security decisions into SQLite and application logs while strictly enforcing zero-secret logging.
    """

    @staticmethod
    def log_event(
        event_type: str,
        action: str,
        decision: str,
        resource: Optional[str] = None,
        reason: Optional[str] = None,
        actor: str = "system",
        metadata: Optional[Dict[str, Any]] = None
    ) -> SecurityAuditEvent:
        import json
        
        # Ensure metadata does not contain raw credentials or secret values
        safe_meta = metadata.copy() if metadata else {}
        for forbidden in ["secret", "password", "token", "api_key", "raw_content"]:
            if forbidden in safe_meta:
                safe_meta[forbidden] = "[REDACTED_BY_AUDIT]"

        meta_json = json.dumps(safe_meta) if safe_meta else None
        
        event = SecurityAuditEvent(
            event_type=event_type,
            actor=actor,
            action=action,
            resource=resource,
            decision=decision,
            reason=reason,
            metadata_json=meta_json
        )

        db = SessionLocal()
        try:
            db.add(event)
            db.commit()
            db.refresh(event)
        except Exception as e:
            logger.error(f"Failed to record security audit event: {e}")
        finally:
            db.close()

        logger.info(f"[SECURITY AUDIT] [{event_type}] Action: '{action}' | Decision: '{decision}' | Resource: '{resource or 'N/A'}' | Reason: '{reason or 'N/A'}'")
        return event

    @staticmethod
    def get_recent_events(limit: int = 50) -> List[SecurityAuditEvent]:
        db = SessionLocal()
        try:
            return db.query(SecurityAuditEvent).order_by(SecurityAuditEvent.timestamp.desc()).limit(limit).all()
        finally:
            db.close()

audit_logger = AuditLogger()
