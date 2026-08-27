"""Backend capability table (Slice 1).

This is a thin mirror of the frontend `capabilities.ts` table. It exists so the
backend can validate `verb` and `capability_id` server-side without
constructing a separate registry system.

The slice-1 table is intentionally tiny: @ai is executable, @browser is
recognized-but-disabled and NEVER executes. No other capabilities exist yet.
Future capabilities (Gmail, Calendar, etc.) MUST be added to this table with
enabled=False and availability="deferred" until their real provider is wired.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Tuple

from app.notepad.schemas import RiskLevel


@dataclass(frozen=True)
class Capability:
    id: str
    provider: str
    name: str
    supported_actions: Tuple[str, ...]
    risk_default: RiskLevel
    requires_approval_above: RiskLevel
    enabled: bool
    availability: Literal["available", "unavailable", "deferred"]
    deferral_message: str = ""


CAPABILITIES: Dict[str, Capability] = {
    "ai": Capability(
        id="ai",
        provider="local_llm",
        name="AI",
        supported_actions=("summarize", "draft", "rewrite", "research", "extract"),
        risk_default=RiskLevel.LOW,
        requires_approval_above=RiskLevel.HIGH,
        enabled=True,
        availability="available",
    ),
    "browser": Capability(
        id="browser",
        provider="browser",
        name="Browser",
        supported_actions=(),
        risk_default=RiskLevel.MEDIUM,
        requires_approval_above=RiskLevel.LOW,
        enabled=False,
        availability="deferred",
        deferral_message="Browser capability is not enabled in this phase.",
    ),
}


def get_capability(capability_id: str) -> Capability | None:
    return CAPABILITIES.get(capability_id)


def is_executable(capability_id: str) -> bool:
    cap = CAPABILITIES.get(capability_id)
    return cap is not None and cap.enabled


def list_capabilities() -> List[Capability]:
    return list(CAPABILITIES.values())
