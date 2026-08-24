"""
MATRIOSHAI Centralized Browser State Store (Phases 3, 4, 5, 6 & 7)

Thread-safe, in-memory state store tracking browser identity, open windows,
tabs, active navigation state, audit logs, Phase 4 Page Observations,
Phase 5 Semantic Page Models, Phase 6 Visual Page Models & Screenshots,
and Phase 7 Unified Browser World Model with immutable historical snapshots.
"""

import threading
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple
from pydantic import BaseModel, Field
from app.core.logging import logger

class TabStatus(str, Enum):
    CREATED = "CREATED"
    LOADING = "LOADING"
    READY = "READY"
    NAVIGATING = "NAVIGATING"
    ERROR = "ERROR"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"

class WindowState(BaseModel):
    window_id: int
    type: str = "normal"
    focused: bool = False
    state: str = "normal"
    tab_ids: List[int] = Field(default_factory=list)
    active_tab_id: Optional[int] = None

class TabState(BaseModel):
    tab_id: int
    window_id: int
    index: int = 0
    active: bool = False
    url: str = ""
    title: str = ""
    status: TabStatus = TabStatus.UNKNOWN
    favIconUrl: Optional[str] = None
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class NavigationStatus(str, Enum):
    REQUESTED = "REQUESTED"
    STARTED = "STARTED"
    LOADING = "LOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class NavigationResult(BaseModel):
    navigation_id: str
    tab_id: int
    requested_url: str
    final_url: Optional[str] = None
    status: NavigationStatus
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[Dict[str, str]] = None

class BrowserAuditLog(BaseModel):
    action_id: str
    type: str
    browser_id: str
    tab_id: Optional[int] = None
    requested_url: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: str = "success"
    error: Optional[str] = None

# ============================================================================
# PHASE 4: PAGE OBSERVATION DATA STRUCTURES
# ============================================================================

class ViewportMetrics(BaseModel):
    width: int = 0
    height: int = 0
    scroll_x: int = 0
    scroll_y: int = 0
    document_width: int = 0
    document_height: int = 0

class BoundingBox(BaseModel):
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    top: int = 0
    left: int = 0
    right: int = 0
    bottom: int = 0

class InteractiveElement(BaseModel):
    element_id: str
    tag_name: str
    role: str
    text: str = ""
    href: Optional[str] = None
    input_type: Optional[str] = None
    value: Optional[str] = None
    placeholder: Optional[str] = None
    bounding_box: BoundingBox
    is_visible: bool = True
    is_in_viewport: bool = True
    is_enabled: bool = True
    attributes: Dict[str, str] = Field(default_factory=dict)

class HeadingElement(BaseModel):
    level: int
    text: str
    id: Optional[str] = None

class LandmarkElement(BaseModel):
    role: str
    tag_name: str
    label: Optional[str] = None

class FrameElement(BaseModel):
    frame_id: str
    src: str = ""
    name: Optional[str] = None
    is_cross_origin: bool = False

class PageObservation(BaseModel):
    observation_id: str
    tab_id: int
    url: str
    title: str = ""
    document_state: str = "complete"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    viewport: ViewportMetrics
    visible_text: List[str] = Field(default_factory=list)
    headings: List[HeadingElement] = Field(default_factory=list)
    landmarks: List[LandmarkElement] = Field(default_factory=list)
    interactive_elements: List[InteractiveElement] = Field(default_factory=list)
    frames: List[FrameElement] = Field(default_factory=list)

# ============================================================================
# PHASE 5: SEMANTIC PAGE & ACCESSIBILITY INTELLIGENCE MODELS
# ============================================================================

class SemanticElementRef(BaseModel):
    semantic_model_id: str
    observation_id: str
    element_id: str
    role: str
    name: str
    tag_name: str
    stable_id: Optional[str] = None
    attributes: Dict[str, str] = Field(default_factory=dict)

class SemanticElementRelationships(BaseModel):
    labelled_by: Optional[str] = None
    described_by: Optional[str] = None
    controls: Optional[str] = None
    owns: List[str] = Field(default_factory=list)

class SemanticElement(BaseModel):
    element_id: str
    role: str
    name: str
    description: Optional[str] = None
    tag_name: str
    semantic_type: str = "UNKNOWN"
    source: str = "native_html"
    confidence: str = "HIGH"

    visible: bool = True
    enabled: bool = True
    focused: bool = False
    required: bool = False
    readonly: bool = False
    selected: bool = False
    checked: bool = False
    expanded: Optional[bool] = None

    sensitive: bool = False
    value_available: bool = True
    value_preview: Optional[str] = None

    bounding_box: BoundingBox
    parent_id: Optional[str] = None
    child_ids: List[str] = Field(default_factory=list)
    relationships: SemanticElementRelationships = Field(default_factory=SemanticElementRelationships)
    attributes: Dict[str, str] = Field(default_factory=dict)

class FormSemanticGroup(BaseModel):
    form_id: str
    name: str
    action: Optional[str] = None
    method: Optional[str] = None
    field_ids: List[str] = Field(default_factory=list)
    submit_button_ids: List[str] = Field(default_factory=list)
    required_field_ids: List[str] = Field(default_factory=list)

class RadioOption(BaseModel):
    element_id: str
    name: str
    selected: bool = False
    disabled: bool = False

class RadioSemanticGroup(BaseModel):
    group_name: str
    label: str
    selected_element_id: Optional[str] = None
    options: List[RadioOption] = Field(default_factory=list)

class TabOption(BaseModel):
    element_id: str
    name: str
    selected: bool = False
    controls_panel_id: Optional[str] = None

class TabSemanticGroup(BaseModel):
    tab_list_id: Optional[str] = None
    tabs: List[TabOption] = Field(default_factory=list)

class DialogSemanticGroup(BaseModel):
    dialog_id: str
    name: str
    role: str = "dialog"
    visible: bool = True
    interactive_element_ids: List[str] = Field(default_factory=list)

class TableCell(BaseModel):
    text: str
    is_header: bool = False
    row_index: int = 0
    col_index: int = 0

class TableSemanticGroup(BaseModel):
    table_id: str
    name: Optional[str] = None
    headers: List[str] = Field(default_factory=list)
    row_count: int = 0
    col_count: int = 0
    rows: List[List[TableCell]] = Field(default_factory=list)

class ListSemanticGroup(BaseModel):
    list_id: str
    type: str = "unordered"
    name: Optional[str] = None
    item_count: int = 0
    items: List[str] = Field(default_factory=list)

class SemanticHeading(BaseModel):
    level: int
    text: str
    element_id: str

class SemanticLandmark(BaseModel):
    role: str
    tag_name: str
    label: Optional[str] = None
    element_ids: List[str] = Field(default_factory=list)

class PageInfo(BaseModel):
    url: str
    title: str
    language: str = "en"

class SemanticPageIndexes(BaseModel):
    byRole: Dict[str, List[str]] = Field(default_factory=dict)
    byName: Dict[str, List[str]] = Field(default_factory=dict)
    byLabel: Dict[str, List[str]] = Field(default_factory=dict)
    byId: Dict[str, str] = Field(default_factory=dict)
    byTag: Dict[str, List[str]] = Field(default_factory=dict)
    byType: Dict[str, List[str]] = Field(default_factory=dict)

class SemanticPageModel(BaseModel):
    semantic_model_id: str
    model_version: int = 1
    observation_id: str
    tab_id: int
    is_stale: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    page: PageInfo
    landmarks: List[SemanticLandmark] = Field(default_factory=list)
    headings: List[SemanticHeading] = Field(default_factory=list)
    interactive_elements: List[SemanticElement] = Field(default_factory=list)
    forms: List[FormSemanticGroup] = Field(default_factory=list)
    radio_groups: List[RadioSemanticGroup] = Field(default_factory=list)
    tabs: List[TabSemanticGroup] = Field(default_factory=list)
    dialogs: List[DialogSemanticGroup] = Field(default_factory=list)
    tables: List[TableSemanticGroup] = Field(default_factory=list)
    lists: List[ListSemanticGroup] = Field(default_factory=list)
    indexes: SemanticPageIndexes = Field(default_factory=SemanticPageIndexes)
    debug_tree: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SemanticQuery(BaseModel):
    role: Optional[str] = None
    name: Optional[str] = None
    label: Optional[str] = None
    text: Optional[str] = None
    type: Optional[str] = None
    id: Optional[str] = None
    exact: Optional[bool] = True

