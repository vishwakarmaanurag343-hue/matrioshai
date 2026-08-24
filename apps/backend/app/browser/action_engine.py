"""
MATRIOSHAI Safe Browser Action Engine (Phase 8)

Deterministic, observable, validated, and policy-governed action execution layer
between AI planning and the Chrome Browser.
"""

import time
import secrets
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from app.core.logging import logger
from app.browser.state_store import (
    browser_state_store,
    ActionIntent,
    ActionType,
    ActionTarget,
    ActionPrecondition,
    ActionPostcondition,
    ActionPolicyCategory,
    PolicyDecision,
    ActionStatus,
    ActionConfirmationRequest,
    ActionConfirmationResponse,
    ActionTraceStep,
    ActionTrace,
    ActionErrorDetail,
    ActionResult,
    ActionQueueItem,
    ActionQueueStatus,
    WorldElement,
    WorldElementRef,
    WorldPageState,
    BrowserWorldModel
)
from app.browser.world_model import world_model_engine

class TargetResolver:
    """
    Resolves ActionTarget references against the current World Model.
    """

    def __init__(self, state_store=None):
        self.state_store = state_store or browser_state_store

    def resolve_target(
        self,
        target: Optional[ActionTarget],
        tab_id: int,
        page_version: int,
        page_id: Optional[str] = None
    ) -> Tuple[str, Optional[WorldElement], List[WorldElementRef], Optional[str]]:
        """
        Resolves action target returning (status, resolved_element, candidates, message).
        Possible statuses: FOUND, NOT_FOUND, AMBIGUOUS, STALE, INVISIBLE, DISABLED, OCCLUDED, WRONG_PAGE, WRONG_TAB.
        """
        store = self.state_store
        if tab_id not in store.tabs:
            return "WRONG_TAB", None, [], f"Target tab {tab_id} is not open."

        current_page = store.page_states.get(tab_id)

        # 1. Page identity check
        if current_page and page_id and current_page.page_id != page_id:
            return "WRONG_PAGE", None, [], f"Page ID mismatch: requested '{page_id}', current is '{current_page.page_id}'."

        # 2. Page version check
        if current_page and page_version < current_page.page_version:
            elements = store.world_elements.get(tab_id, [])
            candidates = [el.element_ref for el in elements]
            return "STALE", None, candidates, f"Page version v{page_version} is stale (current v{current_page.page_version})."

        if not target:
            return "NOT_FOUND", None, [], "No target specified."

        elements = store.world_elements.get(tab_id, [])

        # 3. Exact WorldElementRef match
        if target.world_element_ref and target.world_element_ref.element_id:
            exact = next((el for el in elements if el.element_ref.element_id == target.world_element_ref.element_id), None)
            if exact:
                if not exact.visible:
                    return "INVISIBLE", exact, [exact.element_ref], "Target element is not visible in viewport."
                if not exact.enabled:
                    return "DISABLED", exact, [exact.element_ref], "Target element is disabled."
                return "FOUND", exact, [exact.element_ref], "Resolved via exact WorldElementRef."

        # 4. Stable DOM identity lookup (e.g. id attribute)
        stable_id = None
        if target.world_element_ref and target.world_element_ref.stable_dom_identity:
            stable_id = target.world_element_ref.stable_dom_identity
        elif target.semantic_element_ref and target.semantic_element_ref.stable_id:
            stable_id = target.semantic_element_ref.stable_id

        if stable_id:
            matches = [el for el in elements if el.element_ref.stable_dom_identity == stable_id]
            if len(matches) == 1:
                return "FOUND", matches[0], [matches[0].element_ref], f"Resolved via stable DOM ID #{stable_id}."
            elif len(matches) > 1:
                return "AMBIGUOUS", None, [m.element_ref for m in matches], f"Multiple elements match stable ID #{stable_id}."

        # 5. Role + Accessible Name search
        exp_role = target.expected_role or (target.world_element_ref.role if target.world_element_ref else None)
        exp_name = target.expected_name or (target.world_element_ref.name if target.world_element_ref else None)

        if exp_role and exp_name:
            matches = [
                el for el in elements
                if el.role.lower() == exp_role.lower() and el.name.strip().lower() == exp_name.strip().lower()
            ]
            if len(matches) == 1:
                return "FOUND", matches[0], [matches[0].element_ref], f"Resolved via role='{exp_role}' and name='{exp_name}'."
            elif len(matches) > 1:
                return "AMBIGUOUS", None, [m.element_ref for m in matches], f"Found {len(matches)} elements matching role='{exp_role}' and name='{exp_name}'."

        # 6. Raw coordinate fallback check
        if target.coordinates and target.allow_coordinate_fallback:
            x = target.coordinates.get("x", 0)
            y = target.coordinates.get("y", 0)
            if current_page:
                if 0 <= x <= current_page.viewport_width and 0 <= y <= current_page.viewport_height:
                    return "FOUND", None, [], f"Resolved via validated coordinates ({x}, {y})."
                else:
                    return "NOT_FOUND", None, [], f"Coordinates ({x}, {y}) are outside viewport."
            return "FOUND", None, [], f"Resolved via coordinates ({x}, {y})."

        return "NOT_FOUND", None, [], "Could not resolve target element."

