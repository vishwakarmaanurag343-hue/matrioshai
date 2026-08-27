"""Notepad API routes (Slice 1).

Routes:
  POST /notepad/ai          -> executes @ai through existing call_llm_structured
  POST /notepad/intent/detect -> server-side intent detection (for sync)

No new LLM client, no new provider abstraction, no new task engine, no new
approval engine. Existing call_llm_structured is the only LLM entry point.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.notepad.capabilities import get_capability, is_executable
from app.notepad.intent_block import split_body_and_intents
from app.notepad.intent_parser import detect_intents_for_line
from app.notepad import intent_store
from app.notepad.schemas import (
    IntentDetectRequest,
    IntentDetectResponse,
    IntentDTO,
    NotepadAIError,
    NotepadAIRequest,
    NotepadAIResponse,
    IntentPersistenceResponse,
    IntentPersistenceLoadResponse,
    IntentPersistenceSaveRequest,
)
from app.notepad.policy import classify_risk
from app.security.audit import audit_logger
from sqlalchemy.orm import Session
from app.core.database import get_db
from fastapi import Depends

logger = logging.getLogger("matrioshai.notepad")

router = APIRouter(prefix="/notepad", tags=["Notepad"])


# --- AI execution (the only LLM call site for the Notepad) ---


_NOTEPAD_AI_SYSTEM_PROMPT = (
    "You are a Notepad assistant. The user is writing a personal note and has "
    "invoked the @ai capability with a specific verb. Respond ONLY with a JSON "
    "object of the form: {\"summary\": string, \"suggestions\": [string], "
    "\"confidence\": number between 0 and 1}. Do not include any text outside "
    "the JSON object. The summary must be <= 2000 characters. Suggestions is "
    "optional and may be an empty array; max 10 entries. Confidence is your "
    "self-assessed confidence in the summary, between 0.0 and 1.0. Do not "
    "include credentials, API keys, or any secrets. Do not produce code that "
    "calls external services.\n\n"
    "The user message contains three explicit, labeled sections. Treat the "
    "content under each label as its declared role:\n"
    "  - current_note_context: the user's current note (bounded excerpt). Use "
    "    this to ground your answer. Do not invent content outside of it.\n"
    "  - intent: the @-capability line the user wrote (verbatim).\n"
    "  - requested_action: the verb the user asked for (e.g. summarize, draft).\n"
    "If a section is empty, treat it as empty. Do not request more context."
)


def _validate_ai_response(obj: Any) -> NotepadAIResponse:
    return NotepadAIResponse.model_validate(obj)


@router.post("/ai")
async def notepad_ai(req: NotepadAIRequest) -> Dict[str, Any]:
    """Execute an @ai intent through the existing call_llm_structured.

    Hard rules:
      - verb MUST be in @ai's supported_actions, else 400 UNKNOWN_INTENT
      - capability @ai MUST be enabled, else 400 DEFERRED_CAPABILITY
      - The provider chain is the ONLY LLM call site. We never instantiate
        a new client, never read credentials directly, and never log keys.
      - The user message is built ONLY from req.text + req.context_block,
        hard-capped at 1500 chars for context_block server-side (Pydantic).
    """
    cap = get_capability("ai")
    if cap is None or not is_executable("ai"):
        raise HTTPException(
            status_code=400,
            detail=NotepadAIError(
                category="DEFERRED_CAPABILITY",
                message="@ai is not enabled in this phase.",
            ).model_dump(),
        )

    if req.verb not in cap.supported_actions:
        raise HTTPException(
            status_code=400,
            detail=NotepadAIError(
                category="UNKNOWN_INTENT",
                message=f"Unknown verb '{req.verb}' for @ai.",
            ).model_dump(),
        )

    # Risk/approval classification (slice 1: research requires approval, but
    # slice 1's Notepad does not yet run multi-step AgentTasks; this is
    # reported in the response so the frontend can render an approval prompt
    # in a future phase. The current /notepad/ai call does not gate on it.)
    classify_risk("ai", req.verb, req.text)

    # Build user message. ONLY labeled, bounded sections go to the LLM.
    # The current note context is built from current_note_context, falling
    # back to context_block for slice-1 backward compatibility.
    current_note_context = req.current_note_context or req.context_block or ""
    intent_text = req.intent or req.text or ""
    requested_action = req.requested_action or req.verb or ""

    # Hard cap: total user message <= 4000 chars. Pydantic already caps each
    # field, but the LLM context is what matters; we further defend here.
    MAX_TOTAL = 4000
    parts = [
        "[current_note_context]",
        current_note_context[:2000],
        "[/current_note_context]",
        "[intent]",
        intent_text[:4000],
        "[/intent]",
        "[requested_action]",
        requested_action[:64],
        "[/requested_action]",
    ]
    user_block = "\n".join(parts)
    if len(user_block) > MAX_TOTAL:
        user_block = user_block[:MAX_TOTAL]

    messages = [
        {"role": "system", "content": _NOTEPAD_AI_SYSTEM_PROMPT},
        {"role": "user", "content": user_block},
    ]

    # Lazy import to keep route import surface small.
    from app.llm.provider_chain import call_llm_structured

    trace_id = uuid.uuid4().hex
    try:
        result, _raw = await call_llm_structured(
            messages=messages,
            validate=_validate_ai_response,
            max_attempts=4,
            temperature=req.temperature,
        )
    except ValueError as e:
        # Schema violation after all retries.
        logger.warning("notepad_ai schema_violation trace_id=%s err=%s", trace_id, e)
        audit_logger.log_event(
            event_type="NOTEPAD_AI",
            action="execute",
            resource=req.intent_id,
            decision="BLOCKED",
            reason=f"schema_violation trace_id={trace_id}",
        )
        raise HTTPException(
            status_code=502,
            detail=NotepadAIError(
                category="SCHEMA_VIOLATION",
                message="The model did not produce a valid response after retries.",
                trace_id=trace_id,
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("notepad_ai internal_error trace_id=%s", trace_id)
        audit_logger.log_event(
            event_type="NOTEPAD_AI",
            action="execute",
            resource=req.intent_id,
            decision="BLOCKED",
            reason=f"internal_error trace_id={trace_id} type={type(e).__name__}",
        )
        raise HTTPException(
            status_code=500,
            detail=NotepadAIError(
                category="INTERNAL",
                message="An internal error occurred while calling the AI provider.",
                trace_id=trace_id,
            ).model_dump(),
        )

    audit_logger.log_event(
        event_type="NOTEPAD_AI",
        action="execute",
        resource=req.intent_id,
        decision="ALLOWED",
        reason=(
            f"model={result.model} provider={result.provider} "
            f"tokens={result.confidence} trace_id={trace_id}"
        ),
    )

    return result.model_dump()


# --- Server-side intent detection (for sync between FE and BE) ---


@router.post("/intent/detect", response_model=IntentDetectResponse)
async def intent_detect(req: IntentDetectRequest) -> IntentDetectResponse:
    """Run intent detection over a note body. The frontend also runs this
    locally for instant feedback; the backend version is the source of truth
    and is what gets persisted into the markdown intent block on save."""
    _clean_body, parsed, malformed = split_body_and_intents(req.text)
    # If the block has stale intent objects, we do not trust them for
    # re-execution; we re-detect from the clean body instead. The intent
    # block is purely a persistence carrier.
    intents: List[IntentDTO] = []
    if _clean_body:
        lines = _clean_body.split("\n")
        for idx, line in enumerate(lines):
            detected = detect_intents_for_line(line, idx + 1, req.note_id)
            if detected is not None:
                intents.append(IntentDTO(**detected))
    _ = parsed  # parsed is intentionally not used here; it would carry stale state
    return IntentDetectResponse(intents=intents, malformed_block=malformed)


# --- Sidecar persistence (Slice 1.1) ---


@router.get("/notes/{note_id}/intents", response_model=IntentPersistenceLoadResponse)
def load_note_intents(note_id: str, db: Session = Depends(get_db)) -> IntentPersistenceLoadResponse:
    """Load the persisted Intent array for a note from its sidecar JSON.

    A missing sidecar is a non-error: returns empty list. A malformed
    sidecar is reported via `malformed=true` and returns empty list; the
    note must still work after this call.
    """
    intents, malformed = intent_store.load_intents(db, note_id)
    return IntentPersistenceLoadResponse(intents=intents, malformed=malformed)


@router.put("/notes/{note_id}/intents", response_model=IntentPersistenceResponse)
def save_note_intents(
    note_id: str,
    payload: IntentPersistenceSaveRequest,
    db: Session = Depends(get_db),
) -> IntentPersistenceResponse:
    """Persist the current Intent array for a note to its sidecar JSON.

    The write is atomic. The note's markdown file is NOT touched. The
    `NotesService` is NOT called.
    """
    saved = intent_store.save_intents(db, note_id, payload.intents)
    return IntentPersistenceResponse(saved=saved)
