"""DeepSeek-Harness reasoning layer for browser tasks.

This is the BRAIN of the unified MATRIOSHAI Autonomous Browser Agent Runtime.
It deliberately owns NO execution: it receives the live semantic observation
(produced by the native WKWebView extractor via the frontend harness) plus
goal/history/verification context, and emits exactly ONE structured
AgentDecision. The frontend harness resolves/executes it against the real
browser and verifies the effect; the result is fed back on the next call.

Structured output is enforced through app.llm.provider_chain.call_llm_structured,
so an HTTP-200-with-empty-body from a provider can never be mistaken for a
reasoning result.
"""
import re
from typing import Any, Dict, List, Literal, Optional, get_args
from pydantic import BaseModel, Field

from app.llm.provider_chain import call_llm_structured


# ---------------------------------------------------------------------------
# Canonical decision model (single source of truth; mirrored in
# apps/desktop/src/features/browser/agent/types.ts)
# ---------------------------------------------------------------------------

ActionType = Literal[
    "NAVIGATE", "CLICK", "TYPE", "SELECT", "CHECK", "UNCHECK", "SCROLL",
    "PRESS_KEY", "SUBMIT", "GO_BACK", "GO_FORWARD", "OPEN_TAB", "SWITCH_TAB",
    "CLOSE_TAB", "WAIT", "OBSERVE", "EXTRACT",
    "ANSWER",            # respond to the user in plain text (question answered)
    "ASK_USER",          # need missing information from the user
    "WAIT_FOR_USER",     # user must take over the browser (login / captcha / otp)
    "DONE",              # goal achieved — summary in value
    "FAIL",              # genuinely unrecoverable — explanation in value
]

EffectType = Literal[
    "none", "url_changed", "url_contains", "value_changed",
    "text_present", "element_appeared", "dom_mutated", "tab_opened",
]


class ExpectedEffect(BaseModel):
    type: EffectType = "none"
    target: Optional[str] = None   # el_N for value_changed, substring for url_contains/text_present
    value: Optional[str] = None    # expected value / substring


class EvidenceItem(BaseModel):
    id: Optional[str] = None             # Phase 3: deterministic id e.g. "ev_17877912"
    label: str                          # e.g. "official price", "competitor price"
    value: str                          # e.g. "$1,299.00"
    normalized_value: Optional[str] = None # Phase 4: normalized comparison value
    source: str = ""                    # URL the fact came from
    tab_id: Optional[str] = None        # Phase 3: origin tab id
    timestamp: Optional[str] = None     # Phase 3: ISO timestamp
    confidence: Optional[float] = None  # Phase 3: 0.0-1.0
    evidence_type: Optional[str] = "OBSERVED" # OBSERVED | USER_PROVIDED | INFERRED | DERIVED
    validity: Optional[str] = "CURRENT"      # CURRENT | STALE | INVALIDATED | CONTRADICTED


class AgentDecision(BaseModel):
    action: ActionType
    target: Optional[str] = None       # el_N | url | direction | key name
    value: Optional[str] = None        # text to type | url | DONE/FAIL summary
    reason: str = ""                   # shown to the user ("why")
    expected_effect: ExpectedEffect = Field(default_factory=ExpectedEffect)
    requires_approval: bool = False    # sensitive action → approval gate before dispatch
    message: Optional[str] = None      # ASK_USER / WAIT_FOR_USER text
    evidence: List[EvidenceItem] = Field(default_factory=list)  # REQUIRED for DONE on research goals
    progress_estimate: Optional[int] = None                        # honest self-report 0-100
    subgoal: Optional[str] = None      # Phase 3: next active sub-objective
    confidence: Optional[float] = None # Phase 3: model self-reported confidence 0.0-1.0


FailureCategory = Literal[
    "TARGET_NOT_FOUND", "STALE_ELEMENT", "OBSERVATION_EMPTY", "EXTRACTION_FAILED",
    "NAVIGATION_FAILED", "VERIFICATION_FAILED", "AUTH_REQUIRED",
    "CAPTCHA", "BLOCKED", "PERMISSION_REQUIRED", "TIMEOUT", "UNKNOWN",
]


class ActionFailure(BaseModel):
    """Structured diagnosis attached to every unverified step."""
    category: FailureCategory = "UNKNOWN"
    action: str = ""
    target: Optional[str] = None
    page: str = ""
    url: str = ""
    attempt: int = 1
    evidence: str = ""                  # what was actually observed (truthful)


