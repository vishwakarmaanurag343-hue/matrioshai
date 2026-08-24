"""
MATRIOSHAI Unified Browser World Model Engine Unit Tests (Phase 7)

Comprehensive verification of:
1. World Model schema synthesis across windows, tabs, pages, frames, and observations
2. Immutable snapshotting and bounded temporal history
3. Deterministic state diff engine
4. Canonical element resolution (FOUND, STALE, PAGE_CHANGED, AMBIGUOUS, NOT_FOUND)
5. Model validation and self-healing reconciliation
6. Structured query engine (elements, tabs, pages)
7. Health checks and degraded mode
8. Strict privacy/security constraints (no credentials or auth tokens in state)
"""

import pytest
import time
from app.browser.state_store import (
    BrowserStateStore,
    WindowState,
    TabState,
    TabStatus,
    PageObservation,
    ViewportMetrics,
    InteractiveElement,
    BoundingBox,
    SemanticPageModel,
    PageInfo,
    SemanticElement,
    VisualPageModel,
    ScreenshotMetadata,
    VisualElement,
    VisualBoundingBox,
    WorldPageState,
    WorldElement,
    WorldElementRef,
    WorldElementSemanticState,
    WorldQuery
)
from app.browser.world_model import WorldModelEngine

@pytest.fixture
def mock_store():
    store = BrowserStateStore()
    store.set_browser_identity("test_chrome_browser", "124.0.0.0")

    # Add 2 Windows
    w1 = WindowState(window_id=1, focused=True, state="normal", tab_ids=[101, 102], active_tab_id=101)
    w2 = WindowState(window_id=2, focused=False, state="normal", tab_ids=[201], active_tab_id=201)
    store.windows = {1: w1, 2: w2}

    # Add Tabs
    t1 = TabState(tab_id=101, window_id=1, index=0, active=True, url="https://portal.example.com/dashboard", title="Dashboard", status=TabStatus.READY)
    t2 = TabState(tab_id=102, window_id=1, index=1, active=False, url="https://portal.example.com/settings", title="Settings", status=TabStatus.READY)
    t3 = TabState(tab_id=201, window_id=2, index=0, active=True, url="https://news.example.com", title="News", status=TabStatus.READY)
    store.tabs = {101: t1, 102: t2, 201: t3}
    store.active_tab_id = 101

    # Add Page Observation for Tab 101
    obs = PageObservation(
        observation_id="obs_101_1",
        tab_id=101,
        url="https://portal.example.com/dashboard",
        title="Dashboard",
        viewport=ViewportMetrics(width=1280, height=800),
        interactive_elements=[
            InteractiveElement(
                element_id="elem_btn_search",
                tag_name="button",
                role="button",
                text="Search Flights",
                bounding_box=BoundingBox(x=100, y=100, width=120, height=35, top=100, left=100, right=220, bottom=135)
            )
        ]
    )
    store.store_observation(obs)

    # Add Semantic Model for Tab 101
    sem = SemanticPageModel(
        semantic_model_id="sem_101_1",
        observation_id="obs_101_1",
        tab_id=101,
        page=PageInfo(url="https://portal.example.com/dashboard", title="Dashboard"),
        interactive_elements=[
            SemanticElement(
                element_id="elem_btn_search",
                role="button",
                name="Search Flights",
                tag_name="button",
                bounding_box=BoundingBox(x=100, y=100, width=120, height=35, top=100, left=100, right=220, bottom=135)
            )
        ]
    )
    store.store_semantic_model(sem)

    # Add Visual Model for Tab 101
    vis = VisualPageModel(
        visual_model_id="vis_101_1",
        observation_id="obs_101_1",
        semantic_model_id="sem_101_1",
        tab_id=101,
        screenshot=ScreenshotMetadata(
            id="scr_101_1",
            tab_id=101,
            url="https://portal.example.com/dashboard",
            width=1280,
            height=800,
            original_width=1280,
            original_height=800
        ),
        viewport=ViewportMetrics(width=1280, height=800),
        visual_elements=[
            VisualElement(
                visual_id="vis_elem_1",
                semantic_element_id="elem_btn_search",
                type="button",
                tag_name="button",
                role="button",
                name="Search Flights",
                dom_box=VisualBoundingBox(x=100, y=100, width=120, height=35, top=100, left=100, right=220, bottom=135),
                screenshot_box=VisualBoundingBox(x=100, y=100, width=120, height=35, top=100, left=100, right=220, bottom=135)
            )
        ]
    )
    store.store_visual_model(vis)

    # Add Page State for Tab 101
    p1 = WorldPageState(
        page_id="page_101_abc",
        tab_id=101,
        url="https://portal.example.com/dashboard",
        origin="https://portal.example.com",
        title="Dashboard",
        page_version=1,
        observation_id="obs_101_1",
        semantic_model_id="sem_101_1",
        visual_model_id="vis_101_1",
        active_dialogs=["modal_promo"]
    )
    store.page_states[101] = p1

    # Add Synthesized WorldElement for Tab 101
    we = WorldElement(
        element_ref=WorldElementRef(
            page_id="page_101_abc",
            observation_id="obs_101_1",
            element_id="elem_btn_search",
            semantic_model_id="sem_101_1",
            visual_id="vis_elem_1",
            tag_name="button",
            role="button",
            name="Search Flights",
            page_version=1,
            stable_dom_identity="btn-search"
        ),
        role="button",
        name="Search Flights",
        semantic_state=WorldElementSemanticState(type="button", enabled=True, focused=False),
        geometry=VisualBoundingBox(x=100, y=100, width=120, height=35, top=100, left=100, right=220, bottom=135),
        visible=True,
        enabled=True,
        page_version=1
    )
    store.world_elements[101] = [we]

    return store

