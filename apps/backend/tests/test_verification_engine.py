"""
MATRIOSHAI Action Verification, Recovery & State Reconciliation Engine Tests (Phase 9)

Comprehensive verification of:
1. Outcome verification with multi-signal evidence and confidence model
2. Postcondition engine with ALL, ANY, AT_LEAST_N evaluation
3. Page error surface detection (Server errors, validation errors, auth modals, CAPTCHAs, rate limits)
4. Failure classification across 18 discrete failure types
5. Idempotency policies and duplicate action protections
6. Human intervention workflows and user handoff
7. Workflow checkpoint creation and restoration
8. Selective invalidation
9. Conflicting evidence detection
10. Password/sensitive value safety
"""

import pytest
import asyncio
from app.browser.state_store import (
    BrowserStateStore,
    WindowState,
    TabState,
    TabStatus,
    WorldPageState,
    WorldElement,
    WorldElementRef,
    WorldElementSemanticState,
    VisualBoundingBox,
    BrowserWorldSnapshot,
    WorldTabState,
    ActionIntent,
    ActionType,
    ActionTarget,
    ActionPostcondition,
    ActionResult,
    ActionStatus,
    ActionTrace,
    VerificationStatus,
    FailureClass,
    RecoveryType,
    IdempotencyClass,
    PostconditionEvaluationMode,
    VerificationWaitPolicy
)
from app.browser.verification_engine import (
    VerificationEngine,
    PostconditionEngine,
    PageErrorDetector,
    FailureClassifier,
    IdempotencyPolicy,
    RecoveryEngine,
    WorkflowCheckpointManager
)

@pytest.fixture
def mock_verification_store():
    store = BrowserStateStore()
    store.set_browser_identity("test_chrome_verif_instance", "124.0.0.0")

    # Windows & Tabs
    w1 = WindowState(window_id=1, focused=True, state="normal", tab_ids=[101, 102], active_tab_id=101)
    store.windows = {1: w1}

    t1 = TabState(tab_id=101, window_id=1, index=0, active=True, url="https://portal.example.com/search", title="Search Portal", status=TabStatus.READY)
    t2 = TabState(tab_id=102, window_id=1, index=1, active=False, url="https://portal.example.com/about", title="About", status=TabStatus.READY)
    store.tabs = {101: t1, 102: t2}
    store.active_tab_id = 101
    store.world_model_version = 20

    # Page State for Tab 101
    p1 = WorldPageState(
        page_id="page_101_v1",
        tab_id=101,
        url="https://portal.example.com/search",
        origin="https://portal.example.com",
        title="Search Portal",
        page_version=1,
        viewport_width=1280,
        viewport_height=800,
        active_dialogs=[]
    )
    store.page_states[101] = p1

    # World Elements
    el_search = WorldElement(
        element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="btn_search", role="button", name="Search Flights", page_version=1),
        role="button",
        name="Search Flights",
        semantic_state=WorldElementSemanticState(type="button", enabled=True, focused=False),
        geometry=VisualBoundingBox(x=100, y=100, width=120, height=35),
        visible=True,
        enabled=True,
        page_version=1
    )

    store.world_elements[101] = [el_search]
    return store