class QueryResult(BaseModel):
    status: str
    element: Optional[SemanticElement] = None
    matches: List[SemanticElementRef] = Field(default_factory=list)
    confidence: str = "HIGH"
    query: SemanticQuery
    message: Optional[str] = None

class ResolveResult(BaseModel):
    status: str
    element: Optional[SemanticElement] = None
    matches: List[SemanticElementRef] = Field(default_factory=list)
    reference: SemanticElementRef
    message: Optional[str] = None

# ============================================================================
# PHASE 6: VISUAL PAGE INTELLIGENCE MODELS
# ============================================================================

class VisualBoundingBox(BaseModel):
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    top: int = 0
    left: int = 0
    right: int = 0
    bottom: int = 0
    coordinate_system: str = "DOM_VIEWPORT"

class ScreenshotMetadata(BaseModel):
    id: str
    tab_id: int
    url: str
    width: int
    height: int
    device_pixel_ratio: float = 1.0
    scroll_x: int = 0
    scroll_y: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    viewport_only: bool = True
    scaled: bool = False
    original_width: int
    original_height: int
    format: str = "png"
    bytes: Optional[int] = None
    privacy_mode: str = "STANDARD"
    redacted_regions_count: int = 0
    observation_id: Optional[str] = None
    semantic_model_id: Optional[str] = None
    visual_version: int = 1

class VisualElementMapping(BaseModel):
    element_id: str
    visual_id: str
    dom_box: VisualBoundingBox
    screenshot_box: VisualBoundingBox
    confidence: str = "HIGH"
    visibility: str = "fully_visible"
    occluded: bool = False
    partially_occluded: bool = False
    z_index: int = 0

class VisualRegion(BaseModel):
    region_id: str
    type: str
    label: Optional[str] = None
    bounding_box: VisualBoundingBox
    screenshot_box: VisualBoundingBox
    z_index: int = 0
    is_fixed: bool = False
    is_sticky: bool = False
    element_ids: List[str] = Field(default_factory=list)
    visual_element_ids: List[str] = Field(default_factory=list)

class VisualElementState(BaseModel):
    disabled: Optional[bool] = None
    focused: Optional[bool] = None
    selected: Optional[bool] = None
    expanded: Optional[bool] = None
    checked: Optional[bool] = None

class VisualElement(BaseModel):
    visual_id: str
    semantic_element_id: Optional[str] = None
    type: str
    tag_name: str
    role: Optional[str] = None
    name: Optional[str] = None
    dom_box: VisualBoundingBox
    screenshot_box: VisualBoundingBox
    visibility: str = "fully_visible"
    z_index: int = 0
    is_interactive: bool = False
    is_fixed: bool = False
    is_sticky: bool = False
    is_canvas: bool = False
    is_svg: bool = False
    is_image: bool = False
    is_video: bool = False
    confidence: str = "HIGH"
    source: str = "dom_mapped"
    state: VisualElementState = Field(default_factory=VisualElementState)
    attributes: Dict[str, str] = Field(default_factory=dict)

class VisualOverlay(BaseModel):
    overlay_id: str
    visual_id: str
    type: str = "dialog"
    bounding_box: VisualBoundingBox
    screenshot_box: VisualBoundingBox
    z_index: int = 100
    is_visible: bool = True
    child_visual_ids: List[str] = Field(default_factory=list)

class FixedElement(BaseModel):
    element_id: str
    visual_id: str
    bounding_box: VisualBoundingBox
    screenshot_box: VisualBoundingBox
    z_index: int = 0
    position_type: str = "fixed"

class VisualPageIndexes(BaseModel):
    byVisualType: Dict[str, List[str]] = Field(default_factory=dict)
    bySemanticElement: Dict[str, str] = Field(default_factory=dict)
    byRegion: Dict[str, List[str]] = Field(default_factory=dict)
    byInteractive: List[str] = Field(default_factory=list)
    byVisibility: Dict[str, List[str]] = Field(default_factory=dict)

class VisualPageModel(BaseModel):
    visual_model_id: str
    visual_version: int = 1
    observation_id: str
    semantic_model_id: str
    tab_id: int
    is_stale: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    screenshot: ScreenshotMetadata
    viewport: ViewportMetrics
    regions: List[VisualRegion] = Field(default_factory=list)
    overlays: List[VisualOverlay] = Field(default_factory=list)
    fixed_elements: List[FixedElement] = Field(default_factory=list)
    sticky_elements: List[FixedElement] = Field(default_factory=list)
    visual_elements: List[VisualElement] = Field(default_factory=list)
    mappings: List[VisualElementMapping] = Field(default_factory=list)
    indexes: VisualPageIndexes = Field(default_factory=VisualPageIndexes)
    privacy_mode: str = "STANDARD"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class VisualQuery(BaseModel):
    type: Optional[str] = None
    region_id: Optional[str] = None
    semantic_element_id: Optional[str] = None
    interactive_only: Optional[bool] = False
    visible_only: Optional[bool] = False
    min_confidence: Optional[str] = None

class VisualQueryResult(BaseModel):
    status: str
    elements: List[VisualElement] = Field(default_factory=list)
    mappings: List[VisualElementMapping] = Field(default_factory=list)
    count: int = 0
    query: VisualQuery
    message: Optional[str] = None

class CandidateElement(BaseModel):
    element: VisualElement
    z_index: int = 0
    occluded: bool = False
    confidence: str = "HIGH"

class PointQueryResult(BaseModel):
    status: str
    x: int
    y: int
    coordinate_system: str = "DOM_VIEWPORT"
    topmost_element: Optional[VisualElement] = None
    candidates: List[CandidateElement] = Field(default_factory=list)
    message: Optional[str] = None

# ============================================================================
# PHASE 7: UNIFIED BROWSER WORLD MODEL DATA STRUCTURES
# ============================================================================

class BrowserSessionState(BaseModel):
    browser_session_id: str
    extension_session_id: str
    connected: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    capabilities: List[str] = Field(default_factory=list)
    active_window_id: Optional[int] = None
    active_tab_id: Optional[int] = None

class WorldWindowState(BaseModel):
    window_id: int
    focused: bool = False
    state: str = "normal"
    width: Optional[int] = None
    height: Optional[int] = None
    top: Optional[int] = None
    left: Optional[int] = None
    tab_ids: List[int] = Field(default_factory=list)
    active_tab_id: Optional[int] = None

class WorldTabState(BaseModel):
    tab_id: int
    window_id: int
    index: int = 0
    active: bool = False
    highlighted: bool = False
    pinned: bool = False
    url: str = ""
    title: str = ""
    status: TabStatus = TabStatus.UNKNOWN
    favIconUrl: Optional[str] = None
    opener_tab_id: Optional[int] = None
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class WorldFrameState(BaseModel):
    frame_id: str
    parent_frame_id: Optional[str] = None
    tab_id: int
    origin: str = ""
    url: str = ""
    accessible: bool = True
    page_version: int = 1
    semantic_model_reference: Optional[str] = None
    visual_reference: Optional[str] = None

class FrameTreeNode(BaseModel):
    frame: WorldFrameState
    children: List["FrameTreeNode"] = Field(default_factory=list)

class FrameTree(BaseModel):
    tab_id: int
    root_frame: FrameTreeNode
    frame_count: int = 1

class NavigationHistoryItem(BaseModel):
    navigation_id: str
    tab_id: int
    url: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    title: Optional[str] = None

class NavigationState(BaseModel):
    current_url: str = ""
    previous_url: Optional[str] = None
    navigation_id: str = ""
    navigation_type: str = "INITIAL"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    status: str = "navigation_completed"
    history: List[NavigationHistoryItem] = Field(default_factory=list)

class WorldPageState(BaseModel):
    page_id: str
    tab_id: int
    url: str
    origin: str
    title: str = ""
    ready_state: str = "complete"
    visibility_state: str = "visible"
    page_version: int = 1
    observation_id: Optional[str] = None
    semantic_model_id: Optional[str] = None
    visual_model_id: Optional[str] = None
    scroll_x: int = 0
    scroll_y: int = 0
    viewport_width: int = 1280
    viewport_height: int = 800
    document_width: int = 1280
    document_height: int = 800
    active_dialogs: List[str] = Field(default_factory=list)
    focused_element_id: Optional[str] = None
    has_overlay: bool = False
    lifecycle: str = "READY"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class WorldElementRef(BaseModel):
    page_id: str
    observation_id: str
    element_id: str
    semantic_model_id: Optional[str] = None
    visual_id: Optional[str] = None
    tag_name: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    page_version: int = 1
    stable_dom_identity: Optional[str] = None

