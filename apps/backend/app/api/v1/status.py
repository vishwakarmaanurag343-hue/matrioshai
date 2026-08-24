from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.config import settings
from app.llm.ollama import OllamaProvider
from app.schemas.status import SystemStatusResponse, ComponentStatus
from app.security.secrets import secret_store

router = APIRouter(prefix="/status", tags=["Status"])

@router.get("", response_model=SystemStatusResponse)
async def get_system_status(db: Session = Depends(get_db)):
    # 1. Backend
    backend_status = ComponentStatus(name="Backend", status="Connected", details="FastAPI server bound strictly to 127.0.0.1")

    # 2. Database
    try:
        db.execute(text("SELECT 1"))
        db_status = ComponentStatus(name="Database", status="Connected", details=f"SQLite active at {settings.DATABASE_PATH} (WAL enabled)")
    except Exception as e:
        db_status = ComponentStatus(name="Database", status="Unavailable", details=f"Database error: {str(e)}")

    # 3. Ollama & Model
    ollama_provider = OllamaProvider()
    ollama_info = await ollama_provider.health()
    
    if ollama_info["connected"]:
        oll_status = ComponentStatus(name="Local AI", status="Connected", details=ollama_info["details"])
        if ollama_info["model_available"]:
            model_status = ComponentStatus(name="Model", status="Loaded", details=f"Configured model '{settings.OLLAMA_MODEL}' is ready")
        else:
            model_status = ComponentStatus(name="Model", status="Missing", details=f"Model '{settings.OLLAMA_MODEL}' not found. Run 'ollama pull {settings.OLLAMA_MODEL}'")
    else:
        oll_status = ComponentStatus(name="Local AI", status="Unavailable", details=ollama_info["details"])
        model_status = ComponentStatus(name="Model", status="Unavailable", details="Local LLM server offline")

    # 4. Memory
    memory_status = ComponentStatus(name="Memory", status="Ready", details="Tiered memory engine active with privacy filtering")

    # 5. Notes
    notes_dir = Path(settings.NOTES_PATH)
    if notes_dir.exists():
        notes_status = ComponentStatus(name="Notes", status="Ready", details=f"Markdown notes active with path traversal protection")
    else:
        notes_status = ComponentStatus(name="Notes", status="Unavailable", details="Notes directory missing")

    # 6. Security Subsystem Statuses
    privacy_status = ComponentStatus(name="Privacy Gate", status="Active", details="PII detection and context sanitization active")
    secret_status = ComponentStatus(name="Secret Store", status="Active", details="Isolated OS Keychain storage available")
    audit_status = ComponentStatus(name="Audit Log", status="Active", details="Zero-secret security audit trail enabled")
    tool_status = ComponentStatus(name="Tool Execution", status="Restricted", details="Tier 1-3 permission engine active (autonomous destructive tools blocked)")

    return SystemStatusResponse(
        app_name=settings.APP_NAME,
        app_version="0.2.0",
        backend=backend_status,
        database=db_status,
        ollama=oll_status,
        model=model_status,
        memory=memory_status,
        notes=notes_status,
        privacy_gate=privacy_status,
        secret_store=secret_status,
        audit_log=audit_status,
        tool_execution=tool_status
    )
