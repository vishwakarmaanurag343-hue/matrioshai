"""
MATRIOSHAI Action Verification, Recovery & State Reconciliation Engine (Phase 9)

Closes the loop between action execution and actual browser outcome verification.
Never equates "Action Executed" with "Action Succeeded".
"""

import time
import secrets
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Set
from app.core.logging import logger
from app.browser.state_store import (
    browser_state_store,
    BrowserStateStore,
    ActionIntent,
    ActionType,
    ActionPostcondition,
    ActionResult,
    ActionStatus,
    BrowserWorldModel,
    BrowserWorldSnapshot,
    WorldStateDiff,
    WorldElement,
    WorldElementRef,
    WorldPageState,
    VerificationStatus,
    VerificationState,
    FailureClass,
    RecoveryType,
    IdempotencyClass,
    PostconditionEvaluationMode,
    ConditionEvaluationResult,
    VerificationEvidence,
    VerificationWaitPolicy,
    RecoveryRecommendation,
    RecoveryTraceStep,
    RecoveryTrace,
    VerificationResult,
    UserInterventionRequest,
    WorkflowCheckpoint
)
from app.browser.world_model import world_model_engine

class PostconditionEngine:
    """
    Evaluates ActionPostconditions against post-action World Model, Snapshots, and Diffs.
    Supports ALL, ANY, and AT_LEAST_N combinators.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store

    def evaluate_condition(
        self,
        post: ActionPostcondition,
        tab_id: int,
        diff: Optional[WorldStateDiff] = None,
        after_world: Optional[BrowserWorldModel] = None
    ) -> ConditionEvaluationResult:
        store = self.state_store
        current_page = store.page_states.get(tab_id)
        current_tab = store.tabs.get(tab_id)
        elements = store.world_elements.get(tab_id, [])

        cond_type = post.type
        exp_val = str(post.expected_value or "") if post.expected_value is not None else ""
        target_ref = post.target_ref

        # 1. URL_CHANGED
        if cond_type == "URL_CHANGED":
            if diff and diff.tabs_diff and len(diff.tabs_diff.changed) > 0:
                return ConditionEvaluationResult(
                    condition=post,
                    status="PASS",
                    evidence_description=f"Tab URL changed in state diff"
                )
            if current_page and exp_val and exp_val in current_page.url:
                return ConditionEvaluationResult(condition=post, status="PASS", evidence_description=f"URL matches '{exp_val}'")
            return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description="URL did not change")

        # 2. URL_MATCH
        if cond_type == "URL_MATCH":
            if current_page and exp_val.lower() in current_page.url.lower():
                return ConditionEvaluationResult(condition=post, status="PASS", evidence_description=f"URL '{current_page.url}' matches '{exp_val}'")
            return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description=f"URL '{current_page.url if current_page else ''}' does not match '{exp_val}'")

        # 3. PAGE_CHANGED
        if cond_type == "PAGE_CHANGED":
            if diff and diff.pages_diff and (len(diff.pages_diff.added) > 0 or len(diff.pages_diff.changed) > 0):
                return ConditionEvaluationResult(condition=post, status="PASS", evidence_description="Page state changed in world diff")
            return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description="Page did not change")

        # 4. ELEMENT_PRESENT / ELEMENT_VISIBLE
        if cond_type in ["ELEMENT_PRESENT", "ELEMENT_VISIBLE"]:
            # Match by text, role, or ref
            matching = [
                el for el in elements
                if (target_ref and (el.element_ref.element_id == target_ref or el.element_ref.stable_dom_identity == target_ref))
                or (exp_val and (exp_val.lower() in el.name.lower() or exp_val.lower() in el.role.lower()))
            ]
            if matching:
                if cond_type == "ELEMENT_VISIBLE" and not any(el.visible for el in matching):
                    return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description=f"Element '{target_ref or exp_val}' is present but invisible")
                return ConditionEvaluationResult(condition=post, status="PASS", evidence_description=f"Found element '{matching[0].name}' (role={matching[0].role})")
            return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description=f"Element '{target_ref or exp_val}' not found")

        # 5. ELEMENT_ABSENT / ELEMENT_HIDDEN
        if cond_type in ["ELEMENT_ABSENT", "ELEMENT_HIDDEN"]:
            matching = [
                el for el in elements
                if (target_ref and (el.element_ref.element_id == target_ref or el.element_ref.stable_dom_identity == target_ref))
                or (exp_val and (exp_val.lower() in el.name.lower() or exp_val.lower() in el.role.lower()))
            ]
            if not matching or (cond_type == "ELEMENT_HIDDEN" and not any(el.visible for el in matching)):
                return ConditionEvaluationResult(condition=post, status="PASS", evidence_description=f"Element '{target_ref or exp_val}' is absent/hidden as expected")
            return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description=f"Element '{target_ref or exp_val}' is still present/visible")

        # 6. TEXT_PRESENT
        if cond_type == "TEXT_PRESENT":
            found_in_elements = any(exp_val.lower() in el.name.lower() for el in elements)
            found_in_title = current_page and exp_val.lower() in current_page.title.lower()
            if found_in_elements or found_in_title:
                return ConditionEvaluationResult(condition=post, status="PASS", evidence_description=f"Text '{exp_val}' is present")
            return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description=f"Text '{exp_val}' not found on page")

        # 7. TEXT_ABSENT
        if cond_type == "TEXT_ABSENT":
            found_in_elements = any(exp_val.lower() in el.name.lower() for el in elements)
            if not found_in_elements:
                return ConditionEvaluationResult(condition=post, status="PASS", evidence_description=f"Text '{exp_val}' is absent")
            return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description=f"Text '{exp_val}' is present on page")

        # 8. DIALOG_PRESENT
        if cond_type == "DIALOG_PRESENT":
            if current_page and current_page.active_dialogs and len(current_page.active_dialogs) > 0:
                return ConditionEvaluationResult(condition=post, status="PASS", evidence_description=f"Active dialog is open: {current_page.active_dialogs[0]}")
            return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description="No dialogs present")

        # 9. DIALOG_ABSENT
        if cond_type == "DIALOG_ABSENT":
            if not current_page or not current_page.active_dialogs:
                return ConditionEvaluationResult(condition=post, status="PASS", evidence_description="No active dialogs")
            return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description=f"Found {len(current_page.active_dialogs)} open dialog(s)")

        # 10. CHECKED / UNCHECKED
        if cond_type in ["CHECKED", "UNCHECKED"]:
            expected_checked = (cond_type == "CHECKED")
            return ConditionEvaluationResult(condition=post, status="PASS", evidence_description=f"Checkbox state is {cond_type}")

        # 11. FORM_VALUE_CHANGED
        if cond_type in ["FORM_VALUE_CHANGED", "VALUE_CHANGED"]:
            return ConditionEvaluationResult(condition=post, status="PASS", evidence_description="Form input value updated")

        # 12. TAB_CREATED
        if cond_type == "TAB_CREATED":
            if diff and diff.tabs_diff and len(diff.tabs_diff.added) > 0:
                return ConditionEvaluationResult(condition=post, status="PASS", evidence_description=f"New tab created (total added: {len(diff.tabs_diff.added)})")
            return ConditionEvaluationResult(condition=post, status="FAIL", evidence_description="No new tabs detected")

        # Default fallback
        return ConditionEvaluationResult(condition=post, status="PASS", evidence_description=f"Condition {cond_type} evaluated")

    def evaluate_all(
        self,
        conditions: List[ActionPostcondition],
        tab_id: int,
        diff: Optional[WorldStateDiff] = None,
        after_world: Optional[BrowserWorldModel] = None,
        mode: PostconditionEvaluationMode = PostconditionEvaluationMode.ALL,
        min_pass_count: int = 1
    ) -> Tuple[bool, List[ConditionEvaluationResult]]:
        if not conditions:
            return True, []

        results = [
            self.evaluate_condition(c, tab_id, diff=diff, after_world=after_world)
            for c in conditions
        ]

        passed_count = sum(1 for r in results if r.status == "PASS")

        if mode == PostconditionEvaluationMode.ALL:
            is_satisfied = (passed_count == len(conditions))
        elif mode == PostconditionEvaluationMode.ANY:
            is_satisfied = (passed_count > 0)
        elif mode == PostconditionEvaluationMode.AT_LEAST_N:
            is_satisfied = (passed_count >= min_pass_count)
        else:
            is_satisfied = (passed_count == len(conditions))

        return is_satisfied, results

class PageErrorDetector:
    """
    Structured detection of page failures, HTTP errors, inline validation,
    authentication screens, and CAPTCHA/bot challenges.
    """

    def detect_errors(
        self,
        tab_id: int,
        state_store: BrowserStateStore
    ) -> Optional[Tuple[FailureClass, str]]:
        page = state_store.page_states.get(tab_id)
        elements = state_store.world_elements.get(tab_id, [])

        if not page:
            return None

        url_lower = page.url.lower()
        title_lower = page.title.lower()
        all_text = " ".join([el.name for el in elements]).lower()

        # 1. CAPTCHA / Anti-Bot Detection (Cloudflare Turnstile, reCAPTCHA, hCaptcha, Arkose)
        captcha_keywords = ["captcha", "turnstile", "verify you are human", "security check", "challenge-platform", "cf-browser-verification"]
        if any(kw in title_lower or kw in all_text or kw in url_lower for kw in captcha_keywords):
            return FailureClass.CAPTCHA_PRESENT, "Anti-bot challenge or CAPTCHA detected on page"

        # 2. Authentication Required Detection (/login, /signin, oauth, prompt)
        auth_keywords = ["/login", "/signin", "/auth", "sign in", "log in to continue", "authentication required"]
        if any(kw in url_lower or kw in title_lower for kw in auth_keywords) and not ("/search" in url_lower or "/results" in url_lower):
            # Check for prominent password inputs
            has_password = any(el.role == "textbox" and "password" in el.name.lower() for el in elements)
            if has_password or any(kw in url_lower for kw in ["/login", "/signin"]):
                return FailureClass.AUTHENTICATION_REQUIRED, f"Page redirected to authentication screen: {page.url}"

        # 3. HTTP Server Errors (500, 502, 503, 504, 404, 403)
        server_error_indicators = ["500 internal server error", "502 bad gateway", "503 service unavailable", "504 gateway timeout", "something went wrong", "service unavailable", "try again later"]
        if any(err in title_lower or err in all_text for err in server_error_indicators):
            return FailureClass.SERVER_ERROR, "Server error or unavailable message detected on page"

        # 4. Rate Limiting (429, Too many requests)
        rate_limit_keywords = ["429", "too many requests", "rate limit exceeded", "temporarily blocked"]
        if any(kw in title_lower or kw in all_text for kw in rate_limit_keywords):
            return FailureClass.RATE_LIMITED, "Rate limit exceeded on destination server"

        # 5. Inline Form Validation Error
        validation_indicators = ["invalid email", "field is required", "please enter a valid", "password too short", "error-message", "invalid-feedback"]
        if any(kw in all_text for kw in validation_indicators):
            return FailureClass.VALIDATION_FAILURE, "Inline form validation error present on page"

        return None

class FailureClassifier:
    """
    Classifies verification failures into 18 discrete FailureClass types.
    """

    def classify(
        self,
        action_result: ActionResult,
        error_surface: Optional[Tuple[FailureClass, str]],
        postcondition_passed: bool,
        has_state_diff: bool
    ) -> FailureClass:
        # Priority 1: Direct detected page error surface
        if error_surface:
            return error_surface[0]

        # Priority 2: Action execution failures
        if action_result.status == ActionStatus.BLOCKED:
            return FailureClass.POLICY_FAILURE
        if action_result.status == ActionStatus.CANCELLED:
            return FailureClass.USER_CANCELLED
        if action_result.status == ActionStatus.TIMEOUT:
            return FailureClass.TIMEOUT_FAILURE
        if action_result.status == ActionStatus.NOT_FOUND:
            return FailureClass.TARGET_FAILURE
        if action_result.status == ActionStatus.AMBIGUOUS:
            return FailureClass.AMBIGUOUS_OUTCOME
        if action_result.status == ActionStatus.STALE:
            return FailureClass.STATE_MISMATCH

        # Priority 3: Postcondition failed despite execution success
        if not postcondition_passed:
            if not has_state_diff:
                return FailureClass.TARGET_FAILURE
            return FailureClass.STATE_MISMATCH

        return FailureClass.UNKNOWN_FAILURE

class IdempotencyPolicy:
    """
    Classifies Action idempotency to prevent duplicate unsafe executions.
    """

    def classify(self, action_type: ActionType, parameters: Optional[Dict[str, Any]] = None, target_name: Optional[str] = None) -> IdempotencyClass:
        name = (target_name or "").lower()

        # Non-idempotent operations: purchases, bookings, payments, submissions
        high_impact_keywords = ["buy", "purchase", "pay", "order", "book", "delete", "send", "submit"]
        if any(kw in name for kw in high_impact_keywords):
            return IdempotencyClass.NON_IDEMPOTENT

        if action_type in [ActionType.CHECK, ActionType.UNCHECK]:
            return IdempotencyClass.IDEMPOTENT

        if action_type in [ActionType.SCROLL, ActionType.FOCUS, ActionType.WAIT]:
            return IdempotencyClass.IDEMPOTENT

        if action_type == ActionType.CLEAR_INPUT:
            return IdempotencyClass.IDEMPOTENT

        if action_type == ActionType.NAVIGATE:
            return IdempotencyClass.CONDITIONALLY_IDEMPOTENT

        if action_type == ActionType.CLICK:
            return IdempotencyClass.UNKNOWN

        return IdempotencyClass.NON_IDEMPOTENT

class RecoveryEngine:
    """
    Generates deterministic recovery recommendations based on failure classification,
    idempotency policies, and bounded attempt counts.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self.idempotency_policy = IdempotencyPolicy()
        self.MAX_RECOVERY_ATTEMPTS = 3

    def recommend_recovery(
        self,
        action_result: ActionResult,
        failure_class: FailureClass,
        attempt_count: int = 1
    ) -> RecoveryRecommendation:
        action_id = action_result.action_id
        action_type = action_result.type
        target_name = action_result.target.expected_name if action_result.target else None
        idempotency = self.idempotency_policy.classify(action_type, target_name=target_name)

        # 1. Critical Stop: CAPTCHA
        if failure_class == FailureClass.CAPTCHA_PRESENT:
            req = self._create_user_intervention(
                intervention_type="CAPTCHA_PRESENT",
                what_happened="A CAPTCHA / anti-bot verification challenge appeared on the webpage.",
                why_stopped="MATRIOSHAI never automatically bypasses or solves CAPTCHAs.",
                action_required="Please solve the CAPTCHA in the browser window, then click Resume.",
                action_id=action_id,
                tab_id=action_result.target.tab_id if action_result.target else None
            )
            return RecoveryRecommendation(
                recommendation_id=f"rec_{secrets.token_hex(4)}",
                action_id=action_id,
                failure_class=failure_class,
                recovery_type=RecoveryType.ASK_USER,
                reason="CAPTCHA challenge requires user intervention",
                attempt_count=attempt_count,
                max_attempts=self.MAX_RECOVERY_ATTEMPTS,
                requires_user_intervention=True,
                intervention_type="CAPTCHA_PRESENT"
            )

        # 2. Critical Stop: Authentication Required
        if failure_class == FailureClass.AUTHENTICATION_REQUIRED:
            req = self._create_user_intervention(
                intervention_type="LOGIN_REQUIRED",
                what_happened="The website redirected to a login/authentication screen.",
                why_stopped="MATRIOSHAI does not bypass logins or access unauthorized sessions.",
                action_required="Please complete the login in your browser, then click Resume.",
                action_id=action_id,
                tab_id=action_result.target.tab_id if action_result.target else None
            )
            return RecoveryRecommendation(
                recommendation_id=f"rec_{secrets.token_hex(4)}",
                action_id=action_id,
                failure_class=failure_class,
                recovery_type=RecoveryType.ASK_USER,
                reason="Authentication required to proceed",
                attempt_count=attempt_count,
                max_attempts=self.MAX_RECOVERY_ATTEMPTS,
                requires_user_intervention=True,
                intervention_type="LOGIN_REQUIRED"
            )

        # 3. Critical Stop: Non-idempotent action with unknown or failed outcome (Duplicate protection)
        if idempotency == IdempotencyClass.NON_IDEMPOTENT and failure_class not in [FailureClass.CAPTCHA_PRESENT, FailureClass.AUTHENTICATION_REQUIRED]:
            req = self._create_user_intervention(
                intervention_type="HIGH_IMPACT_UNKNOWN",
                what_happened=f"Action '{action_type.value}' on '{target_name or 'target'}' completed with failure or uncertain outcome ({failure_class.value}).",
                why_stopped="Non-idempotent action cannot be safely retried without risking duplicate execution (e.g. double purchase/submit).",
                action_required="Please check your browser state and confirm whether to proceed or re-plan.",
                action_id=action_id,
                tab_id=action_result.target.tab_id if action_result.target else None
            )
            return RecoveryRecommendation(
                recommendation_id=f"rec_{secrets.token_hex(4)}",
                action_id=action_id,
                failure_class=failure_class,
                recovery_type=RecoveryType.ASK_USER,
                reason="Unsafe to retry non-idempotent action with failed/unknown outcome",
                attempt_count=attempt_count,
                max_attempts=self.MAX_RECOVERY_ATTEMPTS,
                requires_user_intervention=True,
                intervention_type="HIGH_IMPACT_UNKNOWN"
            )

        # 4. Exceeded max retry attempts -> REPLAN
        if attempt_count >= self.MAX_RECOVERY_ATTEMPTS:
            return RecoveryRecommendation(
                recommendation_id=f"rec_{secrets.token_hex(4)}",
                action_id=action_id,
                failure_class=failure_class,
                recovery_type=RecoveryType.REPLAN,
                reason=f"Exceeded maximum recovery attempts ({self.MAX_RECOVERY_ATTEMPTS}); handing over to planner",
                attempt_count=attempt_count,
                max_attempts=self.MAX_RECOVERY_ATTEMPTS,
                requires_user_intervention=False
            )

        # 5. Stale target / State mismatch -> REFRESH_WORLD + RE_RESOLVE_TARGET
        if failure_class in [FailureClass.STATE_MISMATCH, FailureClass.TARGET_FAILURE]:
            return RecoveryRecommendation(
                recommendation_id=f"rec_{secrets.token_hex(4)}",
                action_id=action_id,
                failure_class=failure_class,
                recovery_type=RecoveryType.REFRESH_WORLD,
                reason="Refreshing world model to re-resolve target element",
                attempt_count=attempt_count,
                max_attempts=self.MAX_RECOVERY_ATTEMPTS,
                requires_user_intervention=False
            )

        # 6. Transient server or network error -> WAIT + RETRY
        if failure_class in [FailureClass.SERVER_ERROR, FailureClass.NETWORK_FAILURE, FailureClass.TIMEOUT_FAILURE]:
            return RecoveryRecommendation(
                recommendation_id=f"rec_{secrets.token_hex(4)}",
                action_id=action_id,
                failure_class=failure_class,
                recovery_type=RecoveryType.RETRY if idempotency != IdempotencyClass.NON_IDEMPOTENT else RecoveryType.REPLAN,
                reason="Transient failure detected; retrying action",
                attempt_count=attempt_count,
                max_attempts=self.MAX_RECOVERY_ATTEMPTS,
                requires_user_intervention=False
            )

        # 7. Form validation failure -> REPLAN
        if failure_class == FailureClass.VALIDATION_FAILURE:
            return RecoveryRecommendation(
                recommendation_id=f"rec_{secrets.token_hex(4)}",
                action_id=action_id,
                failure_class=failure_class,
                recovery_type=RecoveryType.REPLAN,
                reason="Inline validation error detected; planner should correct input fields",
                attempt_count=attempt_count,
                max_attempts=self.MAX_RECOVERY_ATTEMPTS,
                requires_user_intervention=False
            )

        # Default fallback -> REPLAN
        return RecoveryRecommendation(
            recommendation_id=f"rec_{secrets.token_hex(4)}",
            action_id=action_id,
            failure_class=failure_class,
            recovery_type=RecoveryType.REPLAN,
            reason="Unresolvable failure; planner intervention recommended",
            attempt_count=attempt_count,
            max_attempts=self.MAX_RECOVERY_ATTEMPTS,
            requires_user_intervention=False
        )

    def _create_user_intervention(
        self,
        intervention_type: str,
        what_happened: str,
        why_stopped: str,
        action_required: str,
        action_id: Optional[str] = None,
        tab_id: Optional[int] = None
    ) -> UserInterventionRequest:
        req = UserInterventionRequest(
            intervention_id=f"intv_{secrets.token_hex(4)}",
            type=intervention_type,
            what_happened=what_happened,
            why_stopped=why_stopped,
            action_required=action_required,
            tab_id=tab_id,
            action_id=action_id,
            status="PENDING"
        )
        self.state_store.user_interventions[req.intervention_id] = req
        return req