class WorldElementSemanticState(BaseModel):
    type: str = "UNKNOWN"
    description: Optional[str] = None
    focused: bool = False
    disabled: bool = False
    required: bool = False
    checked: bool = False
    expanded: Optional[bool] = None
    sensitive: bool = False

class WorldElementVisualState(BaseModel):
    visual_id: str
    visibility: str = "fully_visible"
    occluded: bool = False
    partially_occluded: bool = False
    z_index: int = 0
    is_canvas: bool = False
    is_svg: bool = False

class WorldElement(BaseModel):
    element_ref: WorldElementRef
    role: str
    name: str
    semantic_state: WorldElementSemanticState = Field(default_factory=WorldElementSemanticState)
    visual_state: Optional[WorldElementVisualState] = None
    geometry: VisualBoundingBox
    parent_ref: Optional[str] = None
    child_refs: List[str] = Field(default_factory=list)
    visible: bool = True
    enabled: bool = True
    semantic_confidence: str = "HIGH"
    visual_confidence: str = "HIGH"
    source: str = "semantic_engine"
    page_version: int = 1

class WorldElementResolution(BaseModel):
    status: str
    element: Optional[WorldElement] = None
    reference: WorldElementRef
    candidates: List[WorldElementRef] = Field(default_factory=list)
    message: Optional[str] = None

class WorldStateTransition(BaseModel):
    transition_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_version: int
    target_version: int
    type: str
    tab_id: Optional[int] = None
    changed_entities: Dict[str, Any] = Field(default_factory=dict)
    summary: str

class EntityDiff(BaseModel):
    added: List[Any] = Field(default_factory=list)
    removed: List[Any] = Field(default_factory=list)
    changed: List[Dict[str, Any]] = Field(default_factory=list)
    unchanged_count: int = 0

class WorldStateDiff(BaseModel):
    diff_id: str
    source_snapshot_id: str
    target_snapshot_id: str
    source_version: int
    target_version: int
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tabs_diff: EntityDiff = Field(default_factory=EntityDiff)
    pages_diff: EntityDiff = Field(default_factory=EntityDiff)
    elements_diff: EntityDiff = Field(default_factory=EntityDiff)
    dialogs_diff: EntityDiff = Field(default_factory=EntityDiff)
    navigation_changed: bool = False
    summary: List[str] = Field(default_factory=list)

class BrowserWorldSnapshot(BaseModel):
    snapshot_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    world_model_version: int
    active_tab_id: Optional[int] = None
    tab_states: List[WorldTabState] = Field(default_factory=list)
    page_states: List[WorldPageState] = Field(default_factory=list)
    semantic_references: Dict[int, str] = Field(default_factory=dict)
    visual_references: Dict[int, str] = Field(default_factory=dict)
    navigation_state: Optional[NavigationState] = None
    reason: Optional[str] = None

class PageCapabilities(BaseModel):
    canObserveDom: bool = True
    canObserveAccessibility: bool = True
    canCaptureScreenshot: bool = True
    canObserveFrames: bool = True
    canObserveSemanticModel: bool = True
    canObserveVisualModel: bool = True

class BrowserCapabilities(BaseModel):
    tabObservation: bool = True
    pageObservation: bool = True
    semanticObservation: bool = True
    screenshotCapture: bool = True
    frameObservation: bool = True
    actionExecution: bool = False
    computerVision: bool = False
    agentPlanning: bool = False

class WorldHealth(BaseModel):
    status: str = "READY"
    browser_connected: bool = True
    active_tab_available: bool = True
    page_observation_available: bool = True
    semantic_model_available: bool = True
    visual_model_available: bool = True
    stale_artifacts: int = 0
    unresolved_references: int = 0
    last_reconciliation_time: Optional[str] = None

class BrowserWorldModel(BaseModel):
    world_model_id: str
    world_model_version: int = 1
    browser_session: BrowserSessionState
    active_window: Optional[WorldWindowState] = None
    windows: List[WorldWindowState] = Field(default_factory=list)
    tabs: List[WorldTabState] = Field(default_factory=list)
    active_tab_id: Optional[int] = None
    pages: List[WorldPageState] = Field(default_factory=list)
    frame_trees: Dict[int, FrameTree] = Field(default_factory=dict)
    observations: Dict[int, str] = Field(default_factory=dict)
    semantic_models: Dict[int, str] = Field(default_factory=dict)
    visual_models: Dict[int, str] = Field(default_factory=dict)
    navigation_states: Dict[int, NavigationState] = Field(default_factory=dict)
    temporal_transitions: List[WorldStateTransition] = Field(default_factory=list)
    capabilities: BrowserCapabilities = Field(default_factory=BrowserCapabilities)
    status: str = "READY"
    health: WorldHealth = Field(default_factory=WorldHealth)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)

class WorldQuery(BaseModel):
    type: str = "element"
    tab_id: Optional[int] = None
    page_id: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    visible_only: Optional[bool] = False
    interactive_only: Optional[bool] = False
    dialog_only: Optional[bool] = False

class WorldQueryResult(BaseModel):
    status: str
    query: WorldQuery
    elements: List[WorldElement] = Field(default_factory=list)
    pages: List[WorldPageState] = Field(default_factory=list)
    tabs: List[WorldTabState] = Field(default_factory=list)
    count: int = 0
    message: Optional[str] = None

# ============================================================================
# PHASE 8: SAFE BROWSER ACTION ENGINE DATA STRUCTURES
# ============================================================================

class ActionType(str, Enum):
    NAVIGATE = "NAVIGATE"
    CLICK = "CLICK"
    TYPE = "TYPE"
    CLEAR_INPUT = "CLEAR_INPUT"
    SELECT = "SELECT"
    CHECK = "CHECK"
    UNCHECK = "UNCHECK"
    FOCUS = "FOCUS"
    SCROLL = "SCROLL"
    KEY_PRESS = "KEY_PRESS"
    WAIT = "WAIT"

class ActionPolicyCategory(str, Enum):
    SAFE = "SAFE"
    SENSITIVE = "SENSITIVE"
    HIGH_IMPACT = "HIGH_IMPACT"
    BLOCKED = "BLOCKED"

class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"

class ActionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    STALE = "STALE"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    NO_OP = "NO_OP"
    WOULD_EXECUTE = "WOULD_EXECUTE"

class ActionTarget(BaseModel):
    world_element_ref: Optional[WorldElementRef] = None
    semantic_element_ref: Optional[SemanticElementRef] = None
    visual_element_ref: Optional[str] = None
    coordinates: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    tab_id: Optional[int] = None
    frame_id: Optional[str] = None
    expected_role: Optional[str] = None
    expected_name: Optional[str] = None
    expected_geometry: Optional[VisualBoundingBox] = None
    confidence: Optional[str] = "HIGH"
    allow_coordinate_fallback: Optional[bool] = False

class ActionPrecondition(BaseModel):
    type: str
    target_ref: Optional[str] = None
    expected_value: Optional[Any] = None

class ActionPostcondition(BaseModel):
    type: str
    target_ref: Optional[str] = None
    expected_value: Optional[Any] = None

class ActionIntent(BaseModel):
    action_id: str
    type: ActionType
    target: Optional[ActionTarget] = None
    parameters: Optional[Dict[str, Any]] = None
    world_model_version: int = 1
    page_version: int = 1
    tab_id: Optional[int] = None
    page_id: Optional[str] = None
    requested_by: Optional[str] = "agent_planner"
    confidence: Optional[str] = "HIGH"
    policy_context: Optional[Dict[str, Any]] = None
    preconditions: List[ActionPrecondition] = Field(default_factory=list)
    postconditions: List[ActionPostcondition] = Field(default_factory=list)
    timeout_ms: Optional[int] = 5000
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None

class ActionConfirmationRequest(BaseModel):
    confirmation_id: str
    action_id: str
    action_type: ActionType
    target_description: str
    impact_level: ActionPolicyCategory
    summary: str
    requested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "PENDING"

