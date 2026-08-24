/**
 * MATRIOSHAI Browser Agent Extension — Core Types (Phases 1-5)
 *
 * Defines shared lifecycle contracts, message protocols, diagnostic models,
 * browser control models, Phase 4 Page Observation, and Phase 5 Semantic Page Models.
 */

export type ExtensionEnvironment = 'development' | 'production';

export type ServiceWorkerStatus = 'uninitialized' | 'initializing' | 'ready' | 'error';
export type ContentScriptStatus = 'uninitialized' | 'injected' | 'ready' | 'standby' | 'error';

/**
 * Phase 2 Explicit Connection State Machine
 */
export type BridgeConnectionState =
  | 'DISCONNECTED'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'AUTHENTICATING'
  | 'READY'
  | 'DEGRADED'
  | 'RECONNECTING'
  | 'CLOSING'
  | 'ERROR';

export type BridgeMessageType = 'request' | 'response' | 'event' | 'error' | 'heartbeat';

/**
 * Standard Protocol Actions & Events (Phases 2-5)
 */
export enum BridgeAction {
  // Phase 2 Bridge Health & Diagnostics
  AUTH = 'bridge.auth',
  HEALTH = 'bridge.health',
  INFO = 'bridge.info',
  PING = 'bridge.ping',
  STATUS = 'bridge.status',
  CONNECTED = 'bridge.connected',
  READY = 'bridge.ready',
  DISCONNECTED = 'bridge.disconnected',
  RECONNECTING = 'bridge.reconnecting',
  ERROR = 'bridge.error',
  HEARTBEAT = 'bridge.heartbeat',
  EXTENSION_UPDATED = 'bridge.extension_updated',

  // Phase 3 Browser Discovery & Control
  BROWSER_GET_STATUS = 'browser.getStatus',
  BROWSER_GET_WINDOWS = 'browser.getWindows',
  BROWSER_GET_TABS = 'browser.getTabs',
  BROWSER_GET_ACTIVE_TAB = 'browser.getActiveTab',
  BROWSER_OPEN_TAB = 'browser.openTab',
  BROWSER_CLOSE_TAB = 'browser.closeTab',
  BROWSER_SWITCH_TAB = 'browser.switchTab',
  BROWSER_NAVIGATE = 'browser.navigate',
  BROWSER_RELOAD = 'browser.reload',
  BROWSER_GO_BACK = 'browser.goBack',
  BROWSER_GO_FORWARD = 'browser.goForward',
  BROWSER_WAIT_FOR_NAVIGATION = 'browser.waitForNavigation',
  BROWSER_REFRESH_STATE = 'browser.refreshState',

  // Phase 4 Page Observation Engine
  PAGE_OBSERVE = 'page.observe',

  // Phase 5 Semantic Page & Accessibility Intelligence
  PAGE_SEMANTIC_OBSERVE = 'page.semanticObserve',
  PAGE_SEMANTIC_QUERY = 'page.semanticQuery',
  PAGE_RESOLVE_ELEMENT = 'page.resolveElement',
  PAGE_GET_SEMANTIC_MODEL = 'page.getSemanticModel',
  PAGE_INVALIDATE_SEMANTIC_MODEL = 'page.invalidateSemanticModel',

  // Phase 6 Visual Page Intelligence
  PAGE_CAPTURE_SCREENSHOT = 'page.captureScreenshot',
  PAGE_VISUAL_OBSERVE = 'page.visualObserve',
  PAGE_GET_VISUAL_MODEL = 'page.getVisualModel',
  PAGE_GET_VISUAL_ELEMENT = 'page.getVisualElement',
  PAGE_VISUAL_POINT_QUERY = 'page.visualPointQuery',
  PAGE_VISUAL_QUERY = 'page.visualQuery',
  PAGE_INVALIDATE_VISUAL_MODEL = 'page.invalidateVisualModel',

  // Phase 7 Unified Browser World Model
  WORLD_GET_CURRENT = 'world.getCurrent',
  WORLD_GET_SNAPSHOT = 'world.getSnapshot',
  WORLD_GET_DIFF = 'world.getDiff',
  WORLD_QUERY = 'world.query',
  WORLD_RESOLVE_ELEMENT = 'world.resolveElement',
  WORLD_VALIDATE = 'world.validate',
  WORLD_RECONCILE = 'world.reconcile',
  WORLD_INVALIDATE = 'world.invalidate',
  WORLD_HEALTH = 'world.health',
  WORLD_GET_HISTORY = 'world.getHistory',

  // Phase 8 Safe Browser Action Engine
  ACTION_EXECUTE = 'action.execute',
  ACTION_CANCEL = 'action.cancel',
  ACTION_CONFIRM = 'action.confirm',
  ACTION_QUEUE_STATUS = 'action.queueStatus',
  ACTION_VALIDATE = 'action.validate',

  // Phase 9 Action Verification & Recovery Engine
  VERIFICATION_VERIFY = 'verification.verify',
  VERIFICATION_GET_RESULT = 'verification.getResult',
  RECOVERY_RECOMMEND = 'recovery.recommend',
  CHECKPOINT_CREATE = 'checkpoint.create',
  CHECKPOINT_LIST = 'checkpoint.list',
  INTERVENTION_RESOLVE = 'intervention.resolve',

  // Phase 10 Agent Planning & Execution Loop
  AGENT_CREATE_GOAL = 'agent.createGoal',
  AGENT_START_TASK = 'agent.startTask',
  AGENT_PAUSE_TASK = 'agent.pauseTask',
  AGENT_RESUME_TASK = 'agent.resumeTask',
  AGENT_ABORT_TASK = 'agent.abortTask',
  AGENT_GET_TASK = 'agent.getTask',
  AGENT_GET_EVENTS = 'agent.getEvents',
  AGENT_SUBMIT_CLARIFICATION = 'agent.submitClarification',

  // Phase 12 Real-World Transaction & Booking Engine
  TRANSACTION_CREATE = 'transaction.create',
  TRANSACTION_SELECT_OPTION = 'transaction.selectOption',
  TRANSACTION_PREPARE_REVIEW = 'transaction.prepareReview',
  TRANSACTION_CONFIRM = 'transaction.confirm',
  TRANSACTION_COMMIT = 'transaction.commit',
  TRANSACTION_CANCEL = 'transaction.cancel',
  TRANSACTION_GET = 'transaction.get',
  TRANSACTION_GET_RECEIPT = 'transaction.getReceipt',

  // Phase 13 Security, Permissions & Human-in-the-Loop
  SECURITY_EVALUATE = 'security.evaluate',
  SECURITY_GRANT_PERMISSION = 'security.grantPermission',
  SECURITY_REVOKE_PERMISSION = 'security.revokePermission',
  SECURITY_EMERGENCY_STOP = 'security.emergencyStop',
  SECURITY_SET_TAKEOVER = 'security.setTakeover',
  SECURITY_GET_STATE = 'security.getState',
  SECURITY_GET_AUDIT_LOGS = 'security.getAuditLogs',

  // Phase 14 Production Hardening, Observability & Runtime
  RUNTIME_HEALTH = 'runtime.health',
  RUNTIME_STATUS = 'runtime.status',
  RUNTIME_SUPERVISOR = 'runtime.supervisor',
  RUNTIME_METRICS = 'runtime.metrics',
  RUNTIME_EVENTS = 'runtime.events',
  RUNTIME_DEAD_LETTER_QUEUE = 'runtime.deadLetterQueue',
  CHAOS_INJECT_FAULT = 'chaos.injectFault',

  // Real-time Browser Events
  TAB_CREATED = 'tab.created',
  TAB_UPDATED = 'tab.updated',
  TAB_ACTIVATED = 'tab.activated',
  TAB_REMOVED = 'tab.removed',
  NAVIGATION_REQUESTED = 'navigation.requested',
  NAVIGATION_STARTED = 'navigation.started',
  NAVIGATION_COMPLETED = 'navigation.completed',
  NAVIGATION_FAILED = 'navigation.failed',
  WINDOW_FOCUSED = 'window.focused',
  WINDOW_UPDATED = 'window.updated',

  // Phase 9 Verification & Recovery Events
  VERIFICATION_STARTED = 'verification.started',
  VERIFICATION_PASSED = 'verification.passed',
  VERIFICATION_FAILED = 'verification.failed',
  RECOVERY_STARTED = 'recovery.started',
  USER_INTERVENTION_REQUIRED = 'user.intervention.required',
  WORKFLOW_CHECKPOINT_CREATED = 'workflow.checkpoint.created',

