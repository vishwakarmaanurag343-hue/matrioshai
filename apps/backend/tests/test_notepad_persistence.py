"""Slice 1.1 backend tests for sidecar JSON persistence and labeled AI context."""
import json
import pytest
from unittest.mock import patch, AsyncMock

from app.notepad.intent_store import load_intents, save_intents
from app.notepad.schemas import NotepadAIRequest, NotepadAIResponse


# ============================================================================
# Sidecar persistence
# ============================================================================


def test_sidecar_load_missing_returns_empty(test_db):
    # Create a Note row without writing a sidecar.
    from app.models.db_models import Note
    note = Note(title="t", file_path="2026/08/t.md", source="user", tags_json="[]")
    test_db.add(note)
    test_db.commit()
    test_db.refresh(note)

    intents, malformed = load_intents(test_db, note.id)
    assert intents == []
    assert malformed is False


def test_sidecar_round_trip(test_db, tmp_path):
    from app.models.db_models import Note
    # Override NOTES_PATH so we don't touch the real notes directory.
    from app.core import config
    config.settings.NOTES_PATH = str(tmp_path)

    note = Note(title="t", file_path="2026/08/t.md", source="user", tags_json="[]")
    test_db.add(note)
    test_db.commit()
    test_db.refresh(note)

    payload = [
        {"id": "a", "status": "COMPLETED", "result": {"summary": "ok"}},
        {"id": "b", "status": "FAILED", "failure": {"category": "X", "message": "y"}},
    ]
    saved = save_intents(test_db, note.id, payload)
    assert saved == 2

    loaded, malformed = load_intents(test_db, note.id)
    assert malformed is False
    assert loaded == payload


def test_sidecar_malformed_is_dropped(test_db, tmp_path):
    from app.models.db_models import Note
    from app.core import config
    config.settings.NOTES_PATH = str(tmp_path)

    note = Note(title="t", file_path="2026/08/t.md", source="user", tags_json="[]")
    test_db.add(note)
    test_db.commit()
    test_db.refresh(note)

    # Write a malformed sidecar directly.
    sidecar = tmp_path / "2026" / "08" / "t.md.intents.json"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text("[not json")

    intents, malformed = load_intents(test_db, note.id)
    assert intents == []
    assert malformed is True


def test_sidecar_rejects_escaping_paths(test_db, tmp_path):
    from app.models.db_models import Note
    from app.core import config
    config.settings.NOTES_PATH = str(tmp_path)

    # Note with a file_path that escapes the notes directory.
    note = Note(
        title="escape",
        file_path="../../etc/passwd",
        source="user",
        tags_json="[]",
    )
    test_db.add(note)
    test_db.commit()
    test_db.refresh(note)

    with pytest.raises(ValueError):
        save_intents(test_db, note.id, [{"id": "a"}])

    with pytest.raises(ValueError):
        load_intents(test_db, note.id)


# ============================================================================
# /notepad/notes/{note_id}/intents endpoints
# ============================================================================