class ActionConfirmationResponse(BaseModel):
    confirmation_id: str
    action_id: str
    approved: bool
    user_note: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ActionTraceStep(BaseModel):
    stage: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "PASS"
    detail: Optional[str] = None

class ActionTrace(BaseModel):
    action_id: str
    steps: List[ActionTraceStep] = Field(default_factory=list)
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

class ActionErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False
    requires_replan: bool = False

class ActionResult(BaseModel):
    action_id: str
    type: ActionType
    status: ActionStatus
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: float = 0.0
    world_model_version_before: int = 1
    world_model_version_after: Optional[int] = None
    target: Optional[ActionTarget] = None
    trace: ActionTrace = Field(default_factory=lambda: ActionTrace(action_id="act_none"))
    expected_postconditions: List[ActionPostcondition] = Field(default_factory=list)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[ActionErrorDetail] = None

class ActionQueueItem(BaseModel):
    intent: ActionIntent
    status: str = "QUEUED"
    queued_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ActionQueueStatus(BaseModel):
    tab_id: int
    is_locked: bool = False
    active_action_id: Optional[str] = None
    queue_length: int = 0
    items: List[ActionQueueItem] = Field(default_factory=list)

# ============================================================================
# PHASE 9: ACTION VERIFICATION, RECOVERY & STATE RECONCILIATION DATA STRUCTURES
# ============================================================================

class VerificationStatus(str, Enum):
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    VERIFIED_FAILURE = "VERIFIED_FAILURE"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    NOT_EXECUTED = "NOT_EXECUTED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    TIMEOUT = "TIMEOUT"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"

class VerificationState(str, Enum):
    PENDING = "PENDING"
    OBSERVING = "OBSERVING"
    EVALUATING = "EVALUATING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"
    RECOVERING = "RECOVERING"
    ABORTED = "ABORTED"

class FailureClass(str, Enum):
    TARGET_FAILURE = "TARGET_FAILURE"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"
    NAVIGATION_FAILURE = "NAVIGATION_FAILURE"
    PAGE_FAILURE = "PAGE_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    POLICY_FAILURE = "POLICY_FAILURE"
    TIMEOUT_FAILURE = "TIMEOUT_FAILURE"
    STATE_MISMATCH = "STATE_MISMATCH"
    AMBIGUOUS_OUTCOME = "AMBIGUOUS_OUTCOME"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    CAPTCHA_PRESENT = "CAPTCHA_PRESENT"
    RATE_LIMITED = "RATE_LIMITED"
    SERVER_ERROR = "SERVER_ERROR"
    USER_CANCELLED = "USER_CANCELLED"
    BROWSER_DISCONNECTED = "BROWSER_DISCONNECTED"
    BRIDGE_FAILURE = "BRIDGE_FAILURE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"

class RecoveryType(str, Enum):
    NO_ACTION = "NO_ACTION"
    WAIT = "WAIT"
    REFRESH_WORLD = "REFRESH_WORLD"
    RETRY = "RETRY"
    RE_RESOLVE_TARGET = "RE_RESOLVE_TARGET"
    REPLAN = "REPLAN"
    ASK_USER = "ASK_USER"
    ABORT = "ABORT"

class IdempotencyClass(str, Enum):
    IDEMPOTENT = "IDEMPOTENT"
    CONDITIONALLY_IDEMPOTENT = "CONDITIONALLY_IDEMPOTENT"
    NON_IDEMPOTENT = "NON_IDEMPOTENT"
    UNKNOWN = "UNKNOWN"

class PostconditionEvaluationMode(str, Enum):
    ALL = "ALL"
    ANY = "ANY"
    AT_LEAST_N = "AT_LEAST_N"

class ConditionEvaluationResult(BaseModel):
    condition: ActionPostcondition
    status: str = "PASS"
    evidence_description: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class VerificationEvidence(BaseModel):
    evidence_id: str
    source: str
    type: str
    description: str
    confidence: str = "HIGH"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)

class VerificationWaitPolicy(BaseModel):
    initial_delay_ms: int = 100
    poll_interval_ms: int = 250
    max_timeout_ms: int = 5000
    mode: str = "NORMAL"

class RecoveryRecommendation(BaseModel):
    recommendation_id: str
    action_id: str
    failure_class: FailureClass
    recovery_type: RecoveryType
    suggested_action: Optional[ActionIntent] = None
    reason: str
    attempt_count: int = 1
    max_attempts: int = 3
    requires_user_intervention: bool = False
    intervention_type: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class RecoveryTraceStep(BaseModel):
    attempt: int
    failure_class: FailureClass
    recovery_type: RecoveryType
    result_status: VerificationStatus
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    note: Optional[str] = None

class RecoveryTrace(BaseModel):
    action_id: str
    steps: List[RecoveryTraceStep] = Field(default_factory=list)
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

class VerificationResult(BaseModel):
    verification_id: str
    action_id: str
    status: VerificationStatus
    confidence: str = "HIGH"
    before_snapshot_id: Optional[str] = None
    after_snapshot_id: Optional[str] = None
    before_world_version: int = 1
    after_world_version: int = 1
    evaluated_postconditions: List[ConditionEvaluationResult] = Field(default_factory=list)
    state_changes: Optional[WorldStateDiff] = None
    evidence: List[VerificationEvidence] = Field(default_factory=list)
    failure_class: Optional[FailureClass] = None
    recovery_recommendation: Optional[RecoveryRecommendation] = None
    is_stable: bool = True
    duration_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class UserInterventionRequest(BaseModel):
    intervention_id: str
    type: str
    what_happened: str
    why_stopped: str
    action_required: str
    tab_id: Optional[int] = None
    action_id: Optional[str] = None
    status: str = "PENDING"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None

class WorkflowCheckpoint(BaseModel):
    checkpoint_id: str
    name: str
    step_index: int = 0
    snapshot_id: str
    world_version: int = 1
    tab_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ============================================================================
# PHASE 10: AGENT PLANNING & EXECUTION LOOP DATA STRUCTURES
# ============================================================================

class AgentTaskState(str, Enum):
    CREATED = "CREATED"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    READY = "READY"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    REPLANNING = "REPLANNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    EXPIRED = "EXPIRED"

class TaskPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"

class PlanDecisionType(str, Enum):
    EXECUTE_ACTION = "EXECUTE_ACTION"
    WAIT = "WAIT"
    REPLAN = "REPLAN"
    ASK_USER = "ASK_USER"
    COMPLETE = "COMPLETE"
    ABORT = "ABORT"

class TabRole(str, Enum):
    PRIMARY = "PRIMARY"
    REFERENCE = "REFERENCE"
    AUTHENTICATION = "AUTHENTICATION"
    COMPARISON = "COMPARISON"
    TRANSACTION = "TRANSACTION"

class TaskTabContext(BaseModel):
    tab_id: int
    role: TabRole = TabRole.PRIMARY
    purpose: str = "main_interaction"
    current_url: str = ""
    relevance: str = "HIGH"

class TaskAssumption(BaseModel):
    assumption_id: str
    statement: str
    source: str = "INFERRED"
    is_valid: bool = True
    invalidated_reason: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class SuccessCriterion(BaseModel):
    criterion_id: str
    description: str
    evaluation_type: str = "VERIFICATION_PASSED"
    expected_value: Optional[str] = None
    is_satisfied: bool = False
    evidence: Optional[str] = None

class AgentGoal(BaseModel):
    goal_id: str
    user_request: str
    normalized_goal: Dict[str, Any] = Field(default_factory=dict)
    hard_constraints: List[str] = Field(default_factory=list)
    soft_preferences: List[str] = Field(default_factory=list)
    success_criteria: List[SuccessCriterion] = Field(default_factory=list)
    forbidden_actions: List[str] = Field(default_factory=list)
    confirmation_policy: str = "HIGH_IMPACT_ONLY"
    priority: TaskPriority = TaskPriority.NORMAL
    deadline: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PlanStep(BaseModel):
    step_id: str
    step_index: int = 0
    description: str
    objective: str
    preconditions: List[str] = Field(default_factory=list)
    intended_action: Optional[ActionIntent] = None
    expected_outcome: Optional[Dict[str, Any]] = None
    postconditions: List[ActionPostcondition] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    risk_level: str = "LOW"
    status: str = "PENDING"