  // Phase 10 Agent Loop Events
  AGENT_GOAL_CREATED = 'agent.goal.created',
  AGENT_GOAL_NORMALIZED = 'agent.goal.normalized',
  AGENT_PLANNING_STARTED = 'agent.planning.started',
  AGENT_PLAN_CREATED = 'agent.plan.created',
  AGENT_PLAN_INVALIDATED = 'agent.plan.invalidated',
  AGENT_REPLANNING_STARTED = 'agent.replanning.started',
  AGENT_ACTION_SELECTED = 'agent.action.selected',
  AGENT_ACTION_EXECUTING = 'agent.action.executing',
  AGENT_ACTION_VERIFIED = 'agent.action.verified',
  AGENT_ACTION_FAILED = 'agent.action.failed',
  AGENT_WAITING_FOR_USER = 'agent.waiting_for_user',
  AGENT_TASK_PAUSED = 'agent.task.paused',
  AGENT_TASK_RESUMED = 'agent.task.resumed',
  AGENT_TASK_COMPLETED = 'agent.task.completed',
  AGENT_TASK_FAILED = 'agent.task.failed',
  AGENT_TASK_ABORTED = 'agent.task.aborted',

  // Phase 12 Transaction Events
  TRANSACTION_CREATED = 'transaction.created',
  TRANSACTION_OPTION_SELECTED = 'transaction.option.selected',
  TRANSACTION_SNAPSHOT_CREATED = 'transaction.snapshot.created',
  TRANSACTION_REVIEW_CREATED = 'transaction.review.created',
  TRANSACTION_CONFIRMATION_REQUESTED = 'transaction.confirmation.requested',
  TRANSACTION_CONFIRMATION_RECEIVED = 'transaction.confirmation.received',
  TRANSACTION_CONFIRMATION_INVALIDATED = 'transaction.confirmation.invalidated',
  TRANSACTION_COMMIT_STARTED = 'transaction.commit.started',
  TRANSACTION_COMMIT_COMPLETED = 'transaction.commit.completed',
  TRANSACTION_COMMIT_FAILED = 'transaction.commit.failed',
  TRANSACTION_OUTCOME_UNKNOWN = 'transaction.outcome.unknown',
  TRANSACTION_VERIFICATION_STARTED = 'transaction.verification.started',
  TRANSACTION_VERIFICATION_COMPLETED = 'transaction.verification.completed',
  TRANSACTION_COMPLETED = 'transaction.completed',
  TRANSACTION_CANCELLED = 'transaction.cancelled',

  // Phase 13 Security Events
  SECURITY_REQUESTED = 'security.requested',
  SECURITY_ALLOWED = 'security.allowed',
  SECURITY_DENIED = 'security.denied',
  SECURITY_BLOCKED = 'security.blocked',
  PERMISSION_GRANTED = 'permission.granted',
  PERMISSION_REVOKED = 'permission.revoked',
  PERMISSION_EXPIRED = 'permission.expired',
  HUMAN_TAKEOVER_STARTED = 'security.takeover.started',
  HUMAN_TAKEOVER_ENDED = 'security.takeover.ended',
  EMERGENCY_STOP_ACTIVATED = 'security.emergency_stop',

  // Phase 14 Runtime & Observability Events
  RUNTIME_STARTED = 'runtime.started',
  RUNTIME_DEGRADED = 'runtime.degraded',
  RUNTIME_RECOVERED = 'runtime.recovered',
  CIRCUIT_BREAKER_OPENED = 'circuit_breaker.opened',
  CIRCUIT_BREAKER_CLOSED = 'circuit_breaker.closed',

  // Phase 7 World Events
  WORLD_CREATED = 'world.created',
  WORLD_UPDATED = 'world.updated',
  WORLD_SNAPSHOT_CREATED = 'world.snapshot.created',
  WORLD_PAGE_CHANGED = 'world.page.changed',
  WORLD_SEMANTIC_CHANGED = 'world.semantic.changed',
  WORLD_VISUAL_CHANGED = 'world.visual.changed',
  WORLD_DIALOG_OPENED = 'world.dialog.opened',
  WORLD_DIALOG_CLOSED = 'world.dialog.closed',
  WORLD_FOCUS_CHANGED = 'world.focus.changed',
  WORLD_INVALIDATED = 'world.world.invalidated'
}

/**
 * Phase 3 Window State Model
 */
export interface WindowState {
  window_id: number;
  type: string;
  focused: boolean;
  state: string;
  tab_ids: number[];
  active_tab_id: number | null;
}

/**
 * Phase 3 Tab Lifecycle States
 */
export type TabStatus = 'CREATED' | 'LOADING' | 'READY' | 'NAVIGATING' | 'ERROR' | 'CLOSED' | 'UNKNOWN';

/**
 * Phase 3 Tab State Model
 */
export interface TabState {
  tab_id: number;
  window_id: number;
  index: number;
  active: boolean;
  url: string;
  title: string;
  status: TabStatus;
  favIconUrl?: string | null;
  last_updated: string;
}

/**
 * Phase 3 Navigation Lifecycle States
 */
export type NavigationStatus = 'REQUESTED' | 'STARTED' | 'LOADING' | 'COMPLETED' | 'FAILED';

/**
 * Phase 3 Navigation Result
 */
export interface NavigationResult {
  navigation_id: string;
  tab_id: number;
  requested_url: string;
  final_url?: string;
  status: NavigationStatus;
  timestamp: string;
  error?: {
    code: string;
    message: string;
  };
}

/**
 * Phase 3 Browser Audit Log Model
 */
export interface BrowserAuditLog {
  action_id: string;
  type: string;
  browser_id: string;
  tab_id: number | null;
  requested_url?: string | null;
  timestamp: string;
  result: 'success' | 'failed';
  error?: string | null;
}

// ============================================================================
// PHASE 4: PAGE OBSERVATION ENGINE MODELS
// ============================================================================

export interface ViewportMetrics {
  width: number;
  height: number;
  scroll_x: number;
  scroll_y: number;
  document_width: number;
  document_height: number;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  top: number;
  left: number;
  right: number;
  bottom: number;
}

export interface InteractiveElement {
  element_id: string;
  tag_name: string;
  role: string;
  text: string;
  href?: string | null;
  input_type?: string | null;
  value?: string | null;
  placeholder?: string | null;
  bounding_box: BoundingBox;
  is_visible: boolean;
  is_in_viewport: boolean;
  is_enabled: boolean;
  attributes: Record<string, string>;
}

export interface HeadingElement {
  level: number;
  text: string;
  id?: string | null;
}

export interface LandmarkElement {
  role: string;
  tag_name: string;
  label?: string | null;
}

export interface FrameElement {
  frame_id: string;
  src: string;
  name?: string | null;
  is_cross_origin: boolean;
}

export interface PageObservation {
  observation_id: string;
  tab_id: number;
  url: string;
  title: string;
  document_state: 'loading' | 'interactive' | 'complete';
  timestamp: string;
  viewport: ViewportMetrics;
  visible_text: string[];
  headings: HeadingElement[];
  landmarks: LandmarkElement[];
  interactive_elements: InteractiveElement[];
  frames: FrameElement[];
}

// ============================================================================
// PHASE 5: SEMANTIC PAGE & ACCESSIBILITY INTELLIGENCE MODELS
// ============================================================================

export type SemanticConfidence = 'HIGH' | 'MEDIUM' | 'LOW';

export type SemanticSource =
  | 'native_html'
  | 'aria'
  | 'label'
  | 'computed_accessibility'
  | 'heuristic';

export type ControlClassification =
  | 'TEXT'
  | 'EMAIL'
  | 'PASSWORD'
  | 'PHONE'
  | 'NUMBER'
  | 'DATE'
  | 'TIME'
  | 'DATETIME'
  | 'URL'
  | 'SEARCH'
  | 'CHECKBOX'
  | 'RADIO'
  | 'SELECT'
  | 'COMBOBOX'
  | 'TEXTAREA'
  | 'FILE'
  | 'RANGE'
  | 'BUTTON'
  | 'SUBMIT'
  | 'LINK'
  | 'TAB'
  | 'MENUITEM'
  | 'OPTION'
  | 'UNKNOWN';

export interface SemanticElementRef {
  semantic_model_id: string;
  observation_id: string;
  element_id: string;
  role: string;
  name: string;
  tag_name: string;
  stable_id?: string | null;
  attributes?: Record<string, string>;
}

export interface SemanticElement {
  element_id: string;
  role: string;
  name: string;
  description?: string | null;
  tag_name: string;
  semantic_type: ControlClassification;
  source: SemanticSource;
  confidence: SemanticConfidence;

  // States
  visible: boolean;
  enabled: boolean;
  focused: boolean;
  required: boolean;
  readonly: boolean;
  selected: boolean;
  checked: boolean;
  expanded?: boolean | null;

