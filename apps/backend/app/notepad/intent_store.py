"""Sidecar JSON persistence for Notepad intents (Slice 1.1).

Each Note gets an optional `<file_path>.intents.json` sidecar next to its
markdown file. The sidecar holds the canonical Intent array for that note.

Design:
- The sidecar is owned by this module. The existing `NotesService` is NOT
  modified.
- Path safety: every read/write resolves the sidecar path under
  `settings.NOTES_PATH` and rejects paths that escape it (same invariant
  as `NotesService._validate_safe_path`).
- A missing sidecar is a non-error: load returns an empty list.
- A malformed sidecar is dropped: load returns the empty list and reports
  `malformed=True` so the caller can show a warning toast. The note still
  loads and continues to work.
- Writes are atomic: we write to a `.tmp` file then `os.replace`.
- No secrets are stored on the sidecar (intents do not include API keys).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import logger
from sqlalchemy.orm import Session

from app.models.db_models import Note

_SIDECAR_SUFFIX = ".intents.json"


def _notes_dir() -> Path:
    return Path(settings.NOTES_PATH).resolve()


def _validate_safe_path(p: Path) -> Path:
    """Reject paths that escape the notes directory (defense in depth)."""
    real_p = Path(os.path.realpath(str(p)))
    real_notes = Path(os.path.realpath(str(_notes_dir())))
    if not str(real_p).startswith(str(real_notes) + os.sep) and real_p != real_notes:
        raise ValueError(
            f"Security error: path '{p}' escapes notes directory."
        )
    return real_p


def _sidecar_path_for_note(note: Note) -> Path:
    """Resolve the sidecar path for a given Note row.

    The sidecar is placed next to the markdown file, e.g.
    `<NOTES_PATH>/2026/08/slug.md.intents.json`.
    """
    abs_md = (_notes_dir() / note.file_path).resolve()
    # We do not require the markdown file to exist on disk; persistence
    # is allowed even for transient notes. The directory must, however,
    # exist or be creatable; we only validate the resolved path here.
    sidecar = abs_md.with_name(abs_md.name + _SIDECAR_SUFFIX)
    return _validate_safe_path(sidecar)


def _get_note_or_404(db: Session, note_id: str) -> Note:
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise LookupError(f"Note not found: {note_id}")
    return note


def load_intents(db: Session, note_id: str) -> Tuple[List[Dict[str, Any]], bool]:
    """Return (intents, malformed). Missing sidecar -> ([], False)."""
    try:
        note = _get_note_or_404(db, note_id)
    except LookupError:
        return [], False

    sidecar = _sidecar_path_for_note(note)
    if not sidecar.exists():
        return [], False
    try:
        with open(sidecar, "r", encoding="utf-8") as f:
            text = f.read()
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            logger.warning("intent sidecar for note %s is not a list; dropping", note_id)
            return [], True
        out: List[Dict[str, Any]] = [i for i in parsed if isinstance(i, dict)]
        return out, False
    except (OSError, ValueError, TypeError) as e:
        logger.warning("intent sidecar for note %s is malformed: %s", note_id, e)
        return [], True


def save_intents(db: Session, note_id: str, intents: List[Dict[str, Any]]) -> int:
    """Atomically write the intent list to the sidecar. Returns count saved."""
    note = _get_note_or_404(db, note_id)
    sidecar = _sidecar_path_for_note(note)
    sidecar.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(intents, ensure_ascii=False, separators=(",", ":"))
    # Atomic write: tmp + replace.
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=sidecar.name + ".", suffix=".tmp", dir=str(sidecar.parent)
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, sidecar)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    return len(intents)