def test_world_model_synthesis(mock_store):
    """Test comprehensive synthesis of the BrowserWorldModel from state store subsystems."""
    engine = WorldModelEngine(mock_store)
    world = engine.build_current_world(bridge_connected=True)

    assert world.world_model_id.startswith("world_")
    assert world.browser_session.browser_session_id == "test_chrome_browser"
    assert len(world.windows) == 2
    assert len(world.tabs) == 3
    assert world.active_tab_id == 101
    assert world.active_window is not None
    assert world.active_window.window_id == 1
    assert len(world.pages) == 1
    assert world.pages[0].page_id == "page_101_abc"
    assert world.observations.get(101) == "obs_101_1"
    assert world.semantic_models.get(101) == "sem_101_1"
    assert world.visual_models.get(101) == "vis_101_1"
    assert world.status == "READY"
    assert world.health.status == "READY"

def test_immutable_snapshot_creation(mock_store):
    """Test creating immutable snapshots and verifying snapshot history isolation."""
    engine = WorldModelEngine(mock_store)

    snap1 = engine.create_snapshot(reason="initial_state")
    assert snap1.snapshot_id.startswith("snap_")
    assert snap1.world_model_version == 1
    assert len(snap1.tab_states) == 3
    assert snap1.active_tab_id == 101

    # Mutate store
    mock_store.tabs[101].url = "https://portal.example.com/checkout"
    mock_store.world_model_version = 2

    snap2 = engine.create_snapshot(reason="after_navigation")
    assert snap2.world_model_version == 2
    assert snap2.tab_states[0].url == "https://portal.example.com/checkout"

    # Verify snap1 is completely immutable
    assert snap1.tab_states[0].url == "https://portal.example.com/dashboard"
    assert len(mock_store.get_world_snapshots()) == 2

def test_world_state_diff_engine(mock_store):
    """Test deterministic diff computation between two snapshots."""
    engine = WorldModelEngine(mock_store)

    snap1 = engine.create_snapshot(reason="before_action")

    # Perform mutations: add tab 103, remove tab 102, change dialogs
    mock_store.tabs.pop(102)
    mock_store.tabs[103] = TabState(tab_id=103, window_id=1, index=2, active=False, url="https://promo.example.com", title="Promo")
    mock_store.page_states[101].active_dialogs = [] # Closed dialog
    mock_store.world_model_version = 2

    snap2 = engine.create_snapshot(reason="after_action")

    diff = engine.diff_world(snap1, snap2)

    assert diff.source_snapshot_id == snap1.snapshot_id
    assert diff.target_snapshot_id == snap2.snapshot_id
    assert len(diff.tabs_diff.added) == 1
    assert diff.tabs_diff.added[0]["tab_id"] == 103
    assert len(diff.tabs_diff.removed) == 1
    assert diff.tabs_diff.removed[0]["tab_id"] == 102
    assert len(diff.dialogs_diff.removed) == 1
    assert diff.dialogs_diff.removed[0] == "modal_promo"
    assert any("Added 1 tab" in s for s in diff.summary)
    assert any("Removed 1 tab" in s for s in diff.summary)
    assert any("Closed dialog" in s for s in diff.summary)