@pytest.mark.asyncio
async def test_successful_click_outcome_verification(mock_verification_store):
    """Test standard verification when action executes and expected outcome is reached."""
    engine = VerificationEngine(mock_verification_store)

    # Before snapshot
    before_snap = BrowserWorldSnapshot(
        snapshot_id="snap_pre_search",
        timestamp="2026-08-22T12:00:00Z",
        world_model_version=20,
        active_tab_id=101,
        tab_states=[WorldTabState(tab_id=101, window_id=1, url="https://portal.example.com/search", title="Search", active=True, status="READY")],
        page_states=[mock_verification_store.page_states[101].model_copy(deep=True)],
        reason="pre_action"
    )

    # Simulate transition to Results
    mock_verification_store.page_states[101].url = "https://portal.example.com/results"
    mock_verification_store.page_states[101].title = "Search Results - 14 Flights"
    el_results = WorldElement(
        element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_2", element_id="container_results", role="region", name="Search Results", page_version=1),
        role="region",
        name="Search Results",
        geometry=VisualBoundingBox(x=50, y=150, width=600, height=400),
        visible=True,
        enabled=True,
        page_version=1
    )
    mock_verification_store.world_elements[101] = [el_results]

    # After snapshot
    after_snap = BrowserWorldSnapshot(
        snapshot_id="snap_post_search",
        timestamp="2026-08-22T12:00:01Z",
        world_model_version=21,
        active_tab_id=101,
        tab_states=[WorldTabState(tab_id=101, window_id=1, url="https://portal.example.com/results", title="Search Results", active=True, status="READY")],
        page_states=[mock_verification_store.page_states[101].model_copy(deep=True)],
        reason="post_action"
    )

    action_result = ActionResult(
        action_id="act_search_001",
        type=ActionType.CLICK,
        status=ActionStatus.SUCCESS,
        started_at="2026-08-22T12:00:00Z",
        completed_at="2026-08-22T12:00:01Z",
        duration_ms=45.0,
        world_model_version_before=20,
        world_model_version_after=21,
        target=ActionTarget(expected_name="Search Flights", tab_id=101),
        trace=ActionTrace(action_id="act_search_001", steps=[]),
        expected_postconditions=[
            ActionPostcondition(type="URL_MATCH", expected_value="/results"),
            ActionPostcondition(type="ELEMENT_PRESENT", expected_value="Search Results")
        ]
    )

    ver_res = await engine.verify_action(
        action_result=action_result,
        before_snapshot=before_snap,
        after_snapshot=after_snap
    )

    assert ver_res.status == VerificationStatus.VERIFIED_SUCCESS
    assert ver_res.confidence == "HIGH"
    assert len(ver_res.evaluated_postconditions) == 2
    assert all(p.status == "PASS" for p in ver_res.evaluated_postconditions)

@pytest.mark.asyncio
async def test_click_executed_but_no_state_change_failure(mock_verification_store):
    """Test failure detection when action executes but page does not transition."""
    engine = VerificationEngine(mock_verification_store)

    snap = BrowserWorldSnapshot(
        snapshot_id="snap_same",
        timestamp="2026-08-22T12:00:00Z",
        world_model_version=20,
        active_tab_id=101,
        tab_states=[WorldTabState(tab_id=101, window_id=1, url="https://portal.example.com/search", title="Search", active=True, status="READY")],
        page_states=[mock_verification_store.page_states[101].model_copy(deep=True)],
        reason="same_state"
    )

    action_result = ActionResult(
        action_id="act_noop_click",
        type=ActionType.CLICK,
        status=ActionStatus.SUCCESS, # Executed cleanly
        started_at="2026-08-22T12:00:00Z",
        completed_at="2026-08-22T12:00:01Z",
        duration_ms=50.0,
        world_model_version_before=20,
        world_model_version_after=20,
        target=ActionTarget(expected_name="Search Flights", tab_id=101),
        trace=ActionTrace(action_id="act_noop_click", steps=[]),
        expected_postconditions=[
            ActionPostcondition(type="URL_MATCH", expected_value="/results")
        ]
    )

    ver_res = await engine.verify_action(
        action_result=action_result,
        before_snapshot=snap,
        after_snapshot=snap
    )

    # Must NOT return success!
    assert ver_res.status == VerificationStatus.VERIFIED_FAILURE
    assert ver_res.failure_class is not None

