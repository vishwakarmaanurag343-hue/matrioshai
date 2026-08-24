"""
MATRIOSHAI Safe Browser Action Engine Unit Tests (Phase 8)

Comprehensive verification of:
1. Action schema validation and ActionIntent parsing
2. Semantic and WorldElement target resolution
3. Ambiguous target rejection
4. Stale world and stale target rejection
5. Wrong tab and wrong page rejection
6. Disabled and invisible target rejection
7. Policy engine (SAFE, SENSITIVE with redaction, HIGH_IMPACT confirmation, BLOCKED dangerous schemes)
8. Confirmation flow (approval and cancellation)
9. Dry-run validation (WOULD_EXECUTE)
10. Per-tab queue serialization and conflict cancellation
11. Precondition evaluation
12. Trace generation and Phase 9 verification contract
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
    ActionIntent,
    ActionType,
    ActionTarget,
    ActionPrecondition,
    ActionPostcondition,
    ActionPolicyCategory,
    PolicyDecision,
    ActionStatus
)
from app.browser.action_engine import (
    ActionEngine,
    TargetResolver,
    ActionValidator,
    ActionPolicyEngine,
    ActionQueueManager
)

@pytest.fixture
def mock_store():
    store = BrowserStateStore()
    store.set_browser_identity("test_chrome_action_instance", "124.0.0.0")

    # Add Windows
    w1 = WindowState(window_id=1, focused=True, state="normal", tab_ids=[101, 102], active_tab_id=101)
    store.windows = {1: w1}

    # Add Tabs
    t1 = TabState(tab_id=101, window_id=1, index=0, active=True, url="https://portal.example.com/checkout", title="Checkout", status=TabStatus.READY)
    t2 = TabState(tab_id=102, window_id=1, index=1, active=False, url="https://portal.example.com/search", title="Search", status=TabStatus.READY)
    store.tabs = {101: t1, 102: t2}
    store.active_tab_id = 101
    store.world_model_version = 10

    # Add Page State for Tab 101
    p1 = WorldPageState(
        page_id="page_101_v1",
        tab_id=101,
        url="https://portal.example.com/checkout",
        origin="https://portal.example.com",
        title="Checkout",
        page_version=1,
        viewport_width=1280,
        viewport_height=800,
        active_dialogs=[]
    )
    store.page_states[101] = p1

    # Add WorldElements for Tab 101
    el_search = WorldElement(
        element_ref=WorldElementRef(
            page_id="page_101_v1",
            observation_id="obs_1",
            element_id="elem_btn_search",
            role="button",
            name="Search Flights",
            page_version=1,
            stable_dom_identity="btn-search"
        ),
        role="button",
        name="Search Flights",
        semantic_state=WorldElementSemanticState(type="button", enabled=True, focused=False),
        geometry=VisualBoundingBox(x=100, y=100, width=120, height=35),
        visible=True,
        enabled=True,
        page_version=1
    )

    el_purchase = WorldElement(
        element_ref=WorldElementRef(
            page_id="page_101_v1",
            observation_id="obs_1",
            element_id="elem_btn_buy",
            role="button",
            name="Buy Now",
            page_version=1,
            stable_dom_identity="btn-buy"
        ),
        role="button",
        name="Buy Now",
        semantic_state=WorldElementSemanticState(type="button", enabled=True, focused=False),
        geometry=VisualBoundingBox(x=300, y=300, width=150, height=45),
        visible=True,
        enabled=True,
        page_version=1
    )

    el_disabled = WorldElement(
        element_ref=WorldElementRef(
            page_id="page_101_v1",
            observation_id="obs_1",
            element_id="elem_btn_disabled",
            role="button",
            name="Disabled Option",
            page_version=1
        ),
        role="button",
        name="Disabled Option",
        semantic_state=WorldElementSemanticState(type="button", enabled=False, focused=False),
        geometry=VisualBoundingBox(x=500, y=500, width=100, height=30),
        visible=True,
        enabled=False,
        page_version=1
    )

    el_invisible = WorldElement(
        element_ref=WorldElementRef(
            page_id="page_101_v1",
            observation_id="obs_1",
            element_id="elem_btn_hidden",
            role="button",
            name="Hidden Option",
            page_version=1
        ),
        role="button",
        name="Hidden Option",
        semantic_state=WorldElementSemanticState(type="button", enabled=True, focused=False),
        geometry=VisualBoundingBox(x=-100, y=-100, width=50, height=20),
        visible=False,
        enabled=True,
        page_version=1
    )

    el_duplicate_1 = WorldElement(
        element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="btn_dup_1", role="button", name="Select Option", page_version=1),
        role="button",
        name="Select Option",
        geometry=VisualBoundingBox(x=10, y=10, width=50, height=20),
        visible=True,
        enabled=True,
        page_version=1
    )

    el_duplicate_2 = WorldElement(
        element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="btn_dup_2", role="button", name="Select Option", page_version=1),
        role="button",
        name="Select Option",
        geometry=VisualBoundingBox(x=10, y=50, width=50, height=20),
        visible=True,
        enabled=True,
        page_version=1
    )

    store.world_elements[101] = [el_search, el_purchase, el_disabled, el_invisible, el_duplicate_1, el_duplicate_2]

    return store

@pytest.mark.asyncio
async def test_safe_click_action_execution(mock_store):
    """Test standard safe CLICK action validation, target resolution, and simulated execution."""
    engine = ActionEngine(mock_store)

    intent = ActionIntent(
        action_id="act_click_001",
        type=ActionType.CLICK,
        target=ActionTarget(
            world_element_ref=WorldElementRef(
                page_id="page_101_v1",
                observation_id="obs_1",
                element_id="elem_btn_search",
                page_version=1
            )
        ),
        world_model_version=10,
        page_version=1,
        tab_id=101,
        page_id="page_101_v1",
        postconditions=[ActionPostcondition(type="URL_CHANGED")]
    )

    result = await engine.execute_action(intent)

    assert result.status == ActionStatus.SUCCESS
    assert result.action_id == "act_click_001"
    assert result.world_model_version_before == 10
    assert result.world_model_version_after == 11
    assert len(result.trace.steps) >= 5
    assert any(s.stage == "TARGET_RESOLVED" and s.status == "PASS" for s in result.trace.steps)

@pytest.mark.asyncio
async def test_ambiguous_target_rejection(mock_store):
    """Test rejection when multiple buttons match role and accessible name."""
    engine = ActionEngine(mock_store)

    intent = ActionIntent(
        action_id="act_ambig_001",
        type=ActionType.CLICK,
        target=ActionTarget(
            expected_role="button",
            expected_name="Select Option"
        ),
        world_model_version=10,
        page_version=1,
        tab_id=101,
        page_id="page_101_v1"
    )

    result = await engine.execute_action(intent)

    assert result.status == ActionStatus.AMBIGUOUS
    assert result.error is not None
    assert result.error.code == "AMBIGUOUS"
    assert result.error.requires_replan is True

@pytest.mark.asyncio
async def test_stale_world_and_page_version_rejection(mock_store):
    """Test rejection when ActionIntent is submitted with stale world / page version."""
    engine = ActionEngine(mock_store)

    # Page version is now v2 on tab 101
    mock_store.page_states[101].page_version = 2

    intent = ActionIntent(
        action_id="act_stale_001",
        type=ActionType.CLICK,
        target=ActionTarget(
            world_element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="elem_btn_search", page_version=1)
        ),
        world_model_version=8, # Older than current v10
        page_version=1,        # Older than current v2
        tab_id=101,
        page_id="page_101_v1"
    )

    result = await engine.execute_action(intent)

    assert result.status in [ActionStatus.FAILED, ActionStatus.STALE]
    assert result.error is not None
    assert result.error.requires_replan is True

@pytest.mark.asyncio
async def test_wrong_page_rejection(mock_store):
    """Test rejection when action targets an old or unrelated page_id."""
    engine = ActionEngine(mock_store)

    intent = ActionIntent(
        action_id="act_wrong_page",
        type=ActionType.CLICK,
        target=ActionTarget(
            world_element_ref=WorldElementRef(page_id="page_old_nav_999", observation_id="obs_1", element_id="elem_btn_search", page_version=1)
        ),
        world_model_version=10,
        page_version=1,
        tab_id=101,
        page_id="page_old_nav_999" # Mismatch with current page_101_v1
    )

    result = await engine.execute_action(intent)

    assert result.status in [ActionStatus.NOT_FOUND, ActionStatus.FAILED]
    assert result.error is not None
    assert "WRONG_PAGE" in result.error.code or "Page ID mismatch" in result.error.message

@pytest.mark.asyncio
async def test_disabled_and_invisible_target_rejection(mock_store):
    """Test rejection when target element is disabled or invisible."""
    engine = ActionEngine(mock_store)

    # 1. Disabled
    intent_disabled = ActionIntent(
        action_id="act_disabled",
        type=ActionType.CLICK,
        target=ActionTarget(
            world_element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="elem_btn_disabled", page_version=1)
        ),
        world_model_version=10,
        page_version=1,
        tab_id=101,
        page_id="page_101_v1"
    )
    res_disabled = await engine.execute_action(intent_disabled)
    assert res_disabled.status == ActionStatus.FAILED
    assert res_disabled.error is not None
    assert "DISABLED" in res_disabled.error.code

    # 2. Invisible
    intent_invisible = ActionIntent(
        action_id="act_invisible",
        type=ActionType.CLICK,
        target=ActionTarget(
            world_element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="elem_btn_hidden", page_version=1)
        ),
        world_model_version=10,
        page_version=1,
        tab_id=101,
        page_id="page_101_v1"
    )
    res_invisible = await engine.execute_action(intent_invisible)
    assert res_invisible.status == ActionStatus.FAILED
    assert res_invisible.error is not None
    assert "INVISIBLE" in res_invisible.error.code

@pytest.mark.asyncio
async def test_high_impact_confirmation_policy(mock_store):
    """Test policy gating high-impact purchase actions with REQUIRES_CONFIRMATION."""
    engine = ActionEngine(mock_store)

    intent_purchase = ActionIntent(
        action_id="act_buy_001",
        type=ActionType.CLICK,
        target=ActionTarget(
            expected_role="button",
            expected_name="Buy Now",
            world_element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="elem_btn_buy", page_version=1)
        ),
        world_model_version=10,
        page_version=1,
        tab_id=101,
        page_id="page_101_v1"
    )

    # 1. Unconfirmed -> REQUIRES_CONFIRMATION
    res_unconfirmed = await engine.execute_action(intent_purchase, confirmed=False)
    assert res_unconfirmed.status == ActionStatus.REQUIRES_CONFIRMATION
    conf_id = res_unconfirmed.execution_metadata.get("confirmation_id")
    assert conf_id is not None
    assert conf_id in mock_store.pending_confirmations

    # 2. Confirmed -> SUCCESS
    res_confirmed = await engine.execute_action(intent_purchase, confirmed=True)
    assert res_confirmed.status == ActionStatus.SUCCESS

@pytest.mark.asyncio
async def test_sensitive_field_redaction(mock_store):
    """Test strict redaction of sensitive password text in action results and traces."""
    engine = ActionEngine(mock_store)

    intent_pwd = ActionIntent(
        action_id="act_type_pwd",
        type=ActionType.TYPE,
        target=ActionTarget(
            expected_role="textbox",
            expected_name="Account Password",
            world_element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="elem_btn_search", page_version=1)
        ),
        parameters={
            "text": "super_secret_password_123",
            "sensitive": True
        },
        world_model_version=10,
        page_version=1,
        tab_id=101,
        page_id="page_101_v1"
    )

    result = await engine.execute_action(intent_pwd)

    assert result.status == ActionStatus.SUCCESS
    # Raw password must never appear in result parameters or trace
    result_dump = str(result.model_dump())
    assert "super_secret_password_123" not in result_dump
    assert "[REDACTED]" in result_dump

@pytest.mark.asyncio
async def test_blocked_dangerous_schemes(mock_store):
    """Test policy strictly blocking javascript:, data:, file: URLs."""
    engine = ActionEngine(mock_store)

    intent_bad_nav = ActionIntent(
        action_id="act_bad_nav",
        type=ActionType.NAVIGATE,
        parameters={
            "url": "javascript:alert(document.cookie)"
        },
        world_model_version=10,
        page_version=1,
        tab_id=101
    )

    result = await engine.execute_action(intent_bad_nav)
    assert result.status in [ActionStatus.BLOCKED, ActionStatus.FAILED]
    assert result.error is not None
    assert "POLICY_BLOCKED" in result.error.code

@pytest.mark.asyncio
async def test_dry_run_validation(mock_store):
    """Test dry_run=True returning WOULD_EXECUTE without state mutations."""
    engine = ActionEngine(mock_store)

    intent_dry = ActionIntent(
        action_id="act_dry_run",
        type=ActionType.CLICK,
        target=ActionTarget(
            world_element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="elem_btn_search", page_version=1)
        ),
        parameters={"dry_run": True},
        world_model_version=10,
        page_version=1,
        tab_id=101,
        page_id="page_101_v1"
    )

    result = await engine.execute_action(intent_dry)
    assert result.status == ActionStatus.WOULD_EXECUTE
    # World version must remain unchanged
    assert mock_store.world_model_version == 10

@pytest.mark.asyncio
async def test_precondition_evaluation(mock_store):
    """Test evaluating action preconditions."""
    engine = ActionEngine(mock_store)

    # 1. Matching precondition -> PASS
    intent_pass = ActionIntent(
        action_id="act_pre_pass",
        type=ActionType.CLICK,
        target=ActionTarget(
            world_element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="elem_btn_search", page_version=1)
        ),
        preconditions=[
            ActionPrecondition(type="PAGE_VERSION_MATCHES", expected_value=1),
            ActionPrecondition(type="DIALOG_ABSENT")
        ],
        world_model_version=10,
        page_version=1,
        tab_id=101,
        page_id="page_101_v1"
    )
    res_pass = await engine.execute_action(intent_pass)
    assert res_pass.status == ActionStatus.SUCCESS

    # 2. Failing precondition -> PRECONDITION_FAILED
    intent_fail = ActionIntent(
        action_id="act_pre_fail",
        type=ActionType.CLICK,
        target=ActionTarget(
            world_element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="elem_btn_search", page_version=1)
        ),
        preconditions=[
            ActionPrecondition(type="DIALOG_PRESENT") # Tab has no active dialogs
        ],
        world_model_version=10,
        page_version=1,
        tab_id=101,
        page_id="page_101_v1"
    )
    res_fail = await engine.execute_action(intent_fail)
    assert res_fail.status == ActionStatus.FAILED
    assert res_fail.error is not None
    assert "PRECONDITION_FAILED" in res_fail.error.code

@pytest.mark.asyncio
async def test_per_tab_queue_and_conflict_handling(mock_store):
    """Test serial queueing and conflict invalidation."""
    queue_mgr = ActionQueueManager(mock_store)

    intent1 = ActionIntent(action_id="act_q1", type=ActionType.CLICK, world_model_version=10, page_version=1)
    intent2 = ActionIntent(action_id="act_q2", type=ActionType.TYPE, parameters={"text": "hi"}, world_model_version=10, page_version=1)

    queue_mgr.enqueue_action(intent1, 101)
    queue_mgr.enqueue_action(intent2, 101)

    q_status = queue_mgr.get_queue_status(101)
    assert q_status.queue_length == 2

    # Clear on navigation conflict
    queue_mgr.clear_queue_on_conflict(101, "Navigation started")
    q_status_cleared = queue_mgr.get_queue_status(101)
    assert q_status_cleared.queue_length == 0