class AgentPlan(BaseModel):
    plan_id: str
    goal_id: str
    version: int = 1
    steps: List[PlanStep] = Field(default_factory=list)
    assumptions: List[TaskAssumption] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    success_criteria: List[SuccessCriterion] = Field(default_factory=list)
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PlanDecision(BaseModel):
    decision: PlanDecisionType
    selected_step: Optional[PlanStep] = None
    intended_action: Optional[ActionIntent] = None
    reason: str
    question_for_user: Optional[str] = None
    clarification_options: List[str] = Field(default_factory=list)
    confidence: str = "HIGH"

class TaskProgress(BaseModel):
    total_objectives: int = 0
    completed_objectives: int = 0
    remaining_objectives: int = 0
    failed_objectives: int = 0
    current_milestone: str = "INITIAL"
    percent_complete: float = 0.0

class TaskMemory(BaseModel):
    completed_step_ids: List[str] = Field(default_factory=list)
    failed_step_ids: List[str] = Field(default_factory=list)
    executed_action_ids: List[str] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    user_decisions: Dict[str, str] = Field(default_factory=dict)
    checkpoints: List[str] = Field(default_factory=list)

class AgentResult(BaseModel):
    task_id: str
    goal_id: str
    status: AgentTaskState
    summary: str
    completed_objectives: List[str] = Field(default_factory=list)
    remaining_objectives: List[str] = Field(default_factory=list)
    actions_executed: int = 0
    recoveries_attempted: int = 0
    user_interventions_count: int = 0
    final_world_version: int = 1
    duration_ms: float = 0.0
    evidence: List[str] = Field(default_factory=list)

class AgentTask(BaseModel):
    task_id: str
    goal: AgentGoal
    state: AgentTaskState = AgentTaskState.CREATED
    current_plan: Optional[AgentPlan] = None
    plans: List[AgentPlan] = Field(default_factory=list)
    progress: TaskProgress = Field(default_factory=TaskProgress)
    memory: TaskMemory = Field(default_factory=TaskMemory)
    tab_contexts: Dict[int, TaskTabContext] = Field(default_factory=dict)
    active_tab_id: Optional[int] = None
    iteration_count: int = 0
    max_iterations: int = 30
    planner_calls_count: int = 0
    max_planner_calls: int = 20
    result: Optional[AgentResult] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class AgentEvent(BaseModel):
    event_id: str
    task_id: str
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ============================================================================
# PHASE 12: REAL-WORLD TRANSACTION & BOOKING ENGINE DATA STRUCTURES
# ============================================================================

class TransactionState(str, Enum):
    DISCOVERING = "DISCOVERING"
    COMPARING = "COMPARING"
    SELECTED = "SELECTED"
    PREPARING = "PREPARING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"

class TransactionType(str, Enum):
    FLIGHT_BOOKING = "FLIGHT_BOOKING"
    HOTEL_BOOKING = "HOTEL_BOOKING"
    TRAIN_BOOKING = "TRAIN_BOOKING"
    BUS_BOOKING = "BUS_BOOKING"
    EVENT_TICKET = "EVENT_TICKET"
    MOVIE_TICKET = "MOVIE_TICKET"
    RESTAURANT_RESERVATION = "RESTAURANT_RESERVATION"
    APPOINTMENT = "APPOINTMENT"
    PRODUCT_PURCHASE = "PRODUCT_PURCHASE"
    SERVICE_BOOKING = "SERVICE_BOOKING"
    SUBSCRIPTION = "SUBSCRIPTION"
    OTHER = "OTHER"

class AvailabilityState(str, Enum):
    AVAILABLE = "AVAILABLE"
    LIMITED = "LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"
    CHANGED = "CHANGED"

class CommitPolicy(str, Enum):
    ALWAYS_CONFIRM = "ALWAYS_CONFIRM"
    CONFIRM_IF_PRICE_ABOVE_THRESHOLD = "CONFIRM_IF_PRICE_ABOVE_THRESHOLD"
    CONFIRM_IF_IRREVERSIBLE = "CONFIRM_IF_IRREVERSIBLE"
    USER_PREAUTHORIZED = "USER_PREAUTHORIZED"
    NEVER_AUTO_COMMIT = "NEVER_AUTO_COMMIT"

class TransactionRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class TransactionPrice(BaseModel):
    base: float = 0.0
    tax: float = 0.0
    fees: float = 0.0
    discount: float = 0.0
    total: float = 0.0
    currency: str = "INR"
    confidence: str = "HIGH"

class TransactionConstraint(BaseModel):
    constraint_id: str
    name: str
    type: str = "HARD"
    value: str
    is_satisfied: bool = True

class TransactionPreference(BaseModel):
    preference_id: str
    dimension: str = "PRICE"
    target_value: str
    weight: float = 1.0

class TransactionOption(BaseModel):
    option_id: str
    provider: str
    title: str
    price: TransactionPrice = Field(default_factory=TransactionPrice)
    availability: AvailabilityState = AvailabilityState.AVAILABLE
    attributes: Dict[str, Any] = Field(default_factory=dict)
    constraints_satisfied: bool = True
    preference_score: float = 1.0
    confidence: str = "HIGH"
    source_reference: Optional[str] = None

class TransactionSnapshot(BaseModel):
    snapshot_id: str
    transaction_id: str
    version: int = 1
    selected_option: TransactionOption
    price: TransactionPrice
    availability: AvailabilityState = AvailabilityState.AVAILABLE
    provider: str
    important_conditions: List[str] = Field(default_factory=list)
    cancellation_policy: str = "Non-refundable"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class TransactionReview(BaseModel):
    review_id: str
    transaction_id: str
    item_title: str
    provider: str
    route_or_location: Optional[str] = None
    date_time: Optional[str] = None
    price: TransactionPrice
    important_restrictions: List[str] = Field(default_factory=list)
    cancellation_refund_conditions: List[str] = Field(default_factory=list)
    is_irreversible: bool = True
    risk_level: TransactionRisk = TransactionRisk.HIGH
    commit_action_description: str

class TransactionConfirmation(BaseModel):
    confirmation_id: str
    transaction_id: str
    option_id: str
    snapshot_version: int = 1
    status: str = "PENDING"
    confirmed_at: Optional[str] = None
    expires_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_note: Optional[str] = None

class CommitAuthorization(BaseModel):
    auth_token: str
    transaction_id: str
    confirmation_id: str
    policy_version: int = 1
    snapshot_version: int = 1
    expires_at: str

class TransactionReceipt(BaseModel):
    receipt_id: str
    transaction_id: str
    provider: str
    reference_number: str
    amount: float
    currency: str = "INR"
    booking_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "COMPLETED"
    evidence_summary: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Transaction(BaseModel):
    transaction_id: str
    workflow_id: Optional[str] = None
    type: TransactionType = TransactionType.OTHER
    merchant: str = "Unknown"
    provider: str = "Unknown"
    product_or_service: str
    status: TransactionState = TransactionState.DISCOVERING
    currency: str = "INR"
    amount: float = 0.0
    taxes: float = 0.0
    fees: float = 0.0
    total: float = 0.0
    selected_option: Optional[TransactionOption] = None
    options: List[TransactionOption] = Field(default_factory=list)
    constraints: List[TransactionConstraint] = Field(default_factory=list)
    user_preferences: List[TransactionPreference] = Field(default_factory=list)
    confirmation_policy: CommitPolicy = CommitPolicy.ALWAYS_CONFIRM
    commit_boundary: str = "Pay / Submit"
    risk_level: TransactionRisk = TransactionRisk.HIGH
    active_snapshot: Optional[TransactionSnapshot] = None
    active_review: Optional[TransactionReview] = None
    active_confirmation: Optional[TransactionConfirmation] = None
    receipt: Optional[TransactionReceipt] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class TransactionAuditEvent(BaseModel):
    event_id: str
    transaction_id: str
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ============================================================================
# PHASE 13: SECURITY, PERMISSIONS & HUMAN-IN-THE-LOOP DATA STRUCTURES
# ============================================================================