  // Privacy & Safety
  sensitive: boolean;
  value_available: boolean;
  value_preview?: string | null;

  bounding_box: BoundingBox;
  parent_id?: string | null;
  child_ids: string[];
  relationships: {
    labelled_by?: string | null;
    described_by?: string | null;
    controls?: string | null;
    owns?: string[];
  };
  attributes: Record<string, string>;
}

export interface FormSemanticGroup {
  form_id: string;
  name: string;
  action?: string | null;
  method?: string | null;
  field_ids: string[];
  submit_button_ids: string[];
  required_field_ids: string[];
}

export interface RadioOption {
  element_id: string;
  name: string;
  selected: boolean;
  disabled: boolean;
}

export interface RadioSemanticGroup {
  group_name: string;
  label: string;
  selected_element_id?: string | null;
  options: RadioOption[];
}

export interface TabSemanticGroup {
  tab_list_id?: string | null;
  tabs: Array<{
    element_id: string;
    name: string;
    selected: boolean;
    controls_panel_id?: string | null;
  }>;
}

export interface DialogSemanticGroup {
  dialog_id: string;
  name: string;
  role: 'dialog' | 'alertdialog';
  visible: boolean;
  interactive_element_ids: string[];
}

export interface TableCell {
  text: string;
  is_header: boolean;
  row_index: number;
  col_index: number;
}

export interface TableSemanticGroup {
  table_id: string;
  name?: string | null;
  headers: string[];
  row_count: number;
  col_count: number;
  rows: TableCell[][];
}

export interface ListSemanticGroup {
  list_id: string;
  type: 'ordered' | 'unordered';
  name?: string | null;
  item_count: number;
  items: string[];
}

export interface SemanticHeading {
  level: number;
  text: string;
  element_id: string;
}

export interface SemanticLandmark {
  role: string;
  tag_name: string;
  label?: string | null;
  element_ids: string[];
}

export interface SemanticPageIndexes {
  byRole: Record<string, string[]>;
  byName: Record<string, string[]>;
  byLabel: Record<string, string[]>;
  byId: Record<string, string>;
  byTag: Record<string, string[]>;
  byType: Record<string, string[]>;
}

export interface SemanticPageModel {
  semantic_model_id: string;
  model_version: number;
  observation_id: string;
  tab_id: number;
  is_stale: boolean;
  timestamp: string;

  page: {
    url: string;
    title: string;
    language: string;
  };

  landmarks: SemanticLandmark[];
  headings: SemanticHeading[];
  interactive_elements: SemanticElement[];
  forms: FormSemanticGroup[];
  radio_groups: RadioSemanticGroup[];
  tabs: TabSemanticGroup[];
  dialogs: DialogSemanticGroup[];
  tables: TableSemanticGroup[];
  lists: ListSemanticGroup[];

  indexes: SemanticPageIndexes;
  debug_tree: string;
  metadata: Record<string, unknown>;
}

export interface SemanticQuery {
  role?: string;
  name?: string;
  label?: string;
  text?: string;
  type?: string;
  id?: string;
  exact?: boolean;
}

export type QueryResultStatus = 'FOUND' | 'NOT_FOUND' | 'AMBIGUOUS' | 'STALE' | 'ERROR';

export interface QueryResult {
  status: QueryResultStatus;
  element?: SemanticElement;
  matches: SemanticElementRef[];
  confidence: SemanticConfidence;
  query: SemanticQuery;
  message?: string;
}

export interface ResolveResult {
  status: 'FOUND' | 'NOT_FOUND' | 'AMBIGUOUS' | 'STALE' | 'INACCESSIBLE';
  element?: SemanticElement;
  matches: SemanticElementRef[];
  reference: SemanticElementRef;
  message?: string;
}

// ============================================================================
// PHASE 6: VISUAL PAGE INTELLIGENCE MODELS
// ============================================================================

export type CoordinateSystem = 'DOM_VIEWPORT' | 'SCREENSHOT_PIXEL' | 'DOCUMENT_SPACE';
export type PrivacyMode = 'STANDARD' | 'STRICT' | 'DEBUG';
export type VisibilityState = 'fully_visible' | 'partially_visible' | 'outside_viewport' | 'hidden';

export interface ScreenshotMetadata {
  id: string;
  tab_id: number;
  url: string;
  width: number;
  height: number;
  device_pixel_ratio: number;
  scroll_x: number;
  scroll_y: number;
  timestamp: string;
  viewport_only: boolean;
  scaled: boolean;
  original_width: number;
  original_height: number;
  format: 'png' | 'webp' | 'jpeg';
  bytes?: number;
  privacy_mode: PrivacyMode;
  redacted_regions_count: number;
  observation_id?: string;
  semantic_model_id?: string;
  visual_version: number;
}

export interface VisualBoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  top: number;
  left: number;
  right: number;
  bottom: number;
  coordinate_system: CoordinateSystem;
}

export interface VisualElementMapping {
  element_id: string;
  visual_id: string;
  dom_box: VisualBoundingBox;
  screenshot_box: VisualBoundingBox;
  confidence: SemanticConfidence;
  visibility: VisibilityState;
  occluded: boolean;
  partially_occluded: boolean;
  z_index: number;
}

export type VisualRegionType =
  | 'HEADER'
  | 'NAVIGATION'
  | 'MAIN'
  | 'SIDEBAR'
  | 'FOOTER'
  | 'SEARCH'
  | 'RESULTS'
  | 'CARD'
  | 'DIALOG'
  | 'OVERLAY'
  | 'TOOLBAR'
  | 'CONTENT'
  | 'CANVAS_CONTAINER'
  | 'UNKNOWN';

export interface VisualRegion {
  region_id: string;
  type: VisualRegionType;
  label?: string | null;
  bounding_box: VisualBoundingBox;
  screenshot_box: VisualBoundingBox;
  z_index: number;
  is_fixed: boolean;
  is_sticky: boolean;
  element_ids: string[];
  visual_element_ids: string[];
}

export type VisualElementType =
  | 'TEXT'
  | 'BUTTON'
  | 'INPUT'
  | 'ICON'
  | 'IMAGE'
  | 'CARD'
  | 'LINK'
  | 'MENU'
  | 'DIALOG'
  | 'TAB'
  | 'CHECKBOX'
  | 'RADIO'
  | 'TABLE'
  | 'CHART'
  | 'CANVAS'
  | 'VIDEO'
  | 'MAP'
  | 'UNKNOWN';

export interface VisualElement {
  visual_id: string;
  semantic_element_id?: string | null;
  type: VisualElementType;
  tag_name: string;
  role?: string | null;
  name?: string | null;
  dom_box: VisualBoundingBox;
  screenshot_box: VisualBoundingBox;
  visibility: VisibilityState;
  z_index: number;
  is_interactive: boolean;
  is_fixed: boolean;
  is_sticky: boolean;
  is_canvas: boolean;
  is_svg: boolean;
  is_image: boolean;
  is_video: boolean;
  confidence: SemanticConfidence;
  source: 'dom_mapped' | 'visual_inferred';
  state: {
    disabled?: boolean;
    focused?: boolean;
    selected?: boolean;
    expanded?: boolean | null;
    checked?: boolean;
  };
  attributes: Record<string, string>;
}

export interface VisualOverlay {
  overlay_id: string;
  visual_id: string;
  type: 'dialog' | 'modal' | 'popup' | 'banner' | 'tooltip' | 'dropdown';
  bounding_box: VisualBoundingBox;
  screenshot_box: VisualBoundingBox;
  z_index: number;
  is_visible: boolean;
  child_visual_ids: string[];
}

export interface FixedElement {
  element_id: string;
  visual_id: string;
  bounding_box: VisualBoundingBox;
  screenshot_box: VisualBoundingBox;
  z_index: number;
  position_type: 'fixed' | 'sticky';
}

export interface VisualPageIndexes {
  byVisualType: Record<string, string[]>;
  bySemanticElement: Record<string, string>;
  byRegion: Record<string, string[]>;
  byInteractive: string[];
  byVisibility: Record<VisibilityState, string[]>;
}

export interface VisualPageModel {
  visual_model_id: string;
  visual_version: number;
  observation_id: string;
  semantic_model_id: string;
  tab_id: number;
  is_stale: boolean;
  timestamp: string;

  screenshot: ScreenshotMetadata;
  viewport: ViewportMetrics;

  regions: VisualRegion[];
  overlays: VisualOverlay[];
  fixed_elements: FixedElement[];
  sticky_elements: FixedElement[];
  visual_elements: VisualElement[];
  mappings: VisualElementMapping[];

