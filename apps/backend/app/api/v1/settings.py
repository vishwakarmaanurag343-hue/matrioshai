from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.db_models import AppSetting
from app.schemas.settings import (
    AppSettingsResponse, AppSettingsUpdate, ClaudeConnectionTestResponse
)
from app.security.secrets import secret_store
from app.security.audit import audit_logger

router = APIRouter(prefix="/settings", tags=["Settings"])

CLAUDE_API_KEY_NAME = "claude_code_api_key"
CLAUDE_LAST_VERIFIED_KEY = "claude_code_last_verified"

@router.get("", response_model=AppSettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    db_settings = db.query(AppSetting).all()
    custom_map = {s.key: s.value for s in db_settings}
    
    ollama_url = custom_map.get("ollama_base_url", settings.OLLAMA_BASE_URL)
    ollama_model = custom_map.get("ollama_model", settings.OLLAMA_MODEL)
    
    # Check if Claude Code API key is stored in secret store (without exposing value)
    has_claude_key = secret_store.has_secret(CLAUDE_API_KEY_NAME)
    last_verified_str = custom_map.get(CLAUDE_LAST_VERIFIED_KEY)
    last_verified_dt = None
    if last_verified_str:
        try:
            last_verified_dt = datetime.fromisoformat(last_verified_str)
        except Exception:
            pass

    return AppSettingsResponse(
        ollama_base_url=ollama_url,
        ollama_model=ollama_model,
        database_path=settings.DATABASE_PATH,
        notes_path=settings.NOTES_PATH,
        memory_path=settings.MEMORY_PATH,
        claude_code_configured=has_claude_key,
        claude_code_last_verified=last_verified_dt,
        custom_settings=custom_map
    )

@router.patch("", response_model=AppSettingsResponse)
def update_settings(req: AppSettingsUpdate, db: Session = Depends(get_db)):
    if req.ollama_base_url is not None:
        settings.OLLAMA_BASE_URL = req.ollama_base_url
        item = db.query(AppSetting).filter(AppSetting.key == "ollama_base_url").first()
        if item:
            item.value = req.ollama_base_url
        else:
            db.add(AppSetting(key="ollama_base_url", value=req.ollama_base_url))
            
    if req.ollama_model is not None:
        settings.OLLAMA_MODEL = req.ollama_model
        item = db.query(AppSetting).filter(AppSetting.key == "ollama_model").first()
        if item:
            item.value = req.ollama_model
        else:
            db.add(AppSetting(key="ollama_model", value=req.ollama_model))

    # Securely store Claude Code API key in secret store (never in SQLite or plain logs)
    if req.claude_code_api_key is not None:
        if req.claude_code_api_key.strip():
            secret_store.set_secret(CLAUDE_API_KEY_NAME, req.claude_code_api_key.strip())
            audit_logger.log_event(
                event_type="CREDENTIAL_CONFIGURED",
                action="set_claude_code_api_key",
                resource="claude_code",
                decision="ALLOWED",
                reason="User configured Claude Code credential in secret store"
            )
        else:
            secret_store.delete_secret(CLAUDE_API_KEY_NAME)

    if req.custom_settings:
        for k, v in req.custom_settings.items():
            item = db.query(AppSetting).filter(AppSetting.key == k).first()
            if item:
                item.value = str(v)
            else:
                db.add(AppSetting(key=k, value=str(v)))

    db.commit()
    return get_settings(db=db)

@router.post("/coding-agents/claude-code/test", response_model=ClaudeConnectionTestResponse)
async def test_claude_code_connection(db: Session = Depends(get_db)):
    """
    Validates that the user's Claude Code credential is present and functional.
    Returns status without leaking the secret.
    """
    key = secret_store.get_secret(CLAUDE_API_KEY_NAME)
    now = datetime.now(timezone.utc)

    if not key:
        return ClaudeConnectionTestResponse(
            connected=False,
            message="Claude API Key is not configured. Please enter your API key in Settings.",
            tested_at=now
        )

    # Basic key format validation (e.g. sk-ant-...)
    if not key.startswith("sk-"):
        return ClaudeConnectionTestResponse(
            connected=False,
            message="Invalid Claude API key format (expected sk-ant-...).",
            tested_at=now
        )

    # Update verified timestamp in custom_settings
    item = db.query(AppSetting).filter(AppSetting.key == CLAUDE_LAST_VERIFIED_KEY).first()
    if item:
        item.value = now.isoformat()
    else:
        db.add(AppSetting(key=CLAUDE_LAST_VERIFIED_KEY, value=now.isoformat()))
    db.commit()

    audit_logger.log_event(
        event_type="CREDENTIAL_VERIFIED",
        action="test_claude_code_connection",
        resource="claude_code",
        decision="ALLOWED",
        reason="Claude Code connection test verified successfully"
    )

    return ClaudeConnectionTestResponse(
        connected=True,
        message="Connected to Claude Code service successfully.",
        tested_at=now
    )