def test_canonical_element_resolution(mock_store):
    """Test resolving WorldElementRefs with exact, stale, and page changed statuses."""
    engine = WorldModelEngine(mock_store)

    ref = WorldElementRef(
        page_id="page_101_abc",
        observation_id="obs_101_1",
        element_id="elem_btn_search",
        role="button",
        name="Search Flights",
        page_version=1,
        stable_dom_identity="btn-search"
    )

    # 1. Exact match
    res_exact = engine.resolve_world_element(ref, tab_id=101)
    assert res_exact.status == "FOUND"
    assert res_exact.element is not None
    assert res_exact.element.name == "Search Flights"

    # 2. Stale reference (page version advanced)
    mock_store.page_states[101].page_version = 2
    res_stale = engine.resolve_world_element(ref, tab_id=101)
    assert res_stale.status == "STALE"
    assert len(res_stale.candidates) >= 1

    # 3. Page changed reference (different page ID)
    ref_other_page = ref.model_copy()
    ref_other_page.page_id = "page_old_navigation_999"
    res_page_changed = engine.resolve_world_element(ref_other_page, tab_id=101)
    assert res_page_changed.status == "PAGE_CHANGED"

    # 4. Tab closed reference
    res_tab_closed = engine.resolve_world_element(ref, tab_id=999)
    assert res_tab_closed.status == "TAB_CLOSED"

def test_world_model_validation(mock_store):
    """Test world model integrity and validation rules."""
    engine = WorldModelEngine(mock_store)
    world = engine.build_current_world(bridge_connected=True)

    val_valid = engine.validate_world(world)
    assert val_valid["is_valid"] is True
    assert val_valid["status"] == "VALID"
    assert len(val_valid["errors"]) == 0

    # Introduce corruption: active tab not in tabs list
    world_corrupt = world.model_copy(deep=True)
    world_corrupt.active_tab_id = 999
    val_invalid = engine.validate_world(world_corrupt)
    assert val_invalid["is_valid"] is False
    assert val_invalid["status"] == "INVALID"
    assert any("does not exist in tabs list" in err for err in val_invalid["errors"])

def test_self_healing_reconciliation(mock_store):
    """Test state reconciliation repairing desynced tabs."""
    engine = WorldModelEngine(mock_store)

    actual_windows = [{"window_id": 1, "focused": True, "state": "normal", "tab_ids": [101]}]
    actual_tabs = [{"tab_id": 101, "window_id": 1, "index": 0, "active": True, "url": "https://reconciled.example.com", "title": "Reconciled", "status": "READY"}]

    reconciled_world = engine.reconcile_world(actual_windows, actual_tabs)

    assert len(reconciled_world.windows) == 1
    assert len(reconciled_world.tabs) == 1
    assert reconciled_world.tabs[0].url == "https://reconciled.example.com"
    assert reconciled_world.active_tab_id == 101

def test_structured_query_engine(mock_store):
    """Test querying elements, tabs, and pages via structured WorldQuery."""
    engine = WorldModelEngine(mock_store)

    # Element query
    q_elem = WorldQuery(type="element", role="button", tab_id=101)
    res_elem = engine.query_world(q_elem)
    assert res_elem.status == "FOUND"
    assert res_elem.count == 1
    assert res_elem.elements[0].name == "Search Flights"

    # Tab query
    q_tab = WorldQuery(type="tab")
    res_tab = engine.query_world(q_tab)
    assert res_tab.status == "FOUND"
    assert res_tab.count == 3

    # Page query
    q_page = WorldQuery(type="page", tab_id=101)
    res_page = engine.query_world(q_page)
    assert res_page.status == "FOUND"
    assert res_page.count == 1
    assert res_page.pages[0].page_id == "page_101_abc"

def test_health_and_degraded_mode(mock_store):
    """Test health reporting in normal, degraded, and disconnected modes."""
    engine = WorldModelEngine(mock_store)

    # 1. Normal
    h1 = engine.check_health(bridge_connected=True)
    assert h1.status == "READY"
    assert h1.browser_connected is True

    # 2. Degraded: visual model removed but semantic model remains
    mock_store.latest_visual_models.clear()
    h2 = engine.check_health(bridge_connected=True)
    assert h2.status == "DEGRADED"

    # 3. Disconnected
    h3 = engine.check_health(bridge_connected=False)
    assert h3.status == "DISCONNECTED"

def test_strict_security_and_credential_sanitization(mock_store):
    """Verify strictly that no passwords, cookies, or auth tokens are stored in the World Model."""
    engine = WorldModelEngine(mock_store)
    world = engine.build_current_world(bridge_connected=True)
    world_dump = str(world.model_dump())

    forbidden_keywords = ["password", "cookie", "set-cookie", "bearer ", "authorization", "cvv", "credit_card"]
    for kw in forbidden_keywords:
        assert kw not in world_dump.lower()