  indexes: VisualPageIndexes;
  privacy_mode: PrivacyMode;
  metadata: Record<string, unknown>;
}

export interface VisualSnapshot {
  screenshot_data_url: string;
  metadata: ScreenshotMetadata;
  visual_model?: VisualPageModel;
}

export interface VisualQuery {
  type?: VisualElementType | string;
  region_id?: string;
  semantic_element_id?: string;
  interactive_only?: boolean;
  visible_only?: boolean;
  min_confidence?: SemanticConfidence;
}

export interface VisualQueryResult {
  status: 'FOUND' | 'NOT_FOUND' | 'AMBIGUOUS' | 'STALE' | 'ERROR';
  elements: VisualElement[];
  mappings: VisualElementMapping[];
  count: number;
  query: VisualQuery;
  message?: string;
}

export interface PointQueryResult {
  status: 'FOUND' | 'NOT_FOUND' | 'AMBIGUOUS' | 'STALE';
  x: number;
  y: number;
  coordinate_system: CoordinateSystem;
  topmost_element?: VisualElement;
  candidates: Array<{
    element: VisualElement;
    z_index: number;
    occluded: boolean;
    confidence: SemanticConfidence;
  }>;
  message?: string;
}

export interface VisualGeometryQuery {
  point?: { x: number; y: number; coordinate_system: CoordinateSystem };
  rect?: VisualBoundingBox;
  operation: 'contains_point' | 'intersects_rect' | 'contains_rect' | 'nearest_point';
}

// Vision Provider Abstraction (For future multimodal models / tests)
export interface VisionResult {
  detected_regions?: Array<{ label: string; box: VisualBoundingBox; confidence: number }>;
  text_annotations?: Array<{ text: string; box: VisualBoundingBox }>;
  description?: string;
  raw_response?: Record<string, unknown>;
}

export interface VisionProvider {
  name: string;
  analyze(imageDataUrl: string, context?: Record<string, unknown>): Promise<VisionResult>;
}

/**
 * Versioned Protocol Envelope (1.0)
 */
export interface BridgeEnvelope<T = Record<string, unknown>> {
  protocol_version: string;
  message_id: string;
  type: BridgeMessageType;
  action: BridgeAction | string;
  timestamp: string;
  payload: T;
  success?: boolean;
  error?: {
    code: string;
    message: string;
  };
}

/**
 * Centralized Extension State Model
 */
export interface ExtensionState {
  installed: boolean;
  initialized: boolean;
  serviceWorkerReady: boolean;
  contentScriptReady: boolean;
  extensionVersion: string;
  lastError: string | null;
  environment: ExtensionEnvironment;
  timestamp: string;

  // Phase 2 Bridge State
  bridgeState: BridgeConnectionState;
  bridgeSessionId: string | null;
  bridgeAuthenticated: boolean;
  bridgeLatencyMs: number | null;
  lastHeartbeatAck: string | null;

  // Phase 3 Browser Control State
  browserId: string;
  windowsCount: number;
  tabsCount: number;
  activeTabId: number | null;
  activeTabUrl: string | null;
  navigationState: 'IDLE' | 'NAVIGATING';
  lastCommand: string | null;
  lastCommandResult: 'SUCCESS' | 'FAILED' | null;

  // Reserved for future phases:
  activeWindowId?: number | null;
  observationState?: 'idle' | 'observing' | 'analyzing';
  agentState?: 'idle' | 'active' | 'paused';
}

/**
 * Diagnostic Summary Model (used by Popup and internal health checks)
 */
export interface DiagnosticSummary {
  extensionVersion: string;
  environment: ExtensionEnvironment;
  installed: boolean;
  serviceWorkerStatus: ServiceWorkerStatus;
  contentScriptStatus: ContentScriptStatus;
  serviceWorkerUptimeMs: number;
  lastHealthCheck: string;
  activeTab: {
    id: number | null;
    url: string | null;
    title: string | null;
  } | null;
  lastError: string | null;

  bridge: {
    state: BridgeConnectionState;
    authenticated: boolean;
    sessionId: string | null;
    latencyMs: number | null;
    protocolVersion: string;
    lastHeartbeat: string | null;
    capabilities: string[];
  };

  browser: {
    browserId: string;
    windowsCount: number;
    tabsCount: number;
    activeTabId: number | null;
    activeUrl: string | null;
    navigationState: 'IDLE' | 'NAVIGATING';
    lastCommand: string | null;
    lastResult: 'SUCCESS' | 'FAILED' | null;
  };
}

/**
 * Internal Chrome Message Action Enums
 */
export enum MessageAction {
  PING = 'MATRIOSHAI_PING',
  PONG = 'MATRIOSHAI_PONG',
  GET_STATUS = 'MATRIOSHAI_GET_STATUS',
  REFRESH_STATUS = 'MATRIOSHAI_REFRESH_STATUS',
  CONTENT_SCRIPT_READY = 'MATRIOSHAI_CONTENT_SCRIPT_READY',
  SERVICE_WORKER_READY = 'MATRIOSHAI_SERVICE_WORKER_READY',
  RECORD_ERROR = 'MATRIOSHAI_RECORD_ERROR',
  BRIDGE_CONNECT = 'MATRIOSHAI_BRIDGE_CONNECT',
  BRIDGE_DISCONNECT = 'MATRIOSHAI_BRIDGE_DISCONNECT',
  PAGE_OBSERVE = 'MATRIOSHAI_PAGE_OBSERVE',

  // Phase 5 Semantic IPC
  PAGE_SEMANTIC_OBSERVE = 'MATRIOSHAI_PAGE_SEMANTIC_OBSERVE',
  PAGE_SEMANTIC_QUERY = 'MATRIOSHAI_PAGE_SEMANTIC_QUERY',
  PAGE_RESOLVE_ELEMENT = 'MATRIOSHAI_PAGE_RESOLVE_ELEMENT',
  PAGE_GET_SEMANTIC_MODEL = 'MATRIOSHAI_PAGE_GET_SEMANTIC_MODEL',
  PAGE_INVALIDATE_SEMANTIC_MODEL = 'MATRIOSHAI_PAGE_INVALIDATE_SEMANTIC_MODEL',

  // Phase 6 Visual IPC
  PAGE_CAPTURE_SCREENSHOT = 'MATRIOSHAI_PAGE_CAPTURE_SCREENSHOT',
  PAGE_VISUAL_OBSERVE = 'MATRIOSHAI_PAGE_VISUAL_OBSERVE',
  PAGE_GET_VISUAL_MODEL = 'MATRIOSHAI_PAGE_GET_VISUAL_MODEL',
  PAGE_GET_VISUAL_ELEMENT = 'MATRIOSHAI_PAGE_GET_VISUAL_ELEMENT',
  PAGE_VISUAL_POINT_QUERY = 'MATRIOSHAI_PAGE_VISUAL_POINT_QUERY',
  PAGE_VISUAL_QUERY = 'MATRIOSHAI_PAGE_VISUAL_QUERY',
  PAGE_INVALIDATE_VISUAL_MODEL = 'MATRIOSHAI_PAGE_INVALIDATE_VISUAL_MODEL',

  // Phase 7 World Model IPC
  PAGE_GET_WORLD_PAGE_STATE = 'MATRIOSHAI_PAGE_GET_WORLD_PAGE_STATE',
  PAGE_RESOLVE_WORLD_ELEMENT = 'MATRIOSHAI_PAGE_RESOLVE_WORLD_ELEMENT',

  // Phase 8 Action Engine IPC
  ACTION_EXECUTE_DOM = 'MATRIOSHAI_ACTION_EXECUTE_DOM'
}

// ============================================================================
// PHASE 7: UNIFIED BROWSER WORLD MODEL TYPES
// ============================================================================

export type WorldStatus = 'CONNECTING' | 'SYNCING' | 'READY' | 'DEGRADED' | 'STALE' | 'DISCONNECTED';
export type PageLifecycleState = 'UNKNOWN' | 'LOADING' | 'READY' | 'STALE' | 'FAILED' | 'CLOSED';
export type TransitionType =
  | 'NAVIGATION'
  | 'TAB_CHANGE'
  | 'PAGE_CHANGE'
  | 'DOM_CHANGE'
  | 'VISUAL_CHANGE'
  | 'FORM_STATE_CHANGE'
  | 'DIALOG_OPEN'
  | 'DIALOG_CLOSE'
  | 'FOCUS_CHANGE'
  | 'SCROLL_CHANGE'
  | 'VIEWPORT_CHANGE'
  | 'TAB_CREATED'
  | 'TAB_CLOSED'
  | 'UNKNOWN';