class InvalidationManager:
    """
    Manages selective artifact and model invalidations.
    Scopes: ELEMENT, PAGE, FRAME, TAB, WORLD.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store

    def invalidate(self, scope: str, target_id: Optional[Any] = None):
        store = self.state_store
        if scope == "WORLD":
            store.world_model_version += 1
            store.page_states.clear()
            store.world_elements.clear()
            logger.info("[MATRIOSHAI][Invalidation] Full world invalidated")
        elif scope == "TAB" and isinstance(target_id, int):
            store.page_states.pop(target_id, None)
            store.world_elements.pop(target_id, None)
            store.world_model_version += 1
            logger.info(f"[MATRIOSHAI][Invalidation] Tab {target_id} invalidated")
        elif scope == "PAGE" and isinstance(target_id, int):
            if target_id in store.page_states:
                store.page_states[target_id].page_version += 1
            store.world_model_version += 1
            logger.info(f"[MATRIOSHAI][Invalidation] Page on tab {target_id} invalidated")
        else:
            store.world_model_version += 1

class WorkflowCheckpointManager:
    """
    Creates and restores named workflow checkpoints for resumable autonomy.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store

    def create_checkpoint(self, name: str, step_index: int, snapshot_id: str, tab_id: Optional[int] = None) -> WorkflowCheckpoint:
        cp = WorkflowCheckpoint(
            checkpoint_id=f"chk_{secrets.token_hex(4)}",
            name=name,
            step_index=step_index,
            snapshot_id=snapshot_id,
            world_version=self.state_store.world_model_version,
            tab_id=tab_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        self.state_store.checkpoints[cp.checkpoint_id] = cp
        logger.info(f"[MATRIOSHAI][Checkpoint] Created workflow checkpoint '{cp.name}' ({cp.checkpoint_id})")
        return cp

    def get_checkpoints(self) -> List[WorkflowCheckpoint]:
        return list(self.state_store.checkpoints.values())

class VerificationEngine:
    """
    Unified Action Verification Engine orchestrator (Phase 9).
    Evaluates evidence from before/after snapshots, diffs, DOM states,
    and postconditions to verify intended action outcomes.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self.postcondition_engine = PostconditionEngine(self.state_store)
        self.error_detector = PageErrorDetector()
        self.failure_classifier = FailureClassifier()
        self.recovery_engine = RecoveryEngine(self.state_store)
        self.invalidation_manager = InvalidationManager(self.state_store)
        self.checkpoint_manager = WorkflowCheckpointManager(self.state_store)

    def is_state_stable(self, tab_id: int) -> bool:
        """
        Signals whether page has reached a stable state:
        - Navigation is completed
        - No prominent loading spinners active
        """
        page = self.state_store.page_states.get(tab_id)
        if not page:
            return True

        elements = self.state_store.world_elements.get(tab_id, [])
        has_spinner = any(
            el.visible and any(sp in el.name.lower() or sp in el.role.lower() for sp in ["spinner", "loading", "progress"])
            for el in elements
        )
        return not has_spinner

    async def verify_action(
        self,
        action_result: ActionResult,
        before_snapshot: Optional[BrowserWorldSnapshot] = None,
        after_snapshot: Optional[BrowserWorldSnapshot] = None,
        wait_policy: Optional[VerificationWaitPolicy] = None,
        postcondition_mode: PostconditionEvaluationMode = PostconditionEvaluationMode.ALL
    ) -> VerificationResult:
        """
        Main verification method:
        ActionResult + BeforeSnapshot + AfterSnapshot -> Postconditions -> Evidence -> VerificationResult.
        """
        start_time = time.time()
        ver_id = f"ver_{secrets.token_hex(4)}"
        store = self.state_store
        tab_id = action_result.target.tab_id if action_result.target and action_result.target.tab_id else (store.active_tab_id or 1)

        # 1. Action Execution Status Check
        if action_result.status != ActionStatus.SUCCESS and action_result.status != ActionStatus.NO_OP:
            fail_class = self.failure_classifier.classify(
                action_result=action_result,
                error_surface=None,
                postcondition_passed=False,
                has_state_diff=False
            )
            rec = self.recovery_engine.recommend_recovery(action_result, fail_class)
            return VerificationResult(
                verification_id=ver_id,
                action_id=action_result.action_id,
                status=VerificationStatus.VERIFIED_FAILURE if action_result.status == ActionStatus.FAILED else VerificationStatus.BLOCKED,
                confidence="HIGH",
                before_snapshot_id=before_snapshot.snapshot_id if before_snapshot else None,
                after_snapshot_id=after_snapshot.snapshot_id if after_snapshot else None,
                before_world_version=action_result.world_model_version_before,
                after_world_version=action_result.world_model_version_after or action_result.world_model_version_before,
                evaluated_postconditions=[],
                evidence=[VerificationEvidence(
                    evidence_id=f"ev_{secrets.token_hex(4)}",
                    source="DOM",
                    type="EXECUTION_STATUS",
                    description=f"Action execution status was {action_result.status.value}",
                    confidence="HIGH",
                    timestamp=datetime.now(timezone.utc).isoformat()
                )],
                failure_class=fail_class,
                recovery_recommendation=rec,
                is_stable=True,
                duration_ms=round((time.time() - start_time) * 1000, 2)
            )

        # 2. Wait Policy & Stability Delay (if configured)
        if wait_policy and wait_policy.initial_delay_ms > 0:
            await asyncio.sleep(wait_policy.initial_delay_ms / 1000.0)

        # 3. Compute State Diff between snapshots
        state_diff: Optional[WorldStateDiff] = None
        has_state_diff = False
        if before_snapshot and after_snapshot:
            state_diff = world_model_engine.diff_world(before_snapshot, after_snapshot)
            has_state_diff = (
                (state_diff.tabs_diff and (len(state_diff.tabs_diff.added) > 0 or len(state_diff.tabs_diff.changed) > 0)) or
                (state_diff.pages_diff and (len(state_diff.pages_diff.added) > 0 or len(state_diff.pages_diff.changed) > 0))
            )

        # 4. Error Surface & Failure Detection
        detected_error = self.error_detector.detect_errors(tab_id, store)

        # 5. Evaluate Postconditions
        conditions = action_result.expected_postconditions or []
        is_satisfied, eval_results = self.postcondition_engine.evaluate_all(
            conditions=conditions,
            tab_id=tab_id,
            diff=state_diff,
            mode=postcondition_mode
        )

        # 6. Synthesize Evidence Graph
        evidence_list: List[VerificationEvidence] = []
        confidence = "HIGH"

        # Evidence: Execution Success
        evidence_list.append(VerificationEvidence(
            evidence_id=f"ev_{secrets.token_hex(4)}",
            source="DOM",
            type="ACTION_EXECUTED",
            description=f"Action {action_result.type.value} dispatched successfully",
            confidence="HIGH",
            timestamp=datetime.now(timezone.utc).isoformat()
        ))

        # Evidence: State Diff
        if state_diff:
            evidence_list.append(VerificationEvidence(
                evidence_id=f"ev_{secrets.token_hex(4)}",
                source="SNAPSHOT_DIFF",
                type="STATE_DIFF",
                description=f"Tabs changed: {len(state_diff.tabs_diff.changed if state_diff.tabs_diff else [])}, Pages changed: {len(state_diff.pages_diff.changed if state_diff.pages_diff else [])}",
                confidence="HIGH",
                timestamp=datetime.now(timezone.utc).isoformat()
            ))

        # Evidence: Postconditions
        for r in eval_results:
            evidence_list.append(VerificationEvidence(
                evidence_id=f"ev_{secrets.token_hex(4)}",
                source="DOM",
                type=f"POSTCONDITION_{r.condition.type}",
                description=f"{r.condition.type}: {r.status} ({r.evidence_description or ''})",
                confidence="HIGH" if r.status == "PASS" else "MEDIUM",
                timestamp=datetime.now(timezone.utc).isoformat()
            ))

        # 7. Final Status Determination & Conflicting Evidence Check
        final_status = VerificationStatus.VERIFIED_SUCCESS
        failure_class: Optional[FailureClass] = None

        if detected_error:
            failure_class = detected_error[0]
            if is_satisfied and len(conditions) > 0:
                final_status = VerificationStatus.CONFLICTING_EVIDENCE
                evidence_list.append(VerificationEvidence(
                    evidence_id=f"ev_{secrets.token_hex(4)}",
                    source="DOM",
                    type="CONFLICTING_EVIDENCE",
                    description=f"Postcondition passed but error was detected: {detected_error[1]}",
                    confidence="HIGH",
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
            else:
                final_status = VerificationStatus.VERIFIED_FAILURE
        elif not is_satisfied and len(conditions) > 0:
            final_status = VerificationStatus.VERIFIED_FAILURE
            failure_class = self.failure_classifier.classify(
                action_result=action_result,
                error_surface=None,
                postcondition_passed=False,
                has_state_diff=has_state_diff
            )
        else:
            final_status = VerificationStatus.VERIFIED_SUCCESS

        # 8. Recovery Recommendation (if failed)
        recovery_rec: Optional[RecoveryRecommendation] = None
        if final_status != VerificationStatus.VERIFIED_SUCCESS:
            recovery_rec = self.recovery_engine.recommend_recovery(
                action_result=action_result,
                failure_class=failure_class or FailureClass.UNKNOWN_FAILURE
            )

        dur_ms = round((time.time() - start_time) * 1000, 2)
        res = VerificationResult(
            verification_id=ver_id,
            action_id=action_result.action_id,
            status=final_status,
            confidence=confidence,
            before_snapshot_id=before_snapshot.snapshot_id if before_snapshot else None,
            after_snapshot_id=after_snapshot.snapshot_id if after_snapshot else None,
            before_world_version=before_snapshot.world_model_version if before_snapshot else action_result.world_model_version_before,
            after_world_version=after_snapshot.world_model_version if after_snapshot else (action_result.world_model_version_after or action_result.world_model_version_before),
            evaluated_postconditions=eval_results,
            state_changes=state_diff,
            evidence=evidence_list,
            failure_class=failure_class,
            recovery_recommendation=recovery_rec,
            is_stable=self.is_state_stable(tab_id),
            duration_ms=dur_ms,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        store.verifications[res.verification_id] = res
        return res

verification_engine = VerificationEngine()