class StepRecord(BaseModel):
    """Compact record of one executed iteration, sent back as history."""
    iteration: int
    action: str
    target: Optional[str] = None
    value: Optional[str] = None
    dispatched: bool = True
    verified: bool = False             # effect actually observed?
    url_before: Optional[str] = None
    url_after: Optional[str] = None
    note: str = ""                     # failure reason / verification detail
    tab_id: Optional[str] = None       # which tab world-state this touched
    strategy: Optional[str] = None     # e.g. "dom-extract@host"
    failure: Optional[ActionFailure] = None


class TabSummary(BaseModel):
    tab_id: str
    url: str = ""
    title: str = ""
    active: bool = False


class ReasoningRequest(BaseModel):
    goal: str
    url: str = ""
    title: str = ""
    ready_state: str = "complete"
    headings: List[str] = Field(default_factory=list)
    text_blocks: List[str] = Field(default_factory=list)
    interactive_elements: List[Dict[str, Any]] = Field(default_factory=list)
    tabs: List[TabSummary] = Field(default_factory=list)
    history: List[StepRecord] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    failed_strategies: List[str] = Field(default_factory=list)   # exhausted strategies w/ counts
    observation_level: str = "dom"                               # perception level that produced this view
    subgoal: Optional[str] = None                                # Phase 3: active sub-objective
    accumulated_evidence: List[EvidenceItem] = Field(default_factory=list) # Phase 3: facts verified across steps/tabs


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the MATRIOSHAI browser-agent reasoning engine (DeepSeek Harness).
You are a PERSISTENT autonomous worker: you own the goal until COMPLETED, honest FAILED,
WAIT_FOR_USER, or user cancellation. One failed step never ends the task — diagnose it,
change strategy, and continue.

Reply with ONLY one JSON object, no markdown fences, no prose:
{
  "action": "<one of: NAVIGATE|CLICK|TYPE|SELECT|CHECK|UNCHECK|SCROLL|PRESS_KEY|SUBMIT|GO_BACK|GO_FORWARD|OPEN_TAB|SWITCH_TAB|CLOSE_TAB|WAIT|OBSERVE|EXTRACT|ANSWER|ASK_USER|WAIT_FOR_USER|DONE|FAIL>",
  "target": "<el_N from the interactive-element list, or a full URL for NAVIGATE/OPEN_TAB, or a tab_id for SWITCH_TAB>",
  "value":  "<text for TYPE, url for NAVIGATE, key name for PRESS_KEY (e.g. Enter/Home), option text for SELECT, final answer for ANSWER/DONE, explanation for FAIL>",
  "reason": "<one sentence explaining WHY, shown to the user>",
  "expected_effect": {"type": "<none|url_changed|url_contains|value_changed|text_present|element_appeared|dom_mutated|tab_opened>", "target": "<el_N or substring>", "value": "<expected value/substring>"},
  "requires_approval": <true ONLY for purchases, payments, bookings confirmation, sending messages, deleting data, publishing, account changes>,
  "message": "<text for ASK_USER / WAIT_FOR_USER>",
  "evidence": [{"label":"<fact name>","value":"<fact>","source":"<url>"}],
  "progress_estimate": <0-100 honest estimate of goal completion>
}