class SecurityDecision(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_WITH_CONFIRMATION = "ALLOW_WITH_CONFIRMATION"
    DENY = "DENY"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    REQUIRE_USER = "REQUIRE_USER"
    REQUIRE_AUTHENTICATION = "REQUIRE_AUTHENTICATION"

class SecurityActor(str, Enum):
    USER = "USER"
    MATRIOSHAI_AGENT = "MATRIOSHAI_AGENT"
    SYSTEM = "SYSTEM"
    EXTENSION = "EXTENSION"
    WORKFLOW_ENGINE = "WORKFLOW_ENGINE"
    TRANSACTION_ENGINE = "TRANSACTION_ENGINE"

class PermissionCategory(str, Enum):
    OBSERVE_PAGE = "OBSERVE_PAGE"
    READ_PAGE_DATA = "READ_PAGE_DATA"
    NAVIGATE = "NAVIGATE"
    CLICK = "CLICK"
    TYPE = "TYPE"
    SCROLL = "SCROLL"
    OPEN_TAB = "OPEN_TAB"
    CLOSE_TAB = "CLOSE_TAB"
    UPLOAD_FILE = "UPLOAD_FILE"
    DOWNLOAD_FILE = "DOWNLOAD_FILE"
    USE_CLIPBOARD = "USE_CLIPBOARD"
    ACCESS_LOCATION = "ACCESS_LOCATION"
    ACCESS_CONTACTS = "ACCESS_CONTACTS"
    SEND_MESSAGE = "SEND_MESSAGE"
    MODIFY_ACCOUNT = "MODIFY_ACCOUNT"
    PURCHASE = "PURCHASE"
    BOOK = "BOOK"
    PAY = "PAY"
    DELETE = "DELETE"
    SUBMIT = "SUBMIT"
    USE_EXTERNAL_SERVICE = "USE_EXTERNAL_SERVICE"

class PermissionScope(str, Enum):
    GLOBAL = "GLOBAL"
    DOMAIN = "DOMAIN"
    SITE = "SITE"
    TAB = "TAB"
    WORKFLOW = "WORKFLOW"
    TASK = "TASK"
    ACTION = "ACTION"
    TRANSACTION = "TRANSACTION"

class DomainTrustLevel(str, Enum):
    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    TRUSTED = "TRUSTED"
    RESTRICTED = "RESTRICTED"
    BLOCKED = "BLOCKED"

class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    PRIVATE = "PRIVATE"
    SENSITIVE = "SENSITIVE"
    HIGHLY_SENSITIVE = "HIGHLY_SENSITIVE"
    SECRET = "SECRET"

class AutonomyLevel(str, Enum):
    MANUAL = "MANUAL"
    ASSISTED = "ASSISTED"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS_WITH_CONFIRMATION = "AUTONOMOUS_WITH_CONFIRMATION"
    LIMITED_AUTONOMOUS = "LIMITED_AUTONOMOUS"

class TakeoverState(str, Enum):
    AGENT_CONTROL = "AGENT_CONTROL"
    USER_CONTROL = "USER_CONTROL"
    SHARED_CONTROL = "SHARED_CONTROL"
    PAUSED = "PAUSED"

class DomainPermission(BaseModel):
    domain: str
    permissions: List[PermissionCategory] = Field(default_factory=list)
    scope: PermissionScope = PermissionScope.DOMAIN
    trust_level: DomainTrustLevel = DomainTrustLevel.TRUSTED
    expires_at: Optional[str] = None
    created_by: SecurityActor = SecurityActor.USER
    status: str = "ACTIVE"

class SecurityRequest(BaseModel):
    request_id: str
    actor: SecurityActor = SecurityActor.MATRIOSHAI_AGENT
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    action_type: str
    target_domain: Optional[str] = None
    target_url: Optional[str] = None
    resource: Optional[str] = None
    data_classification: DataClassification = DataClassification.PUBLIC
    risk_level: str = "LOW"
    transaction_id: Optional[str] = None
    reason: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ActionAuthorization(BaseModel):
    authorization_id: str
    actor: SecurityActor
    workflow_id: Optional[str] = None
    action_id: str
    permission: PermissionCategory
    target_domain: Optional[str] = None
    state_version: int = 1
    policy_version: int = 1
    expires_at: str
    nonce: str

class UserApprovalToken(BaseModel):
    token_id: str
    confirmation_id: str
    action_id: str
    transaction_id: Optional[str] = None
    state_version: int = 1
    expires_at: str

class SpendingLimitPolicy(BaseModel):
    currency: str = "INR"
    maximum_amount: float = 10000.0
    time_window: str = "PER_TRANSACTION"
    confirmation_required: bool = True

class SecurityAuditEvent(BaseModel):
    event_id: str
    actor: str
    action: str
    target: Optional[str] = None
    policy_decision: str
    risk: str
    workflow_id: Optional[str] = None
    transaction_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: str = "SUCCESS"

# ============================================================================
# PHASE 14: PRODUCTION HARDENING, RELIABILITY & OBSERVABILITY DATA STRUCTURES
# ============================================================================

class RuntimeState(str, Enum):
    STARTING = "STARTING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    SECURITY_LOCKED = "SECURITY_LOCKED"

class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

class RestartPolicy(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    BACKOFF = "BACKOFF"
    MANUAL = "MANUAL"
    NEVER = "NEVER"

class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class DecisionConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

class ComponentHealth(BaseModel):
    component_name: str
    status: HealthState = HealthState.HEALTHY
    version: str = "1.0.0"
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    consecutive_failures: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)

class RuntimeMetrics(BaseModel):
    uptime_seconds: float = 0.0
    actions_total: int = 0
    actions_successful: int = 0
    actions_failed: int = 0
    transactions_total: int = 0
    transactions_completed: int = 0
    model_requests_total: int = 0
    model_latency_avg_ms: float = 0.0
    circuit_breakers_open: int = 0

class DeadLetterItem(BaseModel):
    item_id: str
    source: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    error_message: str
    attempts: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class RuntimeEvent(BaseModel):
    event_id: str
    event_type: str
    version: int = 1
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "runtime"
    correlation_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)

# ============================================================================
# STATE STORE IMPLEMENTATION
# ============================================================================

