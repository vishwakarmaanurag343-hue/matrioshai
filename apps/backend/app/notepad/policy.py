"""Risk classification + approval policy for Notepad intents (Slice 1).

Slice 1 only handles @ai; @browser is deferred and never reaches this module.
Future capabilities MUST extend this policy with their own rules, but the
existing rules MUST remain unchanged.
"""
from __future__ import annotations

from typing import Tuple

from app.notepad.capabilities import CAPABILITIES, get_capability
from app.notepad.schemas import RiskLevel


# Words that suggest the user wants to execute something with side effects.
# In Slice 1, none of the supported verbs cause external side effects, but we
# keep the structure so future capabilities can plug in.
_INJECTION_INDICATORS = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "disregard the above",
)


def classify_risk(capability_id: str, verb: str, text: str) -> Tuple[RiskLevel, bool]:
    """Return (risk, approval_required) for a given intent.

    Rules for Slice 1:
    - @ai summarize / draft / rewrite / extract   -> LOW, no approval
    - @ai research                                -> MEDIUM, approval required
    - @ai *  with prompt-injection indicator      -> HIGH, approval required
    - any other verb on @ai                       -> LOW, no approval
    - @browser / unknown / disabled               -> caller MUST short-circuit
                                                    before reaching here
    """
    cap = get_capability(capability_id)
    if cap is None or not cap.enabled:
        # Defensive: caller should never ask us about a disabled capability,
        # but if they do, the safest answer is MEDIUM + approval.
        return RiskLevel.MEDIUM, True

    text_lower = (text or "").lower()
    if any(ind in text_lower for ind in _INJECTION_INDICATORS):
        return RiskLevel.HIGH, True

    if verb == "research":
        return RiskLevel.MEDIUM, True

    if verb in ("summarize", "draft", "rewrite", "extract"):
        return RiskLevel.LOW, False

    return cap.risk_default, False