RULES:
1. If the user input is a QUESTION answerable from the current page/context, use ANSWER with the answer in "value". Do not act.
2. Only use el_N identifiers that appear in the CURRENT interactive-element list. Element ids belong to the tab you are observing — after SWITCH_TAB they change; re-read them.
3. TYPE only into textbox/searchbox/textarea roles. Never TYPE into links or buttons. Prefer pressing a named search button over PRESS_KEY; PRESS_KEY must name the key in "value".
4. After every mutating action state the single most checkable expected_effect (what proves it worked). For read-only steps (WAIT/OBSERVE/EXTRACT) leave expected_effect type "none". If EXTRACT has already been executed on the current page and EVIDENCE is present, your NEXT action MUST be ANSWER or DONE with the final summary in "value". Do NOT repeat EXTRACT on the same page.
5. If a page shows login/signup/OTP/CAPTCHA/password that blocks progress: WAIT_FOR_USER with a clear message. NEVER type passwords, OTP codes, or payment credentials yourself.
6. Purchases/payments/bookings/submissions that are irreversible: set requires_approval=true. You may PREPARE (fill cart/form) but the COMMIT happens only after explicit human approval.
7. RECOVERY: history entries marked NOT-VERIFIED carry a structured failure category. When the same action+target failed twice, or a FAILED STRATEGY appears with count>=2, you MUST change strategy: different element, different page section, different site/tab, or a different discovery route (e.g. site search, Google search tab, category navigation). Never repeat an exhausted strategy.
8. If the needed information is absent from the observation, do not loop: try another visible route (search box, category link, another tab). If genuinely impossible everywhere, FAIL honestly.
9. Multi-site research/comparison is encouraged: OPEN_TAB per source, SWITCH_TAB to revisit, EXTRACT facts into evidence, then synthesize.
10. DONE requires EVIDENCE: for research/comparison/find goals include an "evidence" array whose items carry label, value and source URL for every fact you claim (prices, product names, options). A DONE without the required facts will be rejected. Put the final comparison/answer in "value" too.
"""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_ELEMENT_RE = re.compile(r"^el_\d+$")
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

_KNOWN_ACTIONS = frozenset(get_args(ActionType))
_KNOWN_EFFECTS = frozenset(get_args(EffectType))
_ACTIONS_NEEDING_TARGET = {"CLICK", "TYPE", "SELECT", "CHECK", "UNCHECK"}
_SENSITIVE_HINTS = (
    "pay", "purchase", "checkout", "confirm booking", "place order",
    "buy now", "submit payment", "delete", "publish", "send message",
)
# Goals phrased like these require collected evidence before DONE is accepted.
_RESEARCH_GOAL_RE = re.compile(
    r"\b(compare|comparison|cheapest|best|find|research|price|prices|book|"
    r"search|recommend|which)\b", re.IGNORECASE,
)
_TYPEABLE_ROLES = {"textbox", "searchbox", "textarea", "combobox"}

_EFFECT_BY_ACTION = {
    "TYPE": "value_changed",
    "NAVIGATE": "url_contains",
    "OPEN_TAB": "tab_opened",
    "CLICK": "dom_mutated",      # default; model may specialise to url_contains/text_present
}

# Read-only / dispatch-only actions never mutate the page, so there is
# nothing to falsify — their postcondition is forced to "none".
_OBSERVATION_ONLY_ACTIONS = {"WAIT", "OBSERVE", "EXTRACT"}


def _validate_decision(candidate: Dict[str, Any], req: ReasoningRequest) -> AgentDecision:
    if not isinstance(candidate, dict):
        raise ValueError("decision must be a JSON object")

    action = str(candidate.get("action", "")).upper().strip()
    if action not in _KNOWN_ACTIONS:
        raise ValueError(f"unknown action '{action}'")

    target = candidate.get("target") or None
    value = candidate.get("value")
    if value is not None:
        value = str(value)

    # Target rules
    if action in _ACTIONS_NEEDING_TARGET:
        if not target:
            raise ValueError(f"{action} requires 'target'")
        target = str(target)
        if _ELEMENT_RE.match(target):
            known_ids = {
                str(e.get("element_id"))
                for e in req.interactive_elements
                if e.get("element_id") is not None
            }
            if known_ids and target not in known_ids:
                raise ValueError(f"target {target} not present in current observation")
        else:
            raise ValueError(f"{action} target must be an el_N id from the observation, got '{target}'")
    elif action in ("NAVIGATE", "OPEN_TAB"):
        if not target or not _URL_RE.match(str(target)):
            raise ValueError(f"{action} requires an http(s) URL target")
        target = str(target)
    elif action == "SWITCH_TAB":
        if not target:
            raise ValueError("SWITCH_TAB requires a tab_id target")
        target = str(target)
        # Models sometimes echo the prompt's "- tab <uuid>" listing format.
        m = re.match(r"^tab\s+([0-9a-fA-F-]{8,})\s*$", target)
        if m:
            target = m.group(1)
    elif target is not None:
        target = str(target)

    # Value rules
    if action == "TYPE" and not value:
        raise ValueError("TYPE requires non-empty 'value'")
    if action == "PRESS_KEY" and not value:
        raise ValueError("PRESS_KEY requires the key name in 'value' (e.g. Enter, Home)")
    if action == "ANSWER" and not value:
        raise ValueError("ANSWER requires the answer text in 'value'")
    if action in ("ASK_USER", "WAIT_FOR_USER") and not (candidate.get("message") or value):
        raise ValueError(f"{action} requires 'message'")

    # Sensitive-field typing guard (mirrors the Rust-side hard block)
    typed_element: Dict[str, Any] = {}
    if action in ("TYPE", "CLICK", "SELECT"):
        typed_element = next(
            (e for e in req.interactive_elements if str(e.get("element_id")) == target), {}
        )
    if action == "TYPE":
        if typed_element.get("sensitive"):
            raise ValueError("refusing to automate typing into a sensitive field — use WAIT_FOR_USER")
        role = str(typed_element.get("role", "")).lower()
        tag = str(typed_element.get("tag", "")).lower()
        typeable = role in _TYPEABLE_ROLES or tag in {"input", "textarea"} or role == "searchbox"
        if typed_element and not typeable:
            raise ValueError(
                f"TYPE target {target} is a {role or tag or 'non-input'} element — "
                "only textbox/searchbox/textarea roles accept text. Pick the search input instead."
            )

    # Evidence-gated completion: research-style goals must bring their facts.
    if action == "DONE":
        ev_raw = candidate.get("evidence") or []
        if not isinstance(ev_raw, list):
            ev_raw = []
        total_evidence_count = len(ev_raw) + len(req.accumulated_evidence or [])
        if _RESEARCH_GOAL_RE.search(req.goal or "") and total_evidence_count == 0:
            raise ValueError(
                "DONE rejected: this goal needs collected evidence. Include an "
                "'evidence' array of {label,value,source} items for every fact "
                "(prices, names, options with their URLs) — or continue working."
            )

    effect_raw = candidate.get("expected_effect") or {}
    if not isinstance(effect_raw, dict):
        effect_raw = {}
    etype = str(effect_raw.get("type", "none")).lower()
    if etype not in _KNOWN_EFFECTS:
        raise ValueError(f"unknown expected_effect.type '{etype}'")
    if action in _OBSERVATION_ONLY_ACTIONS:
        etype = "none"
    elif etype == "none":
        default = _EFFECT_BY_ACTION.get(action, "none")
        etype = default  # force a checkable postcondition where one naturally exists
    effect = ExpectedEffect(
        type=etype,  # type: ignore[arg-type]
        target=(effect_raw.get("target") or (value if etype == "value_changed" else target) or None),
        value=(effect_raw.get("value") or (value if etype in ("value_changed", "url_contains", "text_present") else None)),
    )

    sensitive_flag = bool(candidate.get("requires_approval", False))
    blob = f"{(candidate.get('reason') or '')} {(candidate.get('message') or '')}".lower()
    if any(h in blob for h in _SENSITIVE_HINTS):
        sensitive_flag = True

    evidence = []
    for item in (candidate.get("evidence") or [])[:12]:
        if isinstance(item, dict) and item.get("label") and item.get("value"):
            evidence.append(EvidenceItem(
                label=str(item["label"])[:80],
                value=str(item["value"])[:200],
                source=str(item.get("source") or "")[:300],
            ))

    progress = candidate.get("progress_estimate")
    try:
        progress = max(0, min(100, int(progress))) if progress is not None else None
    except (TypeError, ValueError):
        progress = None

    return AgentDecision(
        action=action,  # type: ignore[arg-type]
        target=target,
        value=value,
        reason=str(candidate.get("reason") or "")[:400],
        expected_effect=effect,
        requires_approval=sensitive_flag,
        message=candidate.get("message"),
        evidence=evidence,
        progress_estimate=progress,
    )


# ---------------------------------------------------------------------------
# Context assembly + service
# ---------------------------------------------------------------------------

_MAX_ELEMENTS = 40
_MAX_TEXT_BLOCKS = 8
_TEXT_BLOCK_CHARS = 280


def _build_user_prompt(req: ReasoningRequest) -> str:
    els = []
    for e in req.interactive_elements[:_MAX_ELEMENTS]:
        label = e.get("accessible_name") or e.get("name") or e.get("placeholder") or ""
        bits = [str(e.get("element_id")), str(e.get("role", "?")), repr(str(label)[:60])]
        if e.get("href"):
            bits.append(f"href={e['href'][:80]}")
        if e.get("value"):
            bits.append(f"value={str(e['value'])[:40]!r}")
        if e.get("disabled"):
            bits.append("DISABLED")
        els.append(" | ".join(bits))

    tabs = "\n".join(
        f"- tab {t.tab_id}: {t.url[:70]} {t.title[:40]!r}{' (active)' if t.active else ''}"
        for t in req.tabs[:8]
    ) or "- (single tab)"

    hist = ""
    if req.history:
        lines = []
        for h in req.history[-10:]:
            status = "VERIFIED" if h.verified else ("DISPATCHED-BUT-NOT-VERIFIED" if h.dispatched else "NOT-DISPATCHED")
            fail = ""
            if h.failure:
                fail = f" failure={h.failure.category} attempt={h.failure.attempt}"
                if h.failure.evidence:
                    fail += f" observed={h.failure.evidence[:100]}"
            lines.append(
                f"{h.iteration}. {h.action} {h.target or ''} {'→ ' + (h.value or '')[:50] if h.value else ''} [{status}]"
                + fail
                + (f" note: {h.note[:120]}" if h.note else "")
                + (f" url {h.url_before} → {h.url_after}" if h.url_after and h.url_after != h.url_before else "")
            )
        hist = "\nPREVIOUS STEPS:\n" + "\n".join(lines) + "\n"

    failed_strats = ""
    if req.failed_strategies:
        failed_strats = (
            "\nFAILED STRATEGIES (do NOT repeat these; pick a different route):\n"
            + "\n".join(f"- {s}" for s in req.failed_strategies[-8:])
            + "\n"
        )

    constraints = "".join(f"\nCONSTRAINT: {c}" for c in req.constraints)

    subgoal_str = f"\nACTIVE SUBGOAL: {req.subgoal}\n" if req.subgoal else ""

    evidence_str = ""
    if req.accumulated_evidence:
        ev_lines = []
        agreements = []
        contradictions = []

        for e in req.accumulated_evidence[:15]:
            status_tag = f" [{e.validity}]" if e.validity and e.validity != "CURRENT" else ""
            ev_lines.append(f"- [{e.id or 'ev'}][{e.label}]: {e.value} (source: {e.source}{status_tag})")
            if e.validity == "CONTRADICTED":
                contradictions.append(f"  * Conflict on '{e.label}' from {e.source}: '{e.value}'")

        # Group by label to find explicit agreements
        label_groups: Dict[str, List[EvidenceItem]] = {}
        for e in req.accumulated_evidence:
            lKey = e.label.lower().strip()
            label_groups.setdefault(lKey, []).append(e)

        for lKey, g in label_groups.items():
            if len(g) > 1 and all(x.validity != "CONTRADICTED" for x in g):
                sources = ", ".join(x.source for x in g)
                agreements.append(f"  * Multi-source agreement on '{g[0].label}': '{g[0].value}' (sources: {sources})")

        comparison_block = ""
        if agreements:
            comparison_block += "\nVERIFIED AGREEMENTS BETWEEN SOURCES:\n" + "\n".join(agreements) + "\n"
        if contradictions:
            comparison_block += "\nDETECTED CONTRADICTIONS BETWEEN SOURCES:\n" + "\n".join(contradictions) + "\n"

        evidence_str = (
            "\nACCUMULATED CROSS-TAB EVIDENCE:\n"
            + "\n".join(ev_lines) + "\n"
            + comparison_block
        )

    return (
        f"USER GOAL: {req.goal}\n"
        f"{subgoal_str}"
        f"\nCURRENT PAGE: {req.title!r} ({req.url}) readyState={req.ready_state}\n"
        f"PERCEPTION LEVEL: {req.observation_level}"
        + (" (fallback active — primary DOM extraction was empty)" if req.observation_level != "dom" else "")
        + "\n"
        f"HEADINGS: {'; '.join(h[:80] for h in req.headings[:10]) or '(none)'}\n"
        f"PAGE TEXT (excerpt):\n" +
        ("\n".join(f"- {t[:_TEXT_BLOCK_CHARS]}" for t in req.text_blocks[:_MAX_TEXT_BLOCKS]) or "- (none)")
        + "\n"
        f"{evidence_str}"
        f"\nOPEN TABS:\n{tabs}\n"
        f"\nINTERACTIVE ELEMENTS (el_N | role | label):\n" + ("\n".join(els) or "(none detected)") + "\n"
        f"{hist}{failed_strats}{constraints}\n"
        "Decide the single best next step. If history shows repeated failures, change strategy now. Reply with ONLY the JSON decision."
    )


class BrowserStepReasoner:
    """Stateless per-iteration reasoning service (the Harness brain)."""

    def __init__(self) -> None:
        self._last_provider_note = ""

    async def reason_next_step(self, req: ReasoningRequest) -> AgentDecision:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(req)},
        ]
        decision, raw = await call_llm_structured(
            messages,
            validate=lambda c: _validate_decision(c, req),
            max_attempts=4,
            temperature=0.1,
        )
        print(
            f"[HARNESS_TRACE] decision={decision.action} target={decision.target} "
            f"effect={decision.expected_effect.type}:{decision.expected_effect.target} "
            f"approval={decision.requires_approval} reason={decision.reason[:120]!r}",
            flush=True,
        )
        return decision


browser_step_reasoner = BrowserStepReasoner()