class BrowserStateStore:
    def __init__(self):
        self._lock = threading.RLock()
        self.browser_id: str = "browser_uninitialized"
        self.browser_type: str = "chrome"
        self.browser_version: Optional[str] = None
        self.connected_at: Optional[str] = None
        self.last_seen: Optional[str] = None
        self.windows: Dict[int, WindowState] = {}
        self.tabs: Dict[int, TabState] = {}
        self.active_tab_id: Optional[int] = None

        # Phase 4, 5, 6 Caches
        self.latest_observations: Dict[int, PageObservation] = {}
        self.latest_semantic_models: Dict[int, SemanticPageModel] = {}
        self.latest_visual_models: Dict[int, VisualPageModel] = {}
        self.latest_screenshots: Dict[int, str] = {}

        # Phase 7 World Model State & Temporal Graph
        self.world_model_version: int = 1
        self.current_world: Optional[BrowserWorldModel] = None
        self.page_states: Dict[int, WorldPageState] = {}
        self.frame_trees: Dict[int, FrameTree] = {}
        self.navigation_histories: Dict[int, List[NavigationHistoryItem]] = {}
        self.navigation_states: Dict[int, NavigationState] = {}
        self.world_elements: Dict[int, List[WorldElement]] = {}
        self.world_snapshots: List[BrowserWorldSnapshot] = []
        self.world_transitions: List[WorldStateTransition] = []
        self.MAX_SNAPSHOTS = 20
        self.MAX_TRANSITIONS = 50

        # Phase 8 Action Engine State & Audit
        self.action_history: List[ActionResult] = []
        self.action_traces: Dict[str, ActionTrace] = {}
        self.pending_confirmations: Dict[str, ActionConfirmationRequest] = {}
        self.tab_action_queues: Dict[int, List[ActionIntent]] = {}
        self.tab_execution_locks: Dict[int, bool] = {}
        self.MAX_ACTION_HISTORY = 100

        # Phase 9 Verification & Recovery State
        self.verifications: Dict[str, VerificationResult] = {}
        self.user_interventions: Dict[str, UserInterventionRequest] = {}
        self.checkpoints: Dict[str, WorkflowCheckpoint] = {}
        self.recovery_traces: Dict[str, RecoveryTrace] = {}
        self.MAX_VERIFICATIONS = 100

        # Phase 10 Agent Planning & Execution State
        self.agent_tasks: Dict[str, AgentTask] = {}
        self.agent_events: List[AgentEvent] = []
        self.MAX_AGENT_EVENTS = 200

        # Phase 12 Real-World Transaction & Booking Engine State
        self.transactions: Dict[str, Transaction] = {}
        self.transaction_snapshots: Dict[str, TransactionSnapshot] = {}
        self.transaction_confirmations: Dict[str, TransactionConfirmation] = {}
        self.transaction_receipts: Dict[str, TransactionReceipt] = {}
        self.transaction_audit_events: List[TransactionAuditEvent] = []
        self.MAX_TRANSACTION_AUDIT_EVENTS = 200

        # Phase 13 Security, Permissions & Human-in-the-Loop State
        self.domain_permissions: Dict[str, DomainPermission] = {}
        self.action_authorizations: Dict[str, ActionAuthorization] = {}
        self.user_approval_tokens: Dict[str, UserApprovalToken] = {}
        self.security_audit_events: List[SecurityAuditEvent] = []
        self.takeover_state: TakeoverState = TakeoverState.AGENT_CONTROL
        self.emergency_stop_active: bool = False
        self.autonomy_level: AutonomyLevel = AutonomyLevel.SUPERVISED
        self.spending_limits: List[SpendingLimitPolicy] = [
            SpendingLimitPolicy(currency="INR", maximum_amount=15000.0, time_window="PER_TRANSACTION", confirmation_required=True)
        ]
        self.blocked_domains: Set[str] = set()
        self.MAX_SECURITY_AUDIT_EVENTS: int = 500

        # Phase 14 Production Hardening, Observability & Runtime State
        self.runtime_state: RuntimeState = RuntimeState.READY
        self.runtime_start_time: float = time.time()
        self.component_health: Dict[str, ComponentHealth] = {}
        self.dead_letter_queue: List[DeadLetterItem] = []
        self.runtime_events: List[RuntimeEvent] = []
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        self.metrics: RuntimeMetrics = RuntimeMetrics()
        self.MAX_DEAD_LETTER_ITEMS: int = 200
        self.MAX_RUNTIME_EVENTS: int = 500

        # Artifact Lifecycle Registry
        self.artifact_registry: Dict[str, Dict[str, Any]] = {}
        self.audit_logs: List[BrowserAuditLog] = []

    def set_browser_identity(self, browser_id: str, browser_version: Optional[str] = None):
        with self._lock:
            self.browser_id = browser_id
            self.browser_version = browser_version
            self.last_seen = datetime.now(timezone.utc).isoformat()
            if not self.connected_at:
                self.connected_at = self.last_seen

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            active_tab = self.tabs.get(self.active_tab_id) if self.active_tab_id else None
            return {
                "browser_id": self.browser_id,
                "browser_type": self.browser_type,
                "browser_version": self.browser_version,
                "windows_count": len(self.windows),
                "tabs_count": len(self.tabs),
                "active_tab_id": self.active_tab_id,
                "active_tab_url": active_tab.url if active_tab else None,
                "world_model_version": self.world_model_version,
                "cached_snapshots_count": len(self.world_snapshots),
                "cached_observations_count": len(self.latest_observations),
                "cached_semantic_models_count": len(self.latest_semantic_models),
                "cached_visual_models_count": len(self.latest_visual_models),
                "last_seen": self.last_seen
            }

    def get_windows(self) -> List[WindowState]:
        with self._lock:
            return list(self.windows.values())

    def get_tabs(self) -> List[TabState]:
        with self._lock:
            return list(self.tabs.values())

    def get_tab(self, tab_id: int) -> Optional[TabState]:
        with self._lock:
            return self.tabs.get(tab_id)

    def get_active_tab(self) -> Optional[TabState]:
        with self._lock:
            if self.active_tab_id and self.active_tab_id in self.tabs:
                return self.tabs[self.active_tab_id]
            for tab in self.tabs.values():
                if tab.active:
                    return tab
            return None

    # ------------------------------------------------------------------------
    # PAGE OBSERVATION CACHE (PHASE 4)
    # ------------------------------------------------------------------------

    def store_observation(self, observation: PageObservation):
        with self._lock:
            self.latest_observations[observation.tab_id] = observation
            self.register_artifact(observation.observation_id, "observation", observation.tab_id)
            if observation.tab_id in self.tabs:
                self.tabs[observation.tab_id].url = observation.url
                self.tabs[observation.tab_id].title = observation.title
                self.tabs[observation.tab_id].status = TabStatus.READY
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def get_observation(self, tab_id: int) -> Optional[PageObservation]:
        with self._lock:
            return self.latest_observations.get(tab_id)

    # ------------------------------------------------------------------------
    # SEMANTIC PAGE MODEL CACHE (PHASE 5)
    # ------------------------------------------------------------------------

    def store_semantic_model(self, model: SemanticPageModel):
        with self._lock:
            self.latest_semantic_models[model.tab_id] = model
            self.register_artifact(model.semantic_model_id, "semantic_model", model.tab_id)
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def get_semantic_model(self, tab_id: int) -> Optional[SemanticPageModel]:
        with self._lock:
            return self.latest_semantic_models.get(tab_id)

    def invalidate_semantic_model(self, tab_id: int):
        with self._lock:
            if tab_id in self.latest_semantic_models:
                self.latest_semantic_models[tab_id].is_stale = True
                self.latest_semantic_models[tab_id].model_version += 1
                self.mark_artifact_stale(self.latest_semantic_models[tab_id].semantic_model_id)

    # ------------------------------------------------------------------------
    # VISUAL PAGE MODEL & SCREENSHOT CACHE (PHASE 6)
    # ------------------------------------------------------------------------

    def store_visual_model(self, model: VisualPageModel, screenshot_data_url: Optional[str] = None):
        with self._lock:
            self.latest_visual_models[model.tab_id] = model
            self.register_artifact(model.visual_model_id, "visual_model", model.tab_id)
            if screenshot_data_url:
                self.latest_screenshots[model.tab_id] = screenshot_data_url
                self.register_artifact(model.screenshot.id, "screenshot", model.tab_id)
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def get_visual_model(self, tab_id: int) -> Optional[VisualPageModel]:
        with self._lock:
            return self.latest_visual_models.get(tab_id)

    def get_screenshot(self, tab_id: int) -> Optional[str]:
        with self._lock:
            return self.latest_screenshots.get(tab_id)

    def invalidate_visual_model(self, tab_id: int):
        with self._lock:
            if tab_id in self.latest_visual_models:
                self.latest_visual_models[tab_id].is_stale = True
                self.latest_visual_models[tab_id].visual_version += 1
                self.mark_artifact_stale(self.latest_visual_models[tab_id].visual_model_id)
            self.latest_screenshots.pop(tab_id, None)

    # ------------------------------------------------------------------------
    # PHASE 7 ARTIFACT LIFECYCLE MANAGEMENT
    # ------------------------------------------------------------------------

    def register_artifact(self, artifact_id: str, artifact_type: str, tab_id: int):
        self.artifact_registry[artifact_id] = {
            "artifact_id": artifact_id,
            "type": artifact_type,
            "tab_id": tab_id,
            "status": "ACTIVE",
            "registered_at": datetime.now(timezone.utc).isoformat()
        }

    def mark_artifact_stale(self, artifact_id: Optional[str]):
        if artifact_id and artifact_id in self.artifact_registry:
            self.artifact_registry[artifact_id]["status"] = "STALE"

    def get_stale_artifacts_count(self) -> int:
        return sum(1 for a in self.artifact_registry.values() if a.get("status") == "STALE")

    # ------------------------------------------------------------------------
    # PHASE 7 WORLD SNAPSHOTS & TRANSITIONS
    # ------------------------------------------------------------------------

    def append_world_snapshot(self, snapshot: BrowserWorldSnapshot):
        with self._lock:
            self.world_snapshots.append(snapshot)
            if len(self.world_snapshots) > self.MAX_SNAPSHOTS:
                self.world_snapshots.pop(0)

    def get_world_snapshots(self) -> List[BrowserWorldSnapshot]:
        with self._lock:
            return list(self.world_snapshots)

    def get_world_snapshot(self, snapshot_id: str) -> Optional[BrowserWorldSnapshot]:
        with self._lock:
            for s in self.world_snapshots:
                if s.snapshot_id == snapshot_id:
                    return s
            return None

    def record_world_transition(self, transition: WorldStateTransition):
        with self._lock:
            self.world_transitions.append(transition)
            if len(self.world_transitions) > self.MAX_TRANSITIONS:
                self.world_transitions.pop(0)

    def get_world_transitions(self) -> List[WorldStateTransition]:
        with self._lock:
            return list(self.world_transitions)

    # ------------------------------------------------------------------------
    # EVENT-DRIVEN STATE UPDATES
    # ------------------------------------------------------------------------

    def apply_tab_created(self, tab_data: Dict[str, Any]):
        with self._lock:
            try:
                tab = TabState(**tab_data)
                self.tabs[tab.tab_id] = tab
                if tab.window_id in self.windows:
                    if tab.tab_id not in self.windows[tab.window_id].tab_ids:
                        self.windows[tab.window_id].tab_ids.append(tab.tab_id)
                if tab.active:
                    self.active_tab_id = tab.tab_id

                self.world_model_version += 1
                self.record_world_transition(
                    WorldStateTransition(
                        transition_id=f"trans_{int(time.time()*1000)}",
                        source_version=self.world_model_version - 1,
                        target_version=self.world_model_version,
                        type="TAB_CREATED",
                        tab_id=tab.tab_id,
                        changed_entities={"tabs_changed": [tab.tab_id]},
                        summary=f"Tab {tab.tab_id} created at URL '{tab.url}'"
                    )
                )
                self.last_seen = datetime.now(timezone.utc).isoformat()
            except Exception as e:
                logger.warning(f"[MATRIOSHAI][StateStore] Failed to apply tab_created: {e}")

    def apply_tab_updated(self, tab_data: Dict[str, Any]):
        with self._lock:
            try:
                tab = TabState(**tab_data)
                old_tab = self.tabs.get(tab.tab_id)
                self.tabs[tab.tab_id] = tab
                if tab.active:
                    self.active_tab_id = tab.tab_id

                # Invalidate semantic and visual models on navigation
                if tab.tab_id in self.latest_semantic_models:
                    self.latest_semantic_models[tab.tab_id].is_stale = True
                if tab.tab_id in self.latest_visual_models:
                    self.latest_visual_models[tab.tab_id].is_stale = True
                    self.latest_screenshots.pop(tab.tab_id, None)

                # Track navigation history item
                if old_tab and old_tab.url != tab.url and tab.url:
                    if tab.tab_id not in self.navigation_histories:
                        self.navigation_histories[tab.tab_id] = []
                    self.navigation_histories[tab.tab_id].append(
                        NavigationHistoryItem(
                            navigation_id=f"nav_{int(time.time()*1000)}",
                            tab_id=tab.tab_id,
                            url=tab.url,
                            title=tab.title
                        )
                    )
                    if len(self.navigation_histories[tab.tab_id]) > 50:
                        self.navigation_histories[tab.tab_id].pop(0)

                self.world_model_version += 1
                self.last_seen = datetime.now(timezone.utc).isoformat()
            except Exception as e:
                logger.warning(f"[MATRIOSHAI][StateStore] Failed to apply tab_updated: {e}")

    def apply_tab_activated(self, tab_id: int, window_id: int):
        with self._lock:
            self.active_tab_id = tab_id
            for t in self.tabs.values():
                t.active = (t.tab_id == tab_id)
            if window_id in self.windows:
                self.windows[window_id].active_tab_id = tab_id

            self.world_model_version += 1
            self.record_world_transition(
                WorldStateTransition(
                    transition_id=f"trans_{int(time.time()*1000)}",
                    source_version=self.world_model_version - 1,
                    target_version=self.world_model_version,
                    type="TAB_CHANGE",
                    tab_id=tab_id,
                    changed_entities={"tabs_changed": [tab_id]},
                    summary=f"Tab {tab_id} activated in window {window_id}"
                )
            )
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def apply_tab_removed(self, tab_id: int, window_id: int):
        with self._lock:
            self.tabs.pop(tab_id, None)
            self.latest_observations.pop(tab_id, None)
            self.latest_semantic_models.pop(tab_id, None)
            self.latest_visual_models.pop(tab_id, None)
            self.latest_screenshots.pop(tab_id, None)
            self.page_states.pop(tab_id, None)
            self.frame_trees.pop(tab_id, None)
            self.world_elements.pop(tab_id, None)

            if window_id in self.windows and tab_id in self.windows[window_id].tab_ids:
                self.windows[window_id].tab_ids.remove(tab_id)
            if self.active_tab_id == tab_id:
                self.active_tab_id = None

            self.world_model_version += 1
            self.record_world_transition(
                WorldStateTransition(
                    transition_id=f"trans_{int(time.time()*1000)}",
                    source_version=self.world_model_version - 1,
                    target_version=self.world_model_version,
                    type="TAB_CLOSED",
                    tab_id=tab_id,
                    changed_entities={"tabs_changed": [tab_id]},
                    summary=f"Tab {tab_id} closed"
                )
            )
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def apply_window_focused(self, window_id: int):
        with self._lock:
            for w in self.windows.values():
                w.focused = (w.window_id == window_id)
            self.last_seen = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------------
    # DETERMINISTIC STATE RECONCILIATION
    # ------------------------------------------------------------------------

    def reconcile_state(self, windows_data: List[Dict[str, Any]], tabs_data: List[Dict[str, Any]], active_tab_data: Optional[Dict[str, Any]] = None):
        with self._lock:
            new_windows: Dict[int, WindowState] = {}
            for wd in windows_data:
                try:
                    w = WindowState(**wd)
                    new_windows[w.window_id] = w
                except Exception:
                    pass

            new_tabs: Dict[int, TabState] = {}
            active_id = None
            for td in tabs_data:
                try:
                    t = TabState(**td)
                    new_tabs[t.tab_id] = t
                    if t.active:
                        active_id = t.tab_id
                except Exception:
                    pass

            if active_tab_data:
                try:
                    at = TabState(**active_tab_data)
                    new_tabs[at.tab_id] = at
                    active_id = at.tab_id
                except Exception:
                    pass

            self.windows = new_windows
            self.tabs = new_tabs
            self.active_tab_id = active_id
            self.latest_observations = {
                tid: obs for tid, obs in self.latest_observations.items() if tid in self.tabs
            }
            self.latest_semantic_models = {
                tid: sm for tid, sm in self.latest_semantic_models.items() if tid in self.tabs
            }
            self.latest_visual_models = {
                tid: vm for tid, vm in self.latest_visual_models.items() if tid in self.tabs
            }
            self.latest_screenshots = {
                tid: sc for tid, sc in self.latest_screenshots.items() if tid in self.tabs
            }
            self.page_states = {
                tid: ps for tid, ps in self.page_states.items() if tid in self.tabs
            }
            self.world_elements = {
                tid: we for tid, we in self.world_elements.items() if tid in self.tabs
            }
            self.world_model_version += 1
            self.last_seen = datetime.now(timezone.utc).isoformat()
            logger.info(f"[MATRIOSHAI][StateStore] State reconciled: {len(self.windows)} windows, {len(self.tabs)} tabs")

    # ------------------------------------------------------------------------
    # AUDIT LOGGING
    # ------------------------------------------------------------------------

    def record_audit_log(self, action_id: str, action_type: str, tab_id: Optional[int], requested_url: Optional[str], result: str, error: Optional[str] = None):
        with self._lock:
            entry = BrowserAuditLog(
                action_id=action_id,
                type=action_type,
                browser_id=self.browser_id,
                tab_id=tab_id,
                requested_url=requested_url,
                result=result,
                error=error
            )
            self.audit_logs.append(entry)
            if len(self.audit_logs) > 500:
                self.audit_logs.pop(0)

    def get_audit_logs(self, limit: int = 50) -> List[BrowserAuditLog]:
        with self._lock:
            return list(self.audit_logs[-limit:])

    def reset(self):
        with self._lock:
            self.windows.clear()
            self.tabs.clear()
            self.active_tab_id = None
            self.latest_observations.clear()
            self.latest_semantic_models.clear()
            self.latest_visual_models.clear()
            self.latest_screenshots.clear()
            self.page_states.clear()
            self.frame_trees.clear()
            self.navigation_histories.clear()
            self.world_elements.clear()
            self.world_snapshots.clear()
            self.world_transitions.clear()
            self.world_model_version = 1
            self.current_world = None

browser_state_store = BrowserStateStore()
