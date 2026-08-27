"""Lossless markdown intent block parser.

A Notepad note is allowed to carry a fenced HTML comment block that holds
serialized Intent records. On read, the block is stripped from the markdown
body that the editor sees. On write, the block is re-emitted at the end of
the file with the latest Intent snapshot.

Round-trip rules:
- If the block is missing, the body is returned unchanged and the intents
  list is empty.
- If the block is malformed, it is dropped; the body is returned unchanged;
  a warning flag is set so the caller can show a toast.
- A note with zero Intents is byte-identical to a note with no intent block.
"""
from __future__ import annotations

import json
import re
from typing import List, Tuple

# Fenced HTML comment block. The marker is versioned (v1).
_BLOCK_PATTERN = re.compile(
    r"<!--\s*matrioshai:intents\s+v1\s*\n(?P<body>\[.*?\])\n\s*-->\s*$",
    re.DOTALL,
)
# Stricter pattern for matching the trailing block when extracting from body.
_TRAILING_BLOCK = re.compile(
    r"\n*<!--\s*matrioshai:intents\s+v1\s*\n\[.*?\]\n\s*-->\s*$",
    re.DOTALL,
)


def split_body_and_intents(markdown: str) -> Tuple[str, List[dict], bool]:
    """Return (clean_body, intents, had_malformed_block).

    - clean_body: the markdown with the trailing intent block (if any) removed.
    - intents: list of intent dicts; empty if no block.
    - had_malformed_block: True if a block was found but could not be parsed;
      in that case the body is still returned (block stripped) and intents=[]
      so the note still loads.
    """
    if markdown is None:
        return "", [], False

    match = _BLOCK_PATTERN.search(markdown)
    if not match:
        return markdown, [], False

    body_text = match.group("body")
    try:
        parsed = json.loads(body_text)
        if not isinstance(parsed, list):
            return _strip_block(markdown), [], True
        intents = [i for i in parsed if isinstance(i, dict)]
        return _strip_block(markdown), intents, False
    except (ValueError, TypeError):
        return _strip_block(markdown), [], True


def _strip_block(markdown: str) -> str:
    """Strip a trailing intent block from a markdown string.

    Preserves the single trailing newline that the block was preceded by, so
    that bodies without an explicit intent block remain byte-identical.
    """
    return _TRAILING_BLOCK.sub("\n", markdown) if markdown.endswith("\n") else _TRAILING_BLOCK.sub("", markdown)


def serialize_intent_block(intents: List[dict]) -> str:
    """Return a serialized intent block ready to append to a markdown file.

    Always returns a deterministic, compact JSON list. If the list is empty,
    returns an empty string so that a note with zero Intents is byte-identical
    to a note with no block.
    """
    if not intents:
        return ""
    body = json.dumps(intents, ensure_ascii=False, separators=(",", ":"))
    return f"\n<!-- matrioshai:intents v1\n{body}\n-->\n"


def write_note_with_intents(markdown_body: str, intents: List[dict]) -> str:
    """Return the full note file content (body + optional intent block)."""
    # Ensure body has no trailing block before we re-emit.
    body_clean, _, _ = split_body_and_intents(markdown_body)
    block = serialize_intent_block(intents)
    if not block:
        return body_clean
    return body_clean.rstrip("\n") + block