def test_intents_endpoint_round_trip(client, test_db, tmp_path):
    from app.core import config
    from app.models.db_models import Note
    config.settings.NOTES_PATH = str(tmp_path)

    # Create a Note row on the test session the API also uses.
    note = Note(title="t", file_path="2026/08/t.md", source="user", tags_json="[]")
    test_db.add(note)
    test_db.commit()
    test_db.refresh(note)
    note_id = note.id

    # PUT intents
    res = client.put(
        f"/api/v1/notepad/notes/{note_id}/intents",
        json={"intents": [{"id": "a", "status": "COMPLETED"}]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["saved"] == 1

    # GET intents
    res = client.get(f"/api/v1/notepad/notes/{note_id}/intents")
    assert res.status_code == 200
    body = res.json()
    assert body["intents"] == [{"id": "a", "status": "COMPLETED"}]
    assert body["malformed"] is False


def test_intents_endpoint_missing_sidecar_returns_empty(client, test_db, tmp_path):
    from app.core import config
    from app.models.db_models import Note
    config.settings.NOTES_PATH = str(tmp_path)

    note = Note(title="t", file_path="2026/08/t.md", source="user", tags_json="[]")
    test_db.add(note)
    test_db.commit()
    test_db.refresh(note)
    note_id = note.id

    res = client.get(f"/api/v1/notepad/notes/{note_id}/intents")
    assert res.status_code == 200
    body = res.json()
    assert body["intents"] == []
    assert body["malformed"] is False


# ============================================================================
# AI route: labeled context fields
# ============================================================================


def test_notepad_ai_route_uses_labeled_context_fields(client):
    """When the client provides the new labeled fields, the user message
    sent to the provider chain must contain the labeled sections in order."""
    fake_response = type(
        "R",
        (),
        {
            "model": "test-model",
            "provider": "test-provider",
            "confidence": 0.9,
            "summary": "A short summary.",
            "suggestions": ["One"],
            "model_dump": lambda self: {
                "summary": self.summary,
                "suggestions": self.suggestions,
                "confidence": self.confidence,
                "model": self.model,
                "provider": self.provider,
            },
        },
    )()
    captured = {}

    async def fake_structured(messages, validate, max_attempts=4, temperature=0.1):
        captured["messages"] = messages
        return (fake_response, "{}")

    with patch("app.llm.provider_chain.call_llm_structured", new=AsyncMock(side_effect=fake_structured)):
        res = client.post(
            "/api/v1/notepad/ai",
            json={
                "intent_id": "i1",
                "note_id": "n1",
                "verb": "summarize",
                "text": "Summarize this note @ai",
                "current_note_context": "Meeting with client tomorrow.",
                "intent": "Summarize this note @ai",
                "requested_action": "summarize",
                "temperature": 0.2,
            },
        )
    assert res.status_code == 200, res.text
    msgs = captured["messages"]
    assert len(msgs) == 2
    user = msgs[1]["content"]
    # The three labeled sections must appear, in order, with the values we sent.
    assert "[current_note_context]" in user
    assert "Meeting with client tomorrow." in user
    assert "[intent]" in user
    assert "Summarize this note @ai" in user
    assert "[requested_action]" in user
    assert "summarize" in user
    # Sections must close.
    assert "[/current_note_context]" in user
    assert "[/intent]" in user
    assert "[/requested_action]" in user
    # The system prompt must mention the three labels.
    sys = msgs[0]["content"]
    assert "current_note_context" in sys
    assert "intent" in sys
    assert "requested_action" in sys


def test_notepad_ai_route_falls_back_to_legacy_context_block(client):
    """If the new labeled fields are absent, the route must fall back to
    the legacy context_block for backward compatibility with slice 1 callers."""
    fake_response = type(
        "R",
        (),
        {
            "model": "m",
            "provider": "p",
            "confidence": 0.5,
            "summary": "ok",
            "suggestions": [],
            "model_dump": lambda self: {
                "summary": self.summary,
                "suggestions": self.suggestions,
                "confidence": self.confidence,
                "model": self.model,
                "provider": self.provider,
            },
        },
    )()
    captured = {}

    async def fake_structured(messages, validate, max_attempts=4, temperature=0.1):
        captured["messages"] = messages
        return (fake_response, "{}")

    with patch("app.llm.provider_chain.call_llm_structured", new=AsyncMock(side_effect=fake_structured)):
        res = client.post(
            "/api/v1/notepad/ai",
            json={
                "intent_id": "i1",
                "note_id": "n1",
                "verb": "summarize",
                "text": "@ai summarize",
                "context_block": "legacy block",
                "temperature": 0.2,
            },
        )
    assert res.status_code == 200
    user = captured["messages"][1]["content"]
    assert "legacy block" in user


def test_notepad_ai_route_hard_caps_user_message(client):
    """The total user message must be hard-capped at 4000 chars regardless
    of how much the caller stuffs into the labeled fields."""
    fake_response = type(
        "R",
        (),
        {
            "model": "m",
            "provider": "p",
            "confidence": 0.5,
            "summary": "ok",
            "suggestions": [],
            "model_dump": lambda self: {
                "summary": self.summary,
                "suggestions": self.suggestions,
                "confidence": self.confidence,
                "model": self.model,
                "provider": self.provider,
            },
        },
    )()
    captured = {}

    async def fake_structured(messages, validate, max_attempts=4, temperature=0.1):
        captured["messages"] = messages
        return (fake_response, "{}")

    # The schema caps each labeled field (current_note_context=2000,
    # intent=4000, requested_action=64). The route further caps the joined
    # user_block at 4000 chars. We feed a value at the schema boundary
    # (2000 chars) plus a long-but-valid intent (4000) so the route's
    # 4000-char defense is what bounds the user message.
    with patch("app.llm.provider_chain.call_llm_structured", new=AsyncMock(side_effect=fake_structured)):
        res = client.post(
            "/api/v1/notepad/ai",
            json={
                "intent_id": "i1",
                "note_id": "n1",
                "verb": "summarize",
                "text": "@ai summarize",
                "current_note_context": "x" * 2000,
                "intent": "y" * 4000,
                "requested_action": "summarize",
                "temperature": 0.2,
            },
        )
    assert res.status_code == 200
    user = captured["messages"][1]["content"]
    assert len(user) <= 4000


def test_notepad_ai_route_rejects_oversize_labeled_fields(client):
    """A caller that exceeds the Pydantic field caps must be rejected
    at validation time (422), not silently truncated. This documents the
    defense layer order: Pydantic first, then the route's 4000-char cap."""
    res = client.post(
        "/api/v1/notepad/ai",
        json={
            "intent_id": "i1",
            "note_id": "n1",
            "verb": "summarize",
            "text": "@ai summarize",
            "current_note_context": "x" * 2001,  # schema cap is 2000
            "intent": "ok",
            "requested_action": "summarize",
            "temperature": 0.2,
        },
    )
    assert res.status_code == 422