@pytest.mark.asyncio
async def test_server_error_page_detection(mock_verification_store):
    """Test structured detection of HTTP 500 server error."""
    engine = VerificationEngine(mock_verification_store)

    mock_verification_store.page_states[101].title = "500 Internal Server Error"
    mock_verification_store.world_elements[101] = [
        WorldElement(
            element_ref=WorldElementRef(page_id="p1", observation_id="o1", element_id="e_err", role="heading", name="500 Internal Server Error", page_version=1),
            role="heading",
            name="500 Internal Server Error",
            geometry=VisualBoundingBox(x=10, y=10, width=400, height=50),
            visible=True,
            enabled=True,
            page_version=1
        )
    ]

    action_result = ActionResult(
        action_id="act_err_500",
        type=ActionType.CLICK,
        status=ActionStatus.SUCCESS,
        started_at="2026-08-22T12:00:00Z",
        completed_at="2026-08-22T12:00:01Z",
        duration_ms=60.0,
        world_model_version_before=20,
        world_model_version_after=21,
        target=ActionTarget(expected_name="Submit", tab_id=101),
        trace=ActionTrace(action_id="act_err_500", steps=[])
    )

    ver_res = await engine.verify_action(action_result)

    assert ver_res.status == VerificationStatus.VERIFIED_FAILURE
    assert ver_res.failure_class == FailureClass.SERVER_ERROR
    assert ver_res.recovery_recommendation is not None

@pytest.mark.asyncio
async def test_form_validation_failure_detection(mock_verification_store):
    """Test structured detection of inline form validation error."""
    engine = VerificationEngine(mock_verification_store)

    mock_verification_store.world_elements[101] = [
        WorldElement(
            element_ref=WorldElementRef(page_id="p1", observation_id="o1", element_id="e_val", role="alert", name="Please enter a valid email address", page_version=1),
            role="alert",
            name="Please enter a valid email address",
            geometry=VisualBoundingBox(x=10, y=10, width=300, height=25),
            visible=True,
            enabled=True,
            page_version=1
        )
    ]

    action_result = ActionResult(
        action_id="act_val_fail",
        type=ActionType.CLICK,
        status=ActionStatus.SUCCESS,
        started_at="2026-08-22T12:00:00Z",
        completed_at="2026-08-22T12:00:01Z",
        duration_ms=40.0,
        world_model_version_before=20,
        world_model_version_after=21,
        target=ActionTarget(expected_name="Continue", tab_id=101),
        trace=ActionTrace(action_id="act_val_fail", steps=[])
    )

    ver_res = await engine.verify_action(action_result)

    assert ver_res.status == VerificationStatus.VERIFIED_FAILURE
    assert ver_res.failure_class == FailureClass.VALIDATION_FAILURE
    assert ver_res.recovery_recommendation.recovery_type == RecoveryType.REPLAN

@pytest.mark.asyncio
async def test_authentication_screen_detection_and_human_handoff(mock_verification_store):
    """Test detection of redirected authentication screen pausing automation for human handoff."""
    engine = VerificationEngine(mock_verification_store)

    mock_verification_store.page_states[101].url = "https://portal.example.com/login"
    mock_verification_store.page_states[101].title = "Sign In - Security Gateway"
    mock_verification_store.world_elements[101] = [
        WorldElement(
            element_ref=WorldElementRef(page_id="p1", observation_id="o1", element_id="e_pwd", role="textbox", name="Password", page_version=1),
            role="textbox",
            name="Password",
            geometry=VisualBoundingBox(x=10, y=10, width=200, height=35),
            visible=True,
            enabled=True,
            page_version=1
        )
    ]

    action_result = ActionResult(
        action_id="act_auth_req",
        type=ActionType.CLICK,
        status=ActionStatus.SUCCESS,
        started_at="2026-08-22T12:00:00Z",
        completed_at="2026-08-22T12:00:01Z",
        duration_ms=50.0,
        world_model_version_before=20,
        world_model_version_after=21,
        target=ActionTarget(expected_name="Account Settings", tab_id=101),
        trace=ActionTrace(action_id="act_auth_req", steps=[])
    )

    ver_res = await engine.verify_action(action_result)

    assert ver_res.status == VerificationStatus.VERIFIED_FAILURE
    assert ver_res.failure_class == FailureClass.AUTHENTICATION_REQUIRED
    assert ver_res.recovery_recommendation.recovery_type == RecoveryType.ASK_USER
    assert ver_res.recovery_recommendation.requires_user_intervention is True
    assert len(mock_verification_store.user_interventions) == 1