export type ResolutionStatus = 'FOUND' | 'NOT_FOUND' | 'AMBIGUOUS' | 'STALE' | 'PAGE_CHANGED' | 'TAB_CLOSED';
export type ArtifactStatus = 'ACTIVE' | 'STALE' | 'EXPIRED' | 'DELETED';
export type DataSource = 'browser_api' | 'dom' | 'accessibility' | 'semantic_engine' | 'visual_engine' | 'derived';

export interface BrowserSessionState {
  browser_session_id: string;
  extension_session_id: string;
  connected: boolean;
  timestamp: string;
  capabilities: string[];
  active_window_id: number | null;
  active_tab_id: number | null;
}

export interface WorldWindowState {
  window_id: number;
  focused: boolean;
  state: 'normal' | 'minimized' | 'maximized' | 'fullscreen';
  width?: number;
  height?: number;
  top?: number;
  left?: number;
  tab_ids: number[];
  active_tab_id?: number | null;
}

export interface WorldTabState {
  tab_id: number;
  window_id: number;
  index: number;
  active: boolean;
  highlighted: boolean;
  pinned: boolean;
  url: string;
  title: string;
  status: TabStatus;
  favIconUrl?: string | null;
  opener_tab_id?: number | null;
  last_updated: string;
}

export interface WorldFrameState {
  frame_id: string;
  parent_frame_id?: string | null;
  tab_id: number;
  origin: string;
  url: string;
  accessible: boolean;
  page_version: number;
  semantic_model_reference?: string | null;
  visual_reference?: string | null;
}

export interface FrameTreeNode {
  frame: WorldFrameState;
  children: FrameTreeNode[];
}

export interface FrameTree {
  tab_id: number;
  root_frame: FrameTreeNode;
  frame_count: number;
}

export interface NavigationHistoryItem {
  navigation_id: string;
  tab_id: number;
  url: string;
  timestamp: string;
  title?: string | null;
}

export interface NavigationState {
  current_url: string;
  previous_url?: string | null;
  navigation_id: string;
  navigation_type: 'INITIAL' | 'LINK' | 'TYPED' | 'RELOAD' | 'BACK_FORWARD' | 'SPA' | 'UNKNOWN';
  started_at: string;
  completed_at?: string | null;
  status: 'navigation_started' | 'navigation_completed' | 'navigation_failed';
  history: NavigationHistoryItem[];
}

export interface WorldPageState {
  page_id: string;
  tab_id: number;
  url: string;
  origin: string;
  title: string;
  ready_state: string;
  visibility_state: string;
  page_version: number;
  observation_id?: string | null;
  semantic_model_id?: string | null;
  visual_model_id?: string | null;
  scroll_x: number;
  scroll_y: number;
  viewport_width: number;
  viewport_height: number;
  document_width: number;
  document_height: number;
  active_dialogs: string[];
  focused_element_id?: string | null;
  has_overlay: boolean;
  lifecycle: PageLifecycleState;
  timestamp: string;
}

export interface WorldElementRef {
  page_id: string;
  observation_id: string;
  element_id: string;
  semantic_model_id?: string | null;
  visual_id?: string | null;
  tag_name?: string;
  role?: string;
  name?: string;
  page_version: number;
  stable_dom_identity?: string | null;
}

export interface WorldElement {
  element_ref: WorldElementRef;
  role: string;
  name: string;
  semantic_state: {
    type: string;
    description?: string | null;
    focused: boolean;
    disabled: boolean;
    required: boolean;
    checked: boolean;
    expanded?: boolean | null;
    sensitive: boolean;
  };
  visual_state?: {
    visual_id: string;
    visibility: VisibilityState;
    occluded: boolean;
    partially_occluded: boolean;
    z_index: number;
    is_canvas: boolean;
    is_svg: boolean;
  } | null;
  geometry: VisualBoundingBox;
  parent_ref?: string | null;
  child_refs: string[];
  visible: boolean;
  enabled: boolean;
  semantic_confidence: string;
  visual_confidence: string;
  source: DataSource;
  page_version: number;
}

export interface WorldElementResolution {
  status: ResolutionStatus;
  element?: WorldElement | null;
  reference: WorldElementRef;
  candidates: WorldElementRef[];
  message?: string | null;
}

export interface WorldStateTransition {
  transition_id: string;
  timestamp: string;
  source_version: number;
  target_version: number;
  type: TransitionType;
  tab_id?: number | null;
  changed_entities: {
    tabs_changed?: number[];
    pages_changed?: string[];
    dialogs_changed?: string[];
    elements_changed?: string[];
  };
  summary: string;
}

export interface EntityDiff<T = unknown> {
  added: T[];
  removed: T[];
  changed: { before: T; after: T }[];
  unchanged_count: number;
}

export interface WorldStateDiff {
  diff_id: string;
  source_snapshot_id: string;
  target_snapshot_id: string;
  source_version: number;
  target_version: number;
  timestamp: string;
  tabs_diff: EntityDiff<WorldTabState>;
  pages_diff: EntityDiff<WorldPageState>;
  elements_diff: EntityDiff<WorldElement>;
  dialogs_diff: EntityDiff<string>;
  navigation_changed: boolean;
  summary: string[];
}

export interface BrowserWorldSnapshot {
  snapshot_id: string;
  timestamp: string;
  world_model_version: number;
  active_tab_id: number | null;
  tab_states: WorldTabState[];
  page_states: WorldPageState[];
  semantic_references: Record<number, string>;
  visual_references: Record<number, string>;
  navigation_state?: NavigationState | null;
  reason?: string;
}

export interface PageCapabilities {
  canObserveDom: boolean;
  canObserveAccessibility: boolean;
  canCaptureScreenshot: boolean;
  canObserveFrames: boolean;
  canObserveSemanticModel: boolean;
  canObserveVisualModel: boolean;
}

export interface BrowserCapabilities {
  tabObservation: boolean;
  pageObservation: boolean;
  semanticObservation: boolean;
  screenshotCapture: boolean;
  frameObservation: boolean;
  actionExecution: false;
  computerVision: false;
  agentPlanning: false;
}

export interface WorldHealth {
  status: WorldStatus;
  browser_connected: boolean;
  active_tab_available: boolean;
  page_observation_available: boolean;
  semantic_model_available: boolean;
  visual_model_available: boolean;
  stale_artifacts: number;
  unresolved_references: number;
  last_reconciliation_time?: string | null;
}