class ActionValidator:
    """
    Validates schema, versions, preconditions, and safety constraints.
    """

    def __init__(self, state_store=None):
        self.state_store = state_store or browser_state_store
        self.target_resolver = TargetResolver(self.state_store)

    def validate_intent(self, intent: ActionIntent) -> Tuple[bool, Optional[str], Optional[ActionErrorDetail]]:
        """
        Validates ActionIntent against schema, current world version, and preconditions.
        """
        store = self.state_store

        # 1. Action type validation
        if not intent.type:
            return False, "INVALID_ACTION: Action type is required", ActionErrorDetail(code="INVALID_ACTION", message="Action type required")

        # 2. Tab validation
        tab_id = intent.tab_id or store.active_tab_id
        if not tab_id or tab_id not in store.tabs:
            return False, f"WRONG_TAB: Tab {tab_id} is not open", ActionErrorDetail(code="WRONG_TAB", message=f"Tab {tab_id} is closed", requires_replan=True)

        # 3. World version check
        if intent.world_model_version < store.world_model_version:
            # If world advanced significantly, check if page version also changed
            current_page = store.page_states.get(tab_id)
            if current_page and intent.page_version < current_page.page_version:
                return False, f"STALE_WORLD: Intent world v{intent.world_model_version} / page v{intent.page_version} is stale (current world v{store.world_model_version} / page v{current_page.page_version})", ActionErrorDetail(code="STALE_WORLD", message="World state changed", requires_replan=True)

        # 4. Parameters validation
        if intent.type == ActionType.TYPE:
            text = intent.parameters.get("text") if intent.parameters else None
            value = intent.parameters.get("value") if intent.parameters else None
            if text is None and value is None:
                return False, "INVALID_ACTION: TYPE action requires 'text' parameter", ActionErrorDetail(code="INVALID_ACTION", message="TYPE requires text parameter")

        elif intent.type == ActionType.NAVIGATE:
            url = intent.parameters.get("url") if intent.parameters else (intent.target.url if intent.target else None)
            if not url:
                return False, "INVALID_ACTION: NAVIGATE action requires 'url'", ActionErrorDetail(code="INVALID_ACTION", message="NAVIGATE requires url")
            if url.startswith("javascript:") or url.startswith("data:") or url.startswith("file:"):
                return False, f"POLICY_BLOCKED: Dangerous URL scheme in '{url}'", ActionErrorDetail(code="POLICY_BLOCKED", message="Dangerous URL scheme")

        elif intent.type == ActionType.KEY_PRESS:
            key = intent.parameters.get("key") if intent.parameters else None
            if not key:
                return False, "INVALID_ACTION: KEY_PRESS requires 'key' parameter", ActionErrorDetail(code="INVALID_ACTION", message="KEY_PRESS requires key parameter")

        # 5. Precondition evaluation
        for pre in intent.preconditions:
            res, err = self.evaluate_precondition(pre, tab_id)
            if not res:
                return False, f"PRECONDITION_FAILED: {err}", ActionErrorDetail(code="PRECONDITION_FAILED", message=err or "Precondition failed", requires_replan=True)

        return True, None, None

    def evaluate_precondition(self, pre: ActionPrecondition, tab_id: int) -> Tuple[bool, Optional[str]]:
        store = self.state_store
        current_page = store.page_states.get(tab_id)

        if pre.type == "PAGE_VERSION_MATCHES":
            if current_page and current_page.page_version != pre.expected_value:
                return False, f"Page version expected v{pre.expected_value}, found v{current_page.page_version}"

        elif pre.type == "URL_MATCHES":
            tab = store.tabs.get(tab_id)
            if tab and pre.expected_value and pre.expected_value not in tab.url:
                return False, f"URL does not contain '{pre.expected_value}'"

        elif pre.type == "DIALOG_PRESENT":
            if not current_page or not current_page.active_dialogs:
                return False, "Expected dialog to be present, but no dialogs open"

        elif pre.type == "DIALOG_ABSENT":
            if current_page and current_page.active_dialogs:
                return False, f"Expected no dialogs, but found {len(current_page.active_dialogs)} open"

        return True, None