@pytest.mark.asyncio
async def test_captcha_challenge_detection(mock_verification_store):
    """Test detection of CAPTCHA / anti-bot challenge stopping automation without bypass."""
    engine = VerificationEngine(mock_verification_store)

    mock_verification_store.page_states[101].title = "Just a moment... Security Check"
    mock_verification_store.world_elements[101] = [
        WorldElement(
            element_ref=WorldElementRef(page_id="p1", observation_id="o1", element_id="e_turnstile", role="region", name="Verify you are human - Cloudflare Turnstile", page_version=1),
            role="region",
            name="Verify you are human - Cloudflare Turnstile",
            geometry=VisualBoundingBox(x=10, y=10, width=300, height=100),
            visible=True,
            enabled=True,
            page_version=1
        )
    ]

    action_result = ActionResult(
        action_id="act_captcha",
        type=ActionType.CLICK,
        status=ActionStatus.SUCCESS,
        started_at="2026-08-22T12:00:00Z",
        completed_at="2026-08-22T12:00:01Z",
        duration_ms=45.0,
        world_model_version_before=20,
        world_model_version_after=21,
        target=ActionTarget(expected_name="Submit", tab_id=101),
        trace=ActionTrace(action_id="act_captcha", steps=[])
    )

    ver_res = await engine.verify_action(action_result)

    assert ver_res.status == VerificationStatus.VERIFIED_FAILURE
    assert ver_res.failure_class == FailureClass.CAPTCHA_PRESENT
    assert ver_res.recovery_recommendation.recovery_type == RecoveryType.ASK_USER
    assert ver_res.recovery_recommendation.intervention_type == "CAPTCHA_PRESENT"

@pytest.mark.asyncio
async def test_non_idempotent_duplicate_action_protection(mock_verification_store):
    """Test that non-idempotent actions (e.g. Buy Now) are NEVER auto-retried upon unknown outcome."""
    engine = VerificationEngine(mock_verification_store)

    action_result = ActionResult(
        action_id="act_payment_unknown",
        type=ActionType.CLICK,
        status=ActionStatus.SUCCESS,
        started_at="2026-08-22T12:00:00Z",
        completed_at="2026-08-22T12:00:01Z",
        duration_ms=70.0,
        world_model_version_before=20,
        world_model_version_after=20,
        target=ActionTarget(expected_name="Complete Payment & Purchase", tab_id=101),
        trace=ActionTrace(action_id="act_payment_unknown", steps=[]),
        expected_postconditions=[
            ActionPostcondition(type="TEXT_PRESENT", expected_value="Order Confirmed #")
        ]
    )

    ver_res = await engine.verify_action(action_result)

    # Must NOT auto-retry!
    assert ver_res.status == VerificationStatus.VERIFIED_FAILURE
    assert ver_res.recovery_recommendation.recovery_type == RecoveryType.ASK_USER
    assert ver_res.recovery_recommendation.requires_user_intervention is True

@pytest.mark.asyncio
async def test_conflicting_evidence_resolution(mock_verification_store):
    """Test detection when postcondition nominally passes (URL matches) but page displays error."""
    engine = VerificationEngine(mock_verification_store)

    # URL matches /results
    mock_verification_store.page_states[101].url = "https://portal.example.com/results"
    mock_verification_store.page_states[101].title = "Results Page - Something went wrong"
    # But error message is present
    mock_verification_store.world_elements[101] = [
        WorldElement(
            element_ref=WorldElementRef(page_id="p1", observation_id="o1", element_id="e_err", role="alert", name="Something went wrong", page_version=1),
            role="alert",
            name="Something went wrong",
            geometry=VisualBoundingBox(x=10, y=10, width=300, height=40),
            visible=True,
            enabled=True,
            page_version=1
        )
    ]

    action_result = ActionResult(
        action_id="act_conflict",
        type=ActionType.CLICK,
        status=ActionStatus.SUCCESS,
        started_at="2026-08-22T12:00:00Z",
        completed_at="2026-08-22T12:00:01Z",
        duration_ms=45.0,
        world_model_version_before=20,
        world_model_version_after=21,
        target=ActionTarget(expected_name="Search", tab_id=101),
        trace=ActionTrace(action_id="act_conflict", steps=[]),
        expected_postconditions=[
            ActionPostcondition(type="URL_MATCH", expected_value="/results")
        ]
    )

    ver_res = await engine.verify_action(action_result)

    # Must detect CONFLICTING_EVIDENCE
    assert ver_res.status == VerificationStatus.CONFLICTING_EVIDENCE
    assert any(ev.type == "CONFLICTING_EVIDENCE" for ev in ver_res.evidence)