export interface BrowserWorldModel {
  world_model_id: string;
  world_model_version: number;
  browser_session: BrowserSessionState;
  active_window?: WorldWindowState | null;
  windows: WorldWindowState[];
  tabs: WorldTabState[];
  active_tab_id: number | null;
  pages: WorldPageState[];
  frame_trees: Record<number, FrameTree>;
  observations: Record<number, string>;
  semantic_models: Record<number, string>;
  visual_models: Record<number, string>;
  navigation_states: Record<number, NavigationState>;
  temporal_transitions: WorldStateTransition[];
  capabilities: BrowserCapabilities;
  status: WorldStatus;
  health: WorldHealth;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface WorldQuery {
  type: 'element' | 'page' | 'tab' | 'dialog' | 'overlay' | 'window';
  tab_id?: number;
  page_id?: string;
  role?: string;
  name?: string;
  visible_only?: boolean;
  interactive_only?: boolean;
  dialog_only?: boolean;
}

export interface WorldQueryResult {
  status: 'FOUND' | 'NOT_FOUND' | 'AMBIGUOUS' | 'STALE';
  query: WorldQuery;
  elements: WorldElement[];
  pages: WorldPageState[];
  tabs: WorldTabState[];
  count: number;
  message?: string | null;
}

// ============================================================================
// PHASE 8: SAFE BROWSER ACTION ENGINE TYPES
// ============================================================================

export type ActionType =
  | 'NAVIGATE'
  | 'CLICK'
  | 'TYPE'
  | 'CLEAR_INPUT'
  | 'SELECT'
  | 'CHECK'
  | 'UNCHECK'
  | 'FOCUS'
  | 'SCROLL'
  | 'KEY_PRESS'
  | 'WAIT';

export type ActionPolicyCategory = 'SAFE' | 'SENSITIVE' | 'HIGH_IMPACT' | 'BLOCKED';
export type PolicyDecision = 'ALLOW' | 'BLOCK' | 'REQUIRE_CONFIRMATION';

export type ActionTargetResolutionStatus =
  | 'FOUND'
  | 'NOT_FOUND'
  | 'AMBIGUOUS'
  | 'STALE'
  | 'INVISIBLE'
  | 'DISABLED'
  | 'OCCLUDED'
  | 'WRONG_PAGE'
  | 'WRONG_TAB'
  | 'WRONG_FRAME';

export type ActionStatus =
  | 'SUCCESS'
  | 'FAILED'
  | 'BLOCKED'
  | 'REQUIRES_CONFIRMATION'
  | 'STALE'
  | 'NOT_FOUND'
  | 'AMBIGUOUS'
  | 'TIMEOUT'
  | 'CANCELLED'
  | 'NO_OP'
  | 'WOULD_EXECUTE';

export interface ActionTarget {
  world_element_ref?: WorldElementRef | null;
  semantic_element_ref?: SemanticElementRef | null;
  visual_element_ref?: string | null;
  coordinates?: { x: number; y: number; coordinate_system?: CoordinateSystem } | null;
  url?: string | null;
  tab_id?: number | null;
  frame_id?: string | null;
  expected_role?: string | null;
  expected_name?: string | null;
  expected_geometry?: VisualBoundingBox | null;
  confidence?: string;
  allow_coordinate_fallback?: boolean;
}

export interface ActionPrecondition {
  type:
    | 'ELEMENT_EXISTS'
    | 'ELEMENT_VISIBLE'
    | 'ELEMENT_ENABLED'
    | 'ELEMENT_EDITABLE'
    | 'URL_MATCHES'
    | 'PAGE_VERSION_MATCHES'
    | 'DIALOG_PRESENT'
    | 'DIALOG_ABSENT';
  target_ref?: string | null;
  expected_value?: unknown;
}

export interface ActionPostcondition {
  type:
    | 'URL_CHANGED'
    | 'ELEMENT_STATE_CHANGED'
    | 'DIALOG_APPEARED'
    | 'DIALOG_DISAPPEARED'
    | 'TEXT_PRESENT'
    | 'VALUE_CHANGED';
  target_ref?: string | null;
  expected_value?: unknown;
}

export interface ActionIntent {
  action_id: string;
  type: ActionType;
  target?: ActionTarget | null;
  parameters?: {
    text?: string;
    value?: string;
    key?: string;
    direction?: 'UP' | 'DOWN' | 'LEFT' | 'RIGHT';
    amount?: number;
    duration_ms?: number;
    condition?: string;
    url?: string;
    sensitive?: boolean;
    value_redacted?: boolean;
    dry_run?: boolean;
    [key: string]: unknown;
  } | null;
  world_model_version: number;
  page_version: number;
  tab_id?: number | null;
  page_id?: string | null;
  requested_by?: string;
  confidence?: string;
  policy_context?: Record<string, unknown>;
  preconditions?: ActionPrecondition[];
  postconditions?: ActionPostcondition[];
  timeout_ms?: number;
  created_at: string;
  expires_at?: string | null;
}

export interface ActionConfirmationRequest {
  confirmation_id: string;
  action_id: string;
  action_type: ActionType;
  target_description: string;
  impact_level: ActionPolicyCategory;
  summary: string;
  requested_at: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED';
}

export interface ActionConfirmationResponse {
  confirmation_id: string;
  action_id: string;
  approved: boolean;
  user_note?: string;
  timestamp: string;
}

export interface ActionTraceStep {
  stage:
    | 'ACTION_CREATED'
    | 'SCHEMA_VALIDATED'
    | 'WORLD_VERSION_CHECKED'
    | 'PAGE_VALIDATED'
    | 'TARGET_RESOLVED'
    | 'PRECONDITIONS_EVALUATED'
    | 'POLICY_EVALUATED'
    | 'CONFIRMATION_CHECKED'
    | 'EXECUTION_STARTED'
    | 'DOM_DISPATCHED'
    | 'EXECUTION_COMPLETED'
    | 'RESULT_RETURNED';
  timestamp: string;
  status: 'PASS' | 'FAIL' | 'BLOCKED' | 'SKIPPED' | 'INFO';
  detail?: string;
}

export interface ActionTrace {
  action_id: string;
  steps: ActionTraceStep[];
  started_at: string;
  completed_at?: string | null;
}

export interface ActionResult {
  action_id: string;
  type: ActionType;
  status: ActionStatus;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  world_model_version_before: number;
  world_model_version_after?: number | null;
  target?: ActionTarget | null;
  trace: ActionTrace;
  expected_postconditions?: ActionPostcondition[];
  execution_metadata?: Record<string, unknown>;
  error?: {
    code: string;
    message: string;
    retryable: boolean;
    requires_replan: boolean;
  } | null;
}

export interface ActionQueueItem {
  intent: ActionIntent;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'CANCELLED';
  queued_at: string;
}

export interface ActionQueueStatus {
  tab_id: number;
  is_locked: boolean;
  active_action_id?: string | null;
  queue_length: number;
  items: ActionQueueItem[];
}

// ============================================================================
// PHASE 9: ACTION VERIFICATION, RECOVERY & STATE RECONCILIATION TYPES
// ============================================================================

export type VerificationStatus =
  | 'VERIFIED_SUCCESS'
  | 'VERIFIED_FAILURE'
  | 'PARTIAL_SUCCESS'
  | 'UNKNOWN'
  | 'STALE'
  | 'NOT_EXECUTED'
  | 'CANCELLED'
  | 'BLOCKED'
  | 'TIMEOUT'
  | 'CONFLICTING_EVIDENCE';

export type VerificationState =
  | 'PENDING'
  | 'OBSERVING'
  | 'EVALUATING'
  | 'SUCCESS'
  | 'FAILURE'
  | 'UNKNOWN'
  | 'RECOVERING'
  | 'ABORTED';

export type FailureClass =
  | 'TARGET_FAILURE'
  | 'EXECUTION_FAILURE'
  | 'NAVIGATION_FAILURE'
  | 'PAGE_FAILURE'
  | 'NETWORK_FAILURE'
  | 'VALIDATION_FAILURE'
  | 'POLICY_FAILURE'
  | 'TIMEOUT_FAILURE'
  | 'STATE_MISMATCH'
  | 'AMBIGUOUS_OUTCOME'
  | 'AUTHENTICATION_REQUIRED'
  | 'CAPTCHA_PRESENT'
  | 'RATE_LIMITED'
  | 'SERVER_ERROR'
  | 'USER_CANCELLED'
  | 'BROWSER_DISCONNECTED'
  | 'BRIDGE_FAILURE'
  | 'CONFLICTING_EVIDENCE'
  | 'UNKNOWN_FAILURE';

export type RecoveryType =
  | 'NO_ACTION'
  | 'WAIT'
  | 'REFRESH_WORLD'
  | 'RETRY'
  | 'RE_RESOLVE_TARGET'
  | 'REPLAN'
  | 'ASK_USER'
  | 'ABORT';

export type IdempotencyClass =
  | 'IDEMPOTENT'
  | 'CONDITIONALLY_IDEMPOTENT'
  | 'NON_IDEMPOTENT'
  | 'UNKNOWN';

export type PostconditionEvaluationMode = 'ALL' | 'ANY' | 'AT_LEAST_N';

export interface ConditionEvaluationResult {
  condition: ActionPostcondition;
  status: 'PASS' | 'FAIL' | 'UNKNOWN';
  evidence_description?: string;
  timestamp: string;
}

export interface VerificationEvidence {
  evidence_id: string;
  source: 'NAVIGATION' | 'DOM' | 'SEMANTIC' | 'VISUAL' | 'EVENT' | 'SNAPSHOT_DIFF';
  type: string;
  description: string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface VerificationWaitPolicy {
  initial_delay_ms: number;
  poll_interval_ms: number;
  max_timeout_ms: number;
  mode: 'FAST' | 'NORMAL' | 'LONG' | 'DYNAMIC';
}

export interface RecoveryRecommendation {
  recommendation_id: string;
  action_id: string;
  failure_class: FailureClass;
  recovery_type: RecoveryType;
  suggested_action?: ActionIntent | null;
  reason: string;
  attempt_count: number;
  max_attempts: number;
  requires_user_intervention: boolean;
  intervention_type?: 'LOGIN_REQUIRED' | 'CAPTCHA_PRESENT' | 'AMBIGUOUS_TARGET' | 'HIGH_IMPACT_UNKNOWN' | 'PAYMENT_CONFIRMATION' | 'UNEXPECTED_STATE' | null;
  created_at: string;
}

export interface RecoveryTraceStep {
  attempt: number;
  failure_class: FailureClass;
  recovery_type: RecoveryType;
  result_status: VerificationStatus;
  timestamp: string;
  note?: string;
}

export interface RecoveryTrace {
  action_id: string;
  steps: RecoveryTraceStep[];
  started_at: string;
  completed_at?: string | null;
}

export interface VerificationResult {
  verification_id: string;
  action_id: string;
  status: VerificationStatus;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
  before_snapshot_id?: string | null;
  after_snapshot_id?: string | null;
  before_world_version: number;
  after_world_version: number;
  evaluated_postconditions: ConditionEvaluationResult[];
  state_changes?: WorldStateDiff | null;
  evidence: VerificationEvidence[];
  failure_class?: FailureClass | null;
  recovery_recommendation?: RecoveryRecommendation | null;
  is_stable: boolean;
  duration_ms: number;
  timestamp: string;
}

export interface UserInterventionRequest {
  intervention_id: string;
  type: 'LOGIN_REQUIRED' | 'CAPTCHA_PRESENT' | 'AMBIGUOUS_TARGET' | 'HIGH_IMPACT_UNKNOWN' | 'PAYMENT_CONFIRMATION' | 'UNEXPECTED_STATE';
  what_happened: string;
  why_stopped: string;
  action_required: string;
  tab_id?: number | null;
  action_id?: string | null;
  status: 'PENDING' | 'RESOLVED' | 'ABORTED';
  created_at: string;
  resolved_at?: string | null;
}

export interface WorkflowCheckpoint {
  checkpoint_id: string;
  name: string;
  step_index: number;
  snapshot_id: string;
  world_version: number;
  tab_id?: number | null;
  metadata?: Record<string, unknown>;
  timestamp: string;
}

// ============================================================================
// PHASE 10: AGENT PLANNING & EXECUTION LOOP DATA STRUCTURES
// ============================================================================

export type AgentTaskState =
  | 'CREATED'
  | 'UNDERSTANDING'
  | 'PLANNING'
  | 'READY'
  | 'EXECUTING'
  | 'VERIFYING'
  | 'REPLANNING'
  | 'WAITING_FOR_USER'
  | 'PAUSED'
  | 'COMPLETED'
  | 'FAILED'
  | 'ABORTED'
  | 'EXPIRED';

export type TaskPriority = 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';

export type PlanDecisionType =
  | 'EXECUTE_ACTION'
  | 'WAIT'
  | 'REPLAN'
  | 'ASK_USER'
  | 'COMPLETE'
  | 'ABORT';

export type TabRole = 'PRIMARY' | 'REFERENCE' | 'AUTHENTICATION' | 'COMPARISON' | 'TRANSACTION';

export interface TaskTabContext {
  tab_id: number;
  role: TabRole;
  purpose: string;
  current_url: string;
  relevance: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface TaskAssumption {
  assumption_id: string;
  statement: string;
  source: 'INFERRED' | 'USER_SPECIFIED' | 'DEFAULT';
  is_valid: boolean;
  invalidated_reason?: string | null;
  timestamp: string;
}

export interface SuccessCriterion {
  criterion_id: string;
  description: string;
  evaluation_type: 'URL_MATCH' | 'ELEMENT_PRESENT' | 'TEXT_PRESENT' | 'VERIFICATION_PASSED' | 'CUSTOM';
  expected_value?: string | null;
  is_satisfied: boolean;
  evidence?: string | null;
}

export interface AgentGoal {
  goal_id: string;
  user_request: string;
  normalized_goal: Record<string, unknown>;
  hard_constraints: string[];
  soft_preferences: string[];
  success_criteria: SuccessCriterion[];
  forbidden_actions: string[];
  confirmation_policy: 'NEVER' | 'HIGH_IMPACT_ONLY' | 'ALWAYS';
  priority: TaskPriority;
  deadline?: string | null;
  created_at: string;
}

export interface PlanStep {
  step_id: string;
  step_index: number;
  description: string;
  objective: string;
  preconditions: string[];
  intended_action?: ActionIntent | null;
  expected_outcome?: Record<string, unknown> | null;
  postconditions: ActionPostcondition[];
  dependencies: string[];
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'PENDING' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';
}

export interface AgentPlan {
  plan_id: string;
  goal_id: string;
  version: number;
  steps: PlanStep[];
  assumptions: TaskAssumption[];
  dependencies: string[];
  success_criteria: SuccessCriterion[];
  is_active: boolean;
  created_at: string;
}

export interface PlanDecision {
  decision: PlanDecisionType;
  selected_step?: PlanStep | null;
  intended_action?: ActionIntent | null;
  reason: string;
  question_for_user?: string | null;
  clarification_options?: string[];
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
}

export interface TaskProgress {
  total_objectives: number;
  completed_objectives: number;
  remaining_objectives: number;
  failed_objectives: number;
  current_milestone: string;
  percent_complete: number;
}

export interface TaskMemory {
  completed_step_ids: string[];
  failed_step_ids: string[];
  executed_action_ids: string[];
  observations: string[];
  user_decisions: Record<string, string>;
  checkpoints: string[];
}

export interface AgentResult {
  task_id: string;
  goal_id: string;
  status: AgentTaskState;
  summary: string;
  completed_objectives: string[];
  remaining_objectives: string[];
  actions_executed: number;
  recoveries_attempted: number;
  user_interventions_count: number;
  final_world_version: number;
  duration_ms: number;
  evidence: string[];
}

export interface AgentTask {
  task_id: string;
  goal: AgentGoal;
  state: AgentTaskState;
  current_plan?: AgentPlan | null;
  plans: AgentPlan[];
  progress: TaskProgress;
  memory: TaskMemory;
  tab_contexts: Record<number, TaskTabContext>;
  active_tab_id?: number | null;
  iteration_count: number;
  max_iterations: number;
  planner_calls_count: number;
  max_planner_calls: number;
  result?: AgentResult | null;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// PHASE 12: REAL-WORLD TRANSACTION & BOOKING ENGINE DATA STRUCTURES
// ============================================================================

export type TransactionState =
  | 'DISCOVERING'
  | 'COMPARING'
  | 'SELECTED'
  | 'PREPARING'
  | 'READY_FOR_REVIEW'
  | 'AWAITING_CONFIRMATION'
  | 'CONFIRMED'
  | 'COMMITTING'
  | 'COMMITTED'
  | 'VERIFYING'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'FAILED'
  | 'EXPIRED'
  | 'BLOCKED'
  | 'UNKNOWN_OUTCOME';

export type TransactionType =
  | 'FLIGHT_BOOKING'
  | 'HOTEL_BOOKING'
  | 'TRAIN_BOOKING'
  | 'BUS_BOOKING'
  | 'EVENT_TICKET'
  | 'MOVIE_TICKET'
  | 'RESTAURANT_RESERVATION'
  | 'APPOINTMENT'
  | 'PRODUCT_PURCHASE'
  | 'SERVICE_BOOKING'
  | 'SUBSCRIPTION'
  | 'OTHER';

export type AvailabilityState =
  | 'AVAILABLE'
  | 'LIMITED'
  | 'UNAVAILABLE'
  | 'UNKNOWN'
  | 'CHANGED';

export type CommitPolicy =
  | 'ALWAYS_CONFIRM'
  | 'CONFIRM_IF_PRICE_ABOVE_THRESHOLD'
  | 'CONFIRM_IF_IRREVERSIBLE'
  | 'USER_PREAUTHORIZED'
  | 'NEVER_AUTO_COMMIT';

export type TransactionRisk = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface TransactionPrice {
  base: number;
  tax: number;
  fees: number;
  discount: number;
  total: number;
  currency: string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
}

export interface TransactionConstraint {
  constraint_id: string;
  name: string;
  type: 'HARD' | 'SOFT';
  value: string;
  is_satisfied: boolean;
}

export interface TransactionPreference {
  preference_id: string;
  dimension: 'PRICE' | 'DURATION' | 'STOPS' | 'TIME' | 'PROVIDER' | 'REFUNDABILITY';
  target_value: string;
  weight: number;
}

export interface TransactionOption {
  option_id: string;
  provider: string;
  title: string;
  price: TransactionPrice;
  availability: AvailabilityState;
  attributes: Record<string, unknown>;
  constraints_satisfied: boolean;
  preference_score: number;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
  source_reference?: string | null;
}

export interface TransactionSnapshot {
  snapshot_id: string;
  transaction_id: string;
  version: number;
  selected_option: TransactionOption;
  price: TransactionPrice;
  availability: AvailabilityState;
  provider: string;
  important_conditions: string[];
  cancellation_policy: string;
  timestamp: string;
}

export interface TransactionReview {
  review_id: string;
  transaction_id: string;
  item_title: string;
  provider: string;
  route_or_location?: string | null;
  date_time?: string | null;
  price: TransactionPrice;
  important_restrictions: string[];
  cancellation_refund_conditions: string[];
  is_irreversible: boolean;
  risk_level: TransactionRisk;
  commit_action_description: string;
}

export interface TransactionConfirmation {
  confirmation_id: string;
  transaction_id: string;
  option_id: string;
  snapshot_version: number;
  status: 'PENDING' | 'CONFIRMED' | 'REJECTED' | 'EXPIRED' | 'INVALIDATED';
  confirmed_at?: string | null;
  expires_at: string;
  user_note?: string | null;
}

export interface CommitAuthorization {
  auth_token: string;
  transaction_id: string;
  confirmation_id: string;
  policy_version: number;
  snapshot_version: number;
  expires_at: string;
}

export interface TransactionReceipt {
  receipt_id: string;
  transaction_id: string;
  provider: string;
  reference_number: string;
  amount: number;
  currency: string;
  booking_date: string;
  status: 'COMPLETED' | 'PENDING' | 'REFUNDED';
  evidence_summary: string;
  created_at: string;
}

export interface Transaction {
  transaction_id: string;
  workflow_id?: string | null;
  type: TransactionType;
  merchant: string;
  provider: string;
  product_or_service: string;
  status: TransactionState;
  currency: string;
  amount: number;
  taxes: number;
  fees: number;
  total: number;
  selected_option?: TransactionOption | null;
  options: TransactionOption[];
  constraints: TransactionConstraint[];
  user_preferences: TransactionPreference[];
  confirmation_policy: CommitPolicy;
  commit_boundary: string;
  risk_level: TransactionRisk;
  active_snapshot?: TransactionSnapshot | null;
  active_review?: TransactionReview | null;
  active_confirmation?: TransactionConfirmation | null;
  receipt?: TransactionReceipt | null;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// PHASE 13: SECURITY, PERMISSIONS & HUMAN-IN-THE-LOOP DATA STRUCTURES
// ============================================================================

export type SecurityDecision =
  | 'ALLOW'
  | 'ALLOW_WITH_CONFIRMATION'
  | 'DENY'
  | 'BLOCK'
  | 'ESCALATE'
  | 'REQUIRE_USER'
  | 'REQUIRE_AUTHENTICATION';

export type SecurityActor =
  | 'USER'
  | 'MATRIOSHAI_AGENT'
  | 'SYSTEM'
  | 'EXTENSION'
  | 'WORKFLOW_ENGINE'
  | 'TRANSACTION_ENGINE';

export type PermissionCategory =
  | 'OBSERVE_PAGE'
  | 'READ_PAGE_DATA'
  | 'NAVIGATE'
  | 'CLICK'
  | 'TYPE'
  | 'SCROLL'
  | 'OPEN_TAB'
  | 'CLOSE_TAB'
  | 'UPLOAD_FILE'
  | 'DOWNLOAD_FILE'
  | 'USE_CLIPBOARD'
  | 'ACCESS_LOCATION'
  | 'ACCESS_CONTACTS'
  | 'SEND_MESSAGE'
  | 'MODIFY_ACCOUNT'
  | 'PURCHASE'
  | 'BOOK'
  | 'PAY'
  | 'DELETE'
  | 'SUBMIT'
  | 'USE_EXTERNAL_SERVICE';

export type PermissionScope =
  | 'GLOBAL'
  | 'DOMAIN'
  | 'SITE'
  | 'TAB'
  | 'WORKFLOW'
  | 'TASK'
  | 'ACTION'
  | 'TRANSACTION';

export type DomainTrustLevel =
  | 'UNKNOWN'
  | 'LOW'
  | 'MEDIUM'
  | 'TRUSTED'
  | 'RESTRICTED'
  | 'BLOCKED';

export type DataClassification =
  | 'PUBLIC'
  | 'INTERNAL'
  | 'PRIVATE'
  | 'SENSITIVE'
  | 'HIGHLY_SENSITIVE'
  | 'SECRET';

export type AutonomyLevel =
  | 'MANUAL'
  | 'ASSISTED'
  | 'SUPERVISED'
  | 'AUTONOMOUS_WITH_CONFIRMATION'
  | 'LIMITED_AUTONOMOUS';

export type TakeoverState =
  | 'AGENT_CONTROL'
  | 'USER_CONTROL'
  | 'SHARED_CONTROL'
  | 'PAUSED';

export interface DomainPermission {
  domain: string;
  permissions: PermissionCategory[];
  scope: PermissionScope;
  trust_level: DomainTrustLevel;
  expires_at?: string | null;
  created_by: SecurityActor;
  status: 'ACTIVE' | 'REVOKED' | 'EXPIRED';
}

export interface SecurityRequest {
  request_id: string;
  actor: SecurityActor;
  workflow_id?: string | null;
  task_id?: string | null;
  action_type: string;
  target_domain?: string | null;
  target_url?: string | null;
  resource?: string | null;
  data_classification: DataClassification;
  risk_level: string;
  transaction_id?: string | null;
  reason: string;
  timestamp: string;
}

export interface ActionAuthorization {
  authorization_id: string;
  actor: SecurityActor;
  workflow_id?: string | null;
  action_id: string;
  permission: PermissionCategory;
  target_domain?: string | null;
  state_version: number;
  policy_version: number;
  expires_at: string;
  nonce: string;
}

export interface UserApprovalToken {
  token_id: string;
  confirmation_id: string;
  action_id: string;
  transaction_id?: string | null;
  state_version: number;
  expires_at: string;
}

export interface SpendingLimitPolicy {
  currency: string;
  maximum_amount: number;
  time_window: 'PER_TRANSACTION' | 'DAILY' | 'MONTHLY';
  confirmation_required: boolean;
}

export interface SecurityStateSummary {
  autonomy_level: AutonomyLevel;
  takeover_state: TakeoverState;
  emergency_stop_active: boolean;
  active_permissions_count: number;
  blocked_domains: string[];
  pending_authorizations_count: number;
  spending_limits: SpendingLimitPolicy[];
}

// ============================================================================
// PHASE 14: PRODUCTION HARDENING, RELIABILITY & OBSERVABILITY DATA STRUCTURES
// ============================================================================

export type RuntimeState =
  | 'STARTING'
  | 'READY'
  | 'RUNNING'
  | 'PAUSED'
  | 'DEGRADED'
  | 'RECOVERING'
  | 'STOPPING'
  | 'STOPPED'
  | 'FAILED'
  | 'SECURITY_LOCKED';

export type HealthState =
  | 'HEALTHY'
  | 'DEGRADED'
  | 'UNAVAILABLE'
  | 'FAILED'
  | 'UNKNOWN';

export type RestartPolicy =
  | 'IMMEDIATE'
  | 'BACKOFF'
  | 'MANUAL'
  | 'NEVER';

export type CircuitBreakerState =
  | 'CLOSED'
  | 'OPEN'
  | 'HALF_OPEN';

export type DecisionConfidence =
  | 'HIGH'
  | 'MEDIUM'
  | 'LOW'
  | 'UNKNOWN';

export interface ComponentHealth {
  component_name: string;
  status: HealthState;
  version: string;
  last_success?: string | null;
  last_failure?: string | null;
  consecutive_failures: number;
  details?: Record<string, unknown>;
}

export interface RuntimeMetrics {
  uptime_seconds: number;
  actions_total: number;
  actions_successful: number;
  actions_failed: number;
  transactions_total: number;
  transactions_completed: number;
  model_requests_total: number;
  model_latency_avg_ms: number;
  circuit_breakers_open: number;
}

export interface DeadLetterItem {
  item_id: string;
  source: string;
  payload: Record<string, unknown>;
  error_message: string;
  attempts: number;
  created_at: string;
}

/**
 * Standard Envelope for Internal Extension IPC
 */
export interface ExtensionMessage<T = unknown> {
  action: MessageAction | string;
  source: 'popup' | 'service-worker' | 'content-script' | 'external';
  target?: 'popup' | 'service-worker' | 'content-script' | 'external';
  payload?: T;
  requestId?: string;
  timestamp: string;
}

/**
 * Standard Response Envelope
 */
export interface ExtensionResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: string;
}

export interface IBrowserBridge {
  connect(endpoint?: string): Promise<boolean>;
  disconnect(): Promise<void>;
  getState(): BridgeConnectionState;
  isAuthenticated(): boolean;
  sendRequest<TReq, TRes>(action: string, payload: TReq, timeoutMs?: number): Promise<TRes>;
  sendResponse<TRes>(messageId: string, action: string, success: boolean, payload: TRes, error?: { code: string; message: string }): Promise<void>;
  sendEvent<TEvent>(action: string, payload: TEvent): void;
}

export interface IHeartbeatService {
  start(intervalMs: number): void;
  stop(): void;
  ping(): Promise<boolean>;
}

export interface ActionEngine {
  executeAction(actionType: string, params: Record<string, unknown>): Promise<boolean>;
}

export interface VerificationEngine {
  verifyPostCondition(expectedState: unknown, observedState: unknown): boolean;
}