class ActionPolicyEngine:
    """
    Evaluates safety policies and gates high-impact or sensitive actions.
    """

    def __init__(self, state_store=None):
        self.state_store = state_store or browser_state_store

    def evaluate_policy(self, intent: ActionIntent) -> Tuple[PolicyDecision, ActionPolicyCategory, Optional[str]]:
        """
        Categorizes action into SAFE, SENSITIVE, HIGH_IMPACT, or BLOCKED.
        """
        target_name = (intent.target.expected_name or "").lower() if intent.target else ""
        target_role = (intent.target.expected_role or "").lower() if intent.target else ""

        # 1. BLOCKED Category: Dangerous schemes or arbitrary code execution
        if intent.type == ActionType.NAVIGATE:
            url = str(intent.parameters.get("url", "") if intent.parameters else (intent.target.url if intent.target else ""))
            if url.startswith("javascript:") or url.startswith("data:") or url.startswith("file:"):
                return PolicyDecision.BLOCK, ActionPolicyCategory.BLOCKED, "Dangerous scheme is strictly blocked"

        # 2. HIGH_IMPACT Category: Purchases, booking confirmations, financial transactions, permanent deletions
        high_impact_keywords = [
            "buy now", "confirm purchase", "place order", "pay now", "complete payment",
            "book flight", "delete account", "transfer money", "submit application"
        ]
        if intent.type == ActionType.CLICK and any(kw in target_name for kw in high_impact_keywords):
            return PolicyDecision.REQUIRE_CONFIRMATION, ActionPolicyCategory.HIGH_IMPACT, f"Action '{intent.type}' on '{target_name}' is high impact and requires user confirmation"

        # 3. SENSITIVE Category: Password, credentials, card details
        is_sensitive = False
        if intent.parameters and (intent.parameters.get("sensitive") or intent.parameters.get("value_redacted")):
            is_sensitive = True
        if "password" in target_name or "credit card" in target_name or "cvv" in target_name:
            is_sensitive = True

        if is_sensitive:
            return PolicyDecision.ALLOW, ActionPolicyCategory.SENSITIVE, "Action permitted with sensitive parameter redaction"

        # 4. SAFE Category: Default
        return PolicyDecision.ALLOW, ActionPolicyCategory.SAFE, "Standard safe action allowed"

    def create_confirmation_request(self, intent: ActionIntent, summary: str) -> ActionConfirmationRequest:
        conf = ActionConfirmationRequest(
            confirmation_id=f"conf_{secrets.token_hex(4)}",
            action_id=intent.action_id,
            action_type=intent.type,
            target_description=intent.target.expected_name if intent.target else "Target",
            impact_level=ActionPolicyCategory.HIGH_IMPACT,
            summary=summary,
            status="PENDING"
        )
        self.state_store.pending_confirmations[conf.confirmation_id] = conf
        return conf