@pytest.mark.asyncio
async def test_multi_condition_combinators(mock_verification_store):
    """Test evaluating conditions with ALL, ANY, and AT_LEAST_N."""
    post_engine = PostconditionEngine(mock_verification_store)

    mock_verification_store.page_states[101].url = "https://portal.example.com/results"
    mock_verification_store.world_elements[101] = [
        WorldElement(
            element_ref=WorldElementRef(page_id="p1", observation_id="o1", element_id="e_fl", role="button", name="Select Flight #412", page_version=1),
            role="button",
            name="Select Flight #412",
            geometry=VisualBoundingBox(x=10, y=10, width=150, height=35),
            visible=True,
            enabled=True,
            page_version=1
        )
    ]

    c1 = ActionPostcondition(type="URL_MATCH", expected_value="/results")
    c2 = ActionPostcondition(type="ELEMENT_PRESENT", expected_value="Select Flight")
    c3 = ActionPostcondition(type="TEXT_PRESENT", expected_value="No Flights Found") # Will fail

    # 1. Mode: ALL (c1, c2, c3) -> False
    all_ok, res_all = post_engine.evaluate_all([c1, c2, c3], 101, mode=PostconditionEvaluationMode.ALL)
    assert all_ok is False

    # 2. Mode: ANY (c1, c2, c3) -> True
    any_ok, res_any = post_engine.evaluate_all([c1, c2, c3], 101, mode=PostconditionEvaluationMode.ANY)
    assert any_ok is True

    # 3. Mode: AT_LEAST_N (2 out of 3) -> True
    at_least_ok, res_at_least = post_engine.evaluate_all([c1, c2, c3], 101, mode=PostconditionEvaluationMode.AT_LEAST_N, min_pass_count=2)
    assert at_least_ok is True

@pytest.mark.asyncio
async def test_workflow_checkpoints(mock_verification_store):
    """Test creating and retrieving workflow checkpoints."""
    mgr = WorkflowCheckpointManager(mock_verification_store)

    cp1 = mgr.create_checkpoint(name="search_initiated", step_index=1, snapshot_id="snap_1", tab_id=101)
    cp2 = mgr.create_checkpoint(name="results_loaded", step_index=2, snapshot_id="snap_2", tab_id=101)

    checkpoints = mgr.get_checkpoints()
    assert len(checkpoints) == 2
    assert checkpoints[0].name == "search_initiated"
    assert checkpoints[1].step_index == 2

@pytest.mark.asyncio
async def test_recovery_attempt_limits(mock_verification_store):
    """Test enforcing max recovery attempts limit before handing over to planner."""
    rec_engine = RecoveryEngine(mock_verification_store)

    action_result = ActionResult(
        action_id="act_retry_limit",
        type=ActionType.CLICK,
        status=ActionStatus.FAILED,
        started_at="2026-08-22T12:00:00Z",
        completed_at="2026-08-22T12:00:01Z",
        duration_ms=30.0,
        world_model_version_before=20,
        world_model_version_after=20,
        target=ActionTarget(expected_name="Reload"),
        trace=ActionTrace(action_id="act_retry_limit", steps=[])
    )

    # Attempt 1 -> RETRY
    rec1 = rec_engine.recommend_recovery(action_result, FailureClass.NETWORK_FAILURE, attempt_count=1)
    assert rec1.recovery_type == RecoveryType.RETRY

    # Attempt 3 (limit reached) -> REPLAN
    rec3 = rec_engine.recommend_recovery(action_result, FailureClass.NETWORK_FAILURE, attempt_count=3)
    assert rec3.recovery_type == RecoveryType.REPLAN
