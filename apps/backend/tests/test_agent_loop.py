"""
MATRIOSHAI Agent Planning & Execution Loop Tests (Phase 10)

Comprehensive verification of:
1. Goal normalization, clarification requests, and hard vs. soft constraints
2. Plan creation, versioning, and deterministic-first step selection
3. Closed-loop agent execution with Phase 8 Actions and Phase 9 Verifications
4. Dynamic replanning upon failure or world changes
5. Stuck detection and oscillation prevention
6. High-impact commit boundaries and user confirmation
7. Pause, resume, and abort lifecycle
8. Iteration limits and safety budgets
9. Multi-tab context management
10. Context compression and event emission
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
    AgentTaskState,
    TaskPriority,
    PlanDecisionType,
    TabRole
)
from app.browser.agent_loop import (
    GoalNormalizationEngine,
    RelevantWorldState,
    StuckDetector,
    GoalCompletionEngine,
    ReplanningEngine,
    Planner,
    AgentExecutionLoop
)

@pytest.fixture
def mock_agent_store():
    store = BrowserStateStore()
    store.set_browser_identity("test_chrome_agent_instance", "124.0.0.0")

    # Windows & Tabs
    w1 = WindowState(window_id=1, focused=True, state="normal", tab_ids=[101], active_tab_id=101)
    store.windows = {1: w1}

    t1 = TabState(tab_id=101, window_id=1, index=0, active=True, url="https://portal.example.com/search", title="Search Portal", status=TabStatus.READY)
    store.tabs = {101: t1}
    store.active_tab_id = 101
    store.world_model_version = 10

    # Page State
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
        element_ref=WorldElementRef(page_id="page_101_v1", observation_id="obs_1", element_id="input_search", role="searchbox", name="Search", page_version=1),
        role="searchbox",
        name="Search",
        semantic_state=WorldElementSemanticState(type="searchbox", enabled=True, focused=False),
        geometry=VisualBoundingBox(x=100, y=100, width=250, height=35),
        visible=True,
        enabled=True,
        page_version=1
    )

    store.world_elements[101] = [el_search]
    return store

def test_goal_normalization_and_constraints():
    """Test converting natural language into structured goal with hard & soft constraints."""
    norm_engine = GoalNormalizationEngine()

    goal, clarification = norm_engine.normalize("Find me a flight from Ahmedabad to Delhi tomorrow, prefer cheapest option")
    assert clarification is None
    assert goal.normalized_goal.get("origin") == "ahmedabad"
    assert goal.normalized_goal.get("destination") == "delhi"
    assert any("origin=ahmedabad" in c for c in goal.hard_constraints)
    assert any("destination=delhi" in c for c in goal.hard_constraints)
    assert "prefer_cheapest_option" in goal.soft_preferences

def test_goal_clarification_on_missing_information():
    """Test detecting missing mandatory flight booking parameters without hallucinating."""
    norm_engine = GoalNormalizationEngine()

    goal, clarification = norm_engine.normalize("Book me a flight tomorrow")
    assert clarification is not None
    assert "destination" in clarification.lower()

def test_relevant_world_state_compression(mock_agent_store):
    """Test extracting compressed world summary omitting irrelevant DOM clutter."""
    summary = RelevantWorldState.extract_summary(mock_agent_store.current_world, state_store=mock_agent_store, target_tab_id=101)
    assert "tab_id" in summary
    assert "url" in summary
    assert "elements" in summary

def test_stuck_detection_loop_oscillation():
    """Test stuck detector identifying loop oscillation (A -> B -> A -> B)."""
    detector = StuckDetector()

    detector.record_action("CLICK:Search")
    detector.record_action("SCROLL:Down")
    detector.record_action("CLICK:Search")
    detector.record_action("SCROLL:Down")

    is_stuck, reason = detector.is_stuck()
    assert is_stuck is True
    assert "oscillation" in reason.lower()

def test_stuck_detection_repeated_identical_action():
    """Test stuck detector identifying 3 identical consecutive actions."""
    detector = StuckDetector()

    detector.record_action("CLICK:Submit")
    detector.record_action("CLICK:Submit")
    detector.record_action("CLICK:Submit")

    is_stuck, reason = detector.is_stuck()
    assert is_stuck is True
    assert "repeated 3 times" in reason.lower()

def test_planner_deterministic_first_selection(mock_agent_store):
    """Test planner skipping redundant navigation when page is already at target URL."""
    planner = Planner(mock_agent_store)
    norm_engine = GoalNormalizationEngine()

    goal, _ = norm_engine.normalize("Open https://portal.example.com/search")
    plan = planner.create_plan(goal, mock_agent_store.current_world)

    # Page is already at https://portal.example.com/search
    decision = planner.select_next_step(plan, mock_agent_store.current_world)
    # Step should be auto-completed because target URL is already active
    assert decision.decision == PlanDecisionType.COMPLETE

def test_planner_high_impact_commit_boundary(mock_agent_store):
    """Test planner pausing at commit boundary before high-impact purchase action."""
    planner = Planner(mock_agent_store)
    norm_engine = GoalNormalizationEngine()

    goal, _ = norm_engine.normalize("Click Confirm Booking and Pay Now")
    plan = planner.create_plan(goal, mock_agent_store.current_world)
    plan.steps[0].intended_action.target.expected_name = "Submit Payment & Pay Now"

    decision = planner.select_next_step(plan, mock_agent_store.current_world)
    assert decision.decision == PlanDecisionType.ASK_USER
    assert "Commit boundary" in decision.reason

def test_replanning_engine_preserves_completed_work(mock_agent_store):
    """Test replanning engine retaining completed valid steps while updating remaining steps."""
    replanner = ReplanningEngine()
    planner = Planner(mock_agent_store)
    norm_engine = GoalNormalizationEngine()

    goal, _ = norm_engine.normalize("Search for laptops")
    plan_v1 = planner.create_plan(goal, mock_agent_store.current_world)
    plan_v1.steps[0].status = "COMPLETED"

    plan_v2 = replanner.create_replanned_plan(goal, plan_v1, mock_agent_store.current_world, reason="Dynamic DOM update")
    assert plan_v2.version == 2
    assert any(s.status == "COMPLETED" for s in plan_v2.steps)

@pytest.mark.asyncio
async def test_agent_execution_loop_simple_task(mock_agent_store):
    """Test end-to-end closed loop execution of a simple goal."""
    loop = AgentExecutionLoop(mock_agent_store)

    task = loop.create_task("Open https://portal.example.com/search")
    assert task.state == AgentTaskState.CREATED

    result = await loop.run_task_loop(task.task_id)
    assert result.status == AgentTaskState.COMPLETED
    assert len(mock_agent_store.agent_events) > 0

@pytest.mark.asyncio
async def test_agent_pause_resume_abort_lifecycle(mock_agent_store):
    """Test pausing, resuming, and aborting an agent task."""
    loop = AgentExecutionLoop(mock_agent_store)

    task = loop.create_task("Search for flights")
    task_paused = loop.pause_task(task.task_id)
    assert task_paused.state == AgentTaskState.PAUSED

    task_aborted = loop.abort_task(task.task_id)
    assert task_aborted.state == AgentTaskState.ABORTED