class ActionQueueManager:
    """
    Manages per-tab serial FIFO execution queues and conflict detection.
    """

    def __init__(self, state_store=None):
        self.state_store = state_store or browser_state_store
        self._locks: Dict[int, asyncio.Lock] = {}

    def get_tab_lock(self, tab_id: int) -> asyncio.Lock:
        if tab_id not in self._locks:
            self._locks[tab_id] = asyncio.Lock()
        return self._locks[tab_id]

    def enqueue_action(self, intent: ActionIntent, tab_id: int):
        if tab_id not in self.state_store.tab_action_queues:
            self.state_store.tab_action_queues[tab_id] = []
        self.state_store.tab_action_queues[tab_id].append(intent)

    def dequeue_action(self, tab_id: int) -> Optional[ActionIntent]:
        if tab_id in self.state_store.tab_action_queues and self.state_store.tab_action_queues[tab_id]:
            return self.state_store.tab_action_queues[tab_id].pop(0)
        return None

    def get_queue_status(self, tab_id: int) -> ActionQueueStatus:
        items = [
            ActionQueueItem(intent=intent, status="QUEUED")
            for intent in self.state_store.tab_action_queues.get(tab_id, [])
        ]
        return ActionQueueStatus(
            tab_id=tab_id,
            is_locked=self.state_store.tab_execution_locks.get(tab_id, False),
            active_action_id=None,
            queue_length=len(items),
            items=items
        )

    def clear_queue_on_conflict(self, tab_id: int, reason: str):
        if tab_id in self.state_store.tab_action_queues:
            count = len(self.state_store.tab_action_queues[tab_id])
            self.state_store.tab_action_queues[tab_id].clear()
            if count > 0:
                logger.info(f"[MATRIOSHAI][ActionQueue] Invalidated {count} queued actions on tab {tab_id} due to conflict: {reason}")

