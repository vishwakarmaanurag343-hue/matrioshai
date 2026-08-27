"""Server-side intent parser (Slice 1).

Mirrors apps/desktop/src/features/notepad/intentParser.ts. Detection is
deterministic and local; no LLM is used. The parser produces an IntentDTO-
shaped dict so the route can return it directly.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.notepad.capabilities import CAPABILITIES, get_capability, is_executable
from app.notepad.schemas import (
    IntentType,
    RiskLevel,
)


_AT_TOKEN_PATTERN = re.compile(r"(?:^|\s)@([a-z][a-z0-9_-]{1,32})\b(.*)$")

def _at_token_match(line: str):
    """Match an @-capability token anywhere on the line. Returns the match
    object or None. We use search+lookbehind so the prefix whitespace is
    not consumed and we can still anchor to start-of-line."""
    # Try start-of-line first (so leading @ai still works).
    m = re.match(r"@([a-z][a-z0-9_-]{1,32})\b(.*)$", line)
    if m:
        return m
    # Otherwise find an @-token preceded by whitespace.
    return re.search(r"(?<=\s)@([a-z][a-z0-9_-]{1,32})\b(.*)$", line)
_TODO_PATTERN = re.compile(r"^\s*(?:[-*]\s*)?(?:#\s*)?(?:\[(?:\s|x)?\]\s*)?TODO\b[:\s]*(.*)$", re.IGNORECASE)
_COMMAND_PATTERN = re.compile(r"^/([a-z][a-z0-9_-]{0,32})\b(.*)$")

_INJECTION_INDICATORS = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "disregard the above",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def _infer_verb(cap_actions: tuple, rest: str) -> str:
    first = (rest.strip().split() or [""])[0].lower()
    if first in cap_actions:
        return first
    return cap_actions[0] if cap_actions else ""


def _classify_risk(capability_id: str, verb: str, text: str) -> Dict[str, Any]:
    lower = (text or "").lower()
    if any(ind in lower for ind in _INJECTION_INDICATORS):
        return {"risk": RiskLevel.HIGH, "approval": True}
    if capability_id == "ai":
        if verb == "research":
            return {"risk": RiskLevel.MEDIUM, "approval": True}
        if verb in ("summarize", "draft", "rewrite", "extract"):
            return {"risk": RiskLevel.LOW, "approval": False}
        return {"risk": RiskLevel.LOW, "approval": False}
    return {"risk": RiskLevel.MEDIUM, "approval": True}


def _type_for_verb(capability_id: str, verb: str) -> IntentType:
    if capability_id != "ai":
        return IntentType.EXTERNAL_ACTION
    mapping = {
        "research": IntentType.RESEARCH_REQUEST,
        "draft": IntentType.DRAFT_REQUEST,
        "summarize": IntentType.TASK,
        "rewrite": IntentType.TASK,
        "extract": IntentType.TASK,
    }
    return mapping.get(verb, IntentType.TASK)


def detect_intents_for_line(raw_line: str, line_number: int, note_id: str) -> Optional[Dict[str, Any]]:
    """Return a dict matching IntentDTO fields, or None for plain text."""
    if raw_line is None:
        return None
    trimmed = raw_line.rstrip("\r")
    if not trimmed.strip():
        return None

    # TODO
    todo = _TODO_PATTERN.match(trimmed)
    if todo:
        return {
            "id": _new_id(),
            "note_id": note_id,
            "line_number": line_number,
            "raw_text": trimmed,
            "type": IntentType.TODO.value,
            "entities": {"rest": todo.group(1) or ""},
            "capability_id": None,
            "requested_action": "",
            "risk": RiskLevel.LOW.value,
            "approval_required": False,
            "confidence": 1.0,
            "status": "DETECTED",
            "task_id": None,
            "confirmation_id": None,
            "result": None,
            "failure": None,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }

    # COMMAND (reserved; safe no-op in slice 1)
    if _COMMAND_PATTERN.match(trimmed):
        return {
            "id": _new_id(),
            "note_id": note_id,
            "line_number": line_number,
            "raw_text": trimmed,
            "type": IntentType.COMMAND.value,
            "entities": {},
            "capability_id": None,
            "requested_action": "",
            "risk": RiskLevel.LOW.value,
            "approval_required": False,
            "confidence": 1.0,
            "status": "SKIPPED",
            "task_id": None,
            "confirmation_id": None,
            "result": None,
            "failure": None,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }

    # @-capability
    at = _at_token_match(trimmed)
    if at:
        token = at.group(1).lower()
        rest = at.group(2) or ""
        cap = get_capability(token)
        if cap is not None:
            verb = _infer_verb(cap.supported_actions, rest)
            risk = _classify_risk(cap.id, verb, trimmed)
            executable = is_executable(cap.id)
            return {
                "id": _new_id(),
                "note_id": note_id,
                "line_number": line_number,
                "raw_text": trimmed,
                "type": _type_for_verb(cap.id, verb).value,
                "entities": {"verb": verb, "rest": rest.strip()},
                "capability_id": cap.id,
                "requested_action": verb,
                "risk": risk["risk"].value if hasattr(risk["risk"], "value") else risk["risk"],
                "approval_required": risk["approval"],
                "confidence": 1.0 if executable else 0.0,
                "status": "DETECTED" if executable else "DEFERRED",
                "task_id": None,
                "confirmation_id": None,
                "result": None,
                "failure": None,
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
            }
        # Unknown @capability: fall through to plain text.

    return None


def detect_intents_in_note(text: str, note_id: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    out: List[Dict[str, Any]] = []
    for idx, line in enumerate(text.split("\n")):
        detected = detect_intents_for_line(line, idx + 1, note_id)
        if detected is not None:
            out.append(detected)
    return out