class ActionEngine:
    """
    Unified Safe Browser Action Engine orchestrator.
    """

    def __init__(self, state_store=None, bridge_server=None):
        self.state_store = state_store or browser_state_store
        self.target_resolver = TargetResolver(self.state_store)
        self.validator = ActionValidator(self.state_store)
        self.policy_engine = ActionPolicyEngine(self.state_store)
        self.queue_manager = ActionQueueManager(self.state_store)
        self.bridge_server = bridge_server

    def redact_sensitive_intent(self, intent: ActionIntent) -> ActionIntent:
        """
        Ensure sensitive values (e.g. passwords) are redacted before logging or tracing.
        """
        if not intent.parameters:
            return intent

        params = dict(intent.parameters)
        target_name = (intent.target.expected_name or "").lower() if intent.target else ""

        is_sensitive = (
            params.get("sensitive") or
            "password" in target_name or
            "credit card" in target_name or
            "cvv" in target_name
        )

        if is_sensitive:
            if "text" in params:
                params["text"] = "[REDACTED]"
            if "value" in params:
                params["value"] = "[REDACTED]"
            params["value_redacted"] = True

        sanitized = intent.model_copy(deep=True)
        sanitized.parameters = params
        return sanitized

    async def execute_action(
        self,
        intent: ActionIntent,
        confirmed: bool = False
    ) -> ActionResult:
        """
        Main execution pipeline:
        Intent -> Validation -> Target Resolution -> Policy -> Confirmation Gate -> Executor -> ActionResult.
        """
        start_time = time.time()
        start_iso = datetime.now(timezone.utc).isoformat()
        store = self.state_store
        tab_id = intent.tab_id or store.active_tab_id or 1
        world_version_before = store.world_model_version

        trace_steps: List[ActionTraceStep] = [
            ActionTraceStep(stage="ACTION_CREATED", status="PASS", detail=f"Action {intent.action_id} ({intent.type}) submitted")
        ]

        # 1. Validate Schema & Preconditions
        val_ok, val_err, err_detail = self.validator.validate_intent(intent)
        if not val_ok:
            trace_steps.append(ActionTraceStep(stage="SCHEMA_VALIDATED", status="FAIL", detail=val_err))
            return self._build_result(
                intent=intent,
                status=ActionStatus.FAILED,
                start_iso=start_iso,
                start_time=start_time,
                world_before=world_version_before,
                trace_steps=trace_steps,
                error=err_detail or ActionErrorDetail(code="INVALID_ACTION", message=val_err or "Validation failed")
            )
        trace_steps.append(ActionTraceStep(stage="SCHEMA_VALIDATED", status="PASS", detail="Intent schema and world version verified"))

        # 2. Target Resolution (if element action)
        resolved_element = None
        if intent.type not in [ActionType.NAVIGATE, ActionType.WAIT]:
            res_status, resolved_el, candidates, res_msg = self.target_resolver.resolve_target(
                target=intent.target,
                tab_id=tab_id,
                page_version=intent.page_version,
                page_id=intent.page_id
            )

            if res_status != "FOUND":
                trace_steps.append(ActionTraceStep(stage="TARGET_RESOLVED", status="FAIL", detail=f"{res_status}: {res_msg}"))
                if res_status == "NOT_FOUND":
                    act_status = ActionStatus.NOT_FOUND
                elif res_status == "AMBIGUOUS":
                    act_status = ActionStatus.AMBIGUOUS
                elif res_status == "STALE":
                    act_status = ActionStatus.STALE
                else:
                    act_status = ActionStatus.FAILED

                return self._build_result(
                    intent=intent,
                    status=act_status,
                    start_iso=start_iso,
                    start_time=start_time,
                    world_before=world_version_before,
                    trace_steps=trace_steps,
                    error=ActionErrorDetail(code=res_status, message=res_msg or "Target resolution failed", requires_replan=True)
                )

            resolved_element = resolved_el
            trace_steps.append(ActionTraceStep(stage="TARGET_RESOLVED", status="PASS", detail=res_msg))

        # 3. Policy Evaluation
        decision, category, policy_msg = self.policy_engine.evaluate_policy(intent)
        trace_steps.append(ActionTraceStep(stage="POLICY_EVALUATED", status="PASS" if decision == PolicyDecision.ALLOW else "BLOCKED", detail=f"Category {category.value}: {policy_msg}"))

        if decision == PolicyDecision.BLOCK:
            return self._build_result(
                intent=intent,
                status=ActionStatus.BLOCKED,
                start_iso=start_iso,
                start_time=start_time,
                world_before=world_version_before,
                trace_steps=trace_steps,
                error=ActionErrorDetail(code="POLICY_BLOCKED", message=policy_msg or "Action blocked by safety policy")
            )

        if decision == PolicyDecision.REQUIRE_CONFIRMATION and not confirmed:
            conf_req = self.policy_engine.create_confirmation_request(intent, policy_msg or "Action requires confirmation")
            trace_steps.append(ActionTraceStep(stage="CONFIRMATION_CHECKED", status="BLOCKED", detail=f"Pending confirmation {conf_req.confirmation_id}"))
            return self._build_result(
                intent=intent,
                status=ActionStatus.REQUIRES_CONFIRMATION,
                start_iso=start_iso,
                start_time=start_time,
                world_before=world_version_before,
                trace_steps=trace_steps,
                execution_meta={"confirmation_id": conf_req.confirmation_id, "confirmation_request": conf_req.model_dump()}
            )

        # 4. Dry-run Mode Check
        if intent.parameters and intent.parameters.get("dry_run"):
            trace_steps.append(ActionTraceStep(stage="EXECUTION_COMPLETED", status="PASS", detail="Dry-run completed successfully"))
            return self._build_result(
                intent=intent,
                status=ActionStatus.WOULD_EXECUTE,
                start_iso=start_iso,
                start_time=start_time,
                world_before=world_version_before,
                trace_steps=trace_steps,
                execution_meta={"dry_run": True}
            )

        # 5. Serialized Execution via Tab Lock
        tab_lock = self.queue_manager.get_tab_lock(tab_id)
        async with tab_lock:
            trace_steps.append(ActionTraceStep(stage="EXECUTION_STARTED", status="PASS", detail=f"Acquired execution lock for tab {tab_id}"))

            # Execute via Bridge or Local simulation
            exec_status, exec_msg, exec_meta = await self._dispatch_execution(intent, tab_id)
            trace_steps.append(ActionTraceStep(stage="DOM_DISPATCHED", status="PASS" if exec_status == ActionStatus.SUCCESS or exec_status == ActionStatus.NO_OP else "FAIL", detail=exec_msg))

            # Bump world model version on state-modifying actions
            if exec_status == ActionStatus.SUCCESS and intent.type in [ActionType.CLICK, ActionType.TYPE, ActionType.NAVIGATE, ActionType.SELECT, ActionType.CHECK, ActionType.UNCHECK]:
                store.world_model_version += 1

            world_version_after = store.world_model_version
            trace_steps.append(ActionTraceStep(stage="EXECUTION_COMPLETED", status="PASS", detail=f"Finished with status {exec_status.value}"))

            result = self._build_result(
                intent=intent,
                status=exec_status,
                start_iso=start_iso,
                start_time=start_time,
                world_before=world_version_before,
                world_after=world_version_after,
                trace_steps=trace_steps,
                execution_meta=exec_meta,
                error=None if exec_status in [ActionStatus.SUCCESS, ActionStatus.NO_OP] else ActionErrorDetail(code="EXECUTION_FAILED", message=exec_msg)
            )

            # Record in action history
            store.action_history.append(result)
            if len(store.action_history) > store.MAX_ACTION_HISTORY:
                store.action_history.pop(0)

            return result

    async def _dispatch_execution(
        self,
        intent: ActionIntent,
        tab_id: int
    ) -> Tuple[ActionStatus, str, Dict[str, Any]]:
        """
        Dispatch execution to Chrome Bridge or fallback local simulator.
        """
        store = self.state_store

        # If bridge is available, send request
        if self.bridge_server and hasattr(self.bridge_server, "send_request") and self.bridge_server.is_ready():
            try:
                resp = await self.bridge_server.send_request(
                    "action.execute",
                    {"tab_id": tab_id, "intent": intent.model_dump()},
                    timeout_seconds=(intent.timeout_ms or 5000) / 1000.0
                )
                raw_status = resp.get("status", "SUCCESS")
                status = ActionStatus(raw_status) if raw_status in ActionStatus._value2member_map_ else ActionStatus.SUCCESS
                return status, resp.get("message", "Action dispatched to bridge"), resp
            except Exception as e:
                logger.warning(f"[MATRIOSHAI][ActionEngine] Bridge action execution error: {e}")
                return ActionStatus.FAILED, f"Bridge execution error: {str(e)}", {}

        # Local simulation mode (for unit tests / mock environment)
        if intent.type == ActionType.NAVIGATE:
            url = str(intent.parameters.get("url", "") if intent.parameters else (intent.target.url if intent.target else ""))
            if tab_id in store.tabs:
                store.tabs[tab_id].url = url
            return ActionStatus.SUCCESS, f"Navigated tab {tab_id} to {url}", {"url": url}

        elif intent.type == ActionType.WAIT:
            dur = (intent.parameters.get("duration_ms", 100) if intent.parameters else 100) / 1000.0
            await asyncio.sleep(min(dur, 1.0))
            return ActionStatus.SUCCESS, f"Waited {dur}s", {}

        elif intent.type == ActionType.CHECK:
            return ActionStatus.SUCCESS, "Checked element", {}

        elif intent.type == ActionType.UNCHECK:
            return ActionStatus.SUCCESS, "Unchecked element", {}

        return ActionStatus.SUCCESS, f"Simulated {intent.type.value} action successfully", {}

    def _build_result(
        self,
        intent: ActionIntent,
        status: ActionStatus,
        start_iso: str,
        start_time: float,
        world_before: int,
        trace_steps: List[ActionTraceStep],
        world_after: Optional[int] = None,
        execution_meta: Optional[Dict[str, Any]] = None,
        error: Optional[ActionErrorDetail] = None
    ) -> ActionResult:
        now = datetime.now(timezone.utc).isoformat()
        dur = round((time.time() - start_time) * 1000, 2)
        sanitized_intent = self.redact_sensitive_intent(intent)

        meta = dict(execution_meta or {})
        if sanitized_intent.parameters:
            meta["parameters"] = sanitized_intent.parameters

        trace = ActionTrace(
            action_id=intent.action_id,
            steps=trace_steps,
            started_at=start_iso,
            completed_at=now
        )
        self.state_store.action_traces[intent.action_id] = trace

        return ActionResult(
            action_id=intent.action_id,
            type=intent.type,
            status=status,
            started_at=start_iso,
            completed_at=now,
            duration_ms=dur,
            world_model_version_before=world_before,
            world_model_version_after=world_after or world_before,
            target=sanitized_intent.target,
            trace=trace,
            expected_postconditions=intent.postconditions or [],
            execution_metadata=meta,
            error=error
        )

action_engine = ActionEngine()
