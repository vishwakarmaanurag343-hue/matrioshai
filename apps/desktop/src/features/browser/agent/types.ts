export type ActionRiskLevel = "ReadOnly" | "Low" | "Medium" | "High" | "Critical";

export interface RobustElement {
  id: string;
  name?: string;
  role: string;
  tag: string;
  text: string;
  ariaLabel?: string;
  placeholder?: string;
  href?: string;
  value?: string; // live input value (carried through PageModelBuilder for effect verification)
  inputType?: string;
  disabled?: boolean;
  selector: string;
  selectorHints?: string[];
  sensitive?: boolean;
  boundingBox?: { x: number; y: number; width: number; height: number };
  visible?: boolean;
  enabled?: boolean;
  interactive?: boolean;
  confidence?: number;
}

export interface PerceptionSnapshot {
  url: string;
  title: string;
  headings: string[];
  text_blocks: string[];
  interactive_elements: RobustElement[];
  forms_count: number;
  tables_count: number;
  links_count: number;
  timestamp: string;
  observation_status?: string;
  observation_failed?: boolean;
}

export type StepStatus = "pending" | "running" | "completed" | "failed" | "waiting_approval" | "skipped";

/**
 * SINGLE SOURCE OF TRUTH for the browser-agent TASK lifecycle (Phase 1
 * consolidation). Distinct concepts that must NOT be merged into this union:
 *   - HarnessState  (harness FSM phase, agentHarness.ts)
 *   - StepStatus    (individual planned-step lifecycle, above)
 *   - the GENERAL agent subsystem's AgentTaskStatus (src/types/index.ts)
 * Terminal semantics: completed | failed | cancelled | waiting_user.
 */
export type BrowserAgentTaskStatus =
  | "running"
  | "paused"
  | "waiting_review"
  | "waiting_user"
  | "completed"
  | "failed"
  | "cancelled";

export interface PlanStep {
  id: string;
  goal: string;
  tool: string; // "click" | "navigate" | "type" | "scroll" | "wait" | "extract" | "select" | "press_key"
  target?: string;
  value?: string;
  expectedOutcome?: string;
  status: StepStatus;
  riskLevel: ActionRiskLevel;
  resultMessage?: string;
}

export interface AgentTask {
  taskId: string;
  userGoal: string;
  mode: "general" | "research" | "comparison" | "travel";
  steps: PlanStep[];
  currentStepIndex: number;
  status: BrowserAgentTaskStatus;
  createdAt: string;
  updatedAt: string;
  visitedUrls: string[];
  extractedFacts: string[];
  sources: { title: string; url: string; snippet?: string }[];
  evidence?: EvidenceItem[];          // goal-predicate evidence for completion
  failedStrategies?: string[];        // exhausted strategy signatures
  comparisonMatrix?: {
    headers: string[];
    rows: Record<string, string>[];
  };
  itinerary?: {
    day: number;
    title: string;
    activities: string[];
    costEstimate?: string;
  }[];
}

export interface ActionVerificationResult {
  success: boolean;
  changed: boolean;
  message: string;
  beforeUrl: string;
  afterUrl: string;
  domMutated: boolean;
}

// ===========================================================================
// UNIFIED AGENT RUNTIME — mirrors app/agent/runtime/browser_reasoning.py
// (single source of truth lives in the backend; keep both in sync)
// ===========================================================================

export type AgentActionType =
  | "NAVIGATE" | "CLICK" | "TYPE" | "SELECT" | "CHECK" | "UNCHECK" | "SCROLL"
  | "PRESS_KEY" | "SUBMIT" | "GO_BACK" | "GO_FORWARD" | "OPEN_TAB" | "SWITCH_TAB"
  | "CLOSE_TAB" | "WAIT" | "OBSERVE" | "EXTRACT"
  | "ANSWER"          // respond to the user in plain text (question answered)
  | "ASK_USER"        // need missing information from the user
  | "WAIT_FOR_USER"   // user must take over the browser (login / captcha / otp)
  | "DONE"            // goal achieved — summary in value
  | "FAIL";           // genuinely unrecoverable — explanation in value

export type ExpectedEffectType =
  | "none" | "url_changed" | "url_contains" | "value_changed"
  | "text_present" | "element_appeared" | "dom_mutated" | "tab_opened";

export interface ExpectedEffect {
  type: ExpectedEffectType;
  target?: string | null; // el_N for value_changed, substring for url_contains/text_present
  value?: string | null;  // expected value / substring
}

export interface AgentDecision {
  action: AgentActionType;
  target?: string | null;
  value?: string | null;
  reason: string;
  expected_effect: ExpectedEffect;
  requires_approval: boolean;
  message?: string | null;
  evidence?: EvidenceItem[] | null;   // required for DONE on research goals
  progress_estimate?: number | null;  // honest self-reported 0-100
  subgoal?: string | null;            // Phase 3: next active sub-objective
  confidence?: number | null;         // Phase 3: model self-reported confidence 0.0-1.0
}

export interface StepRecord {
  iteration: number;
  action: string;
  target?: string | null;
  value?: string | null;
  dispatched: boolean;
  verified: boolean;
  url_before?: string | null;
  url_after?: string | null;
  note: string;
  tab_id?: string | null;          // which tab world-state this step touched
  strategy?: string | null;        // e.g. "dom-extract@product-page"
  failure?: ActionFailure | null;  // structured diagnosis when not verified
}

export interface TabSummary {
  tab_id: string;
  url: string;
  title: string;
  active: boolean;
}

// ===========================================================================
// PERSISTENT WORKER: failure taxonomy, evidence, events, perception levels
// ===========================================================================

export type FailureCategory =
  | "TARGET_NOT_FOUND" | "STALE_ELEMENT" | "OBSERVATION_EMPTY" | "EXTRACTION_FAILED"
  | "NAVIGATION_FAILED" | "VERIFICATION_FAILED" | "AUTH_REQUIRED"
  | "CAPTCHA" | "BLOCKED" | "PERMISSION_REQUIRED" | "TIMEOUT" | "UNKNOWN";

export interface ActionFailure {
  category: FailureCategory;
  action: string;
  target?: string | null;
  page: string;          // page title / role description
  url: string;
  attempt: number;       // 1-based attempt count for this action+target
  evidence: string;      // what was actually observed (truthful)
}

export type EvidenceType = "OBSERVED" | "USER_PROVIDED" | "INFERRED" | "DERIVED";
export type EvidenceValidity = "CURRENT" | "STALE" | "INVALIDATED" | "CONTRADICTED";

export interface EvidenceItem {
  id?: string;               // Phase 3: deterministic id e.g. "ev_17877912"
  label: string;             // e.g. "official price", "competitor price"
  value: string;             // e.g. "$1,299.00"
  normalized_value?: string; // Phase 4: e.g. "1299.00 USD"
  source: string;            // URL the evidence came from
  tab_id?: string;           // Phase 3: origin tab id
  timestamp?: string;        // Phase 3: ISO timestamp
  confidence?: number;       // Phase 3: 0.0-1.0
  evidence_type?: EvidenceType; // Phase 4: OBSERVED | USER_PROVIDED | INFERRED | DERIVED
  validity?: EvidenceValidity;  // Phase 4: CURRENT | STALE | INVALIDATED | CONTRADICTED
}

/** Universal perception escalation ladder (no site-specific logic). */
export type PerceptionLevel =
  | "dom"                 // L1: semantic DOM extraction (inspect_page)
  | "semantic-tree"       // L2: accessibility / semantic page command
  | "rendered-text"       // L3/L4: rendered text + geometry via debug eval
  | "visual"              // L5: screenshot perception (if supported)
  | "alternative-route";  // L6: different legitimate discovery route

export interface TabWorldState {
  tab_id: string;
  url: string;
  title: string;
  observation_level: PerceptionLevel;
  version: number;        // bumped every fresh observation of this tab
  extracted_facts?: EvidenceItem[]; // Phase 3: facts remembered from this specific tab
}

export type AgentEventType =
  | "TASK_STARTED" | "OBSERVING" | "OBSERVED" | "PLANNING"
  | "ACTION_PROPOSED" | "ACTION_EXECUTING" | "ACTION_VERIFIED" | "ACTION_FAILED"
  | "RECOVERY_STARTED" | "STRATEGY_CHANGED" | "WAITING_FOR_USER"
  | "USER_INPUT_REQUIRED" | "CHECKPOINT" | "READY_FOR_REVIEW"
  | "TASK_COMPLETED" | "TASK_FAILED" | "TASK_CANCELLED"
  | "HUMAN_TAKEOVER_REQUIRED" | "HUMAN_TAKEOVER_PAUSED" | "SESSION_CHECKPOINT_CREATED"
  | "HUMAN_TAKEOVER_RESUME_REQUESTED" | "SESSION_CHECKPOINT_VALIDATED"
  | "SESSION_CHECKPOINT_REJECTED" | "HUMAN_TAKEOVER_RESUMED"
  | "SECURITY_INJECTION_REDACTED" | "SECURITY_POLICY_BLOCKED" | "SECURITY_KERNEL_VERIFIED";

export interface AgentEvent {
  id: string;
  task_id: string;
  timestamp: string;
  type: AgentEventType;
  summary: string;
  status: "info" | "success" | "warn" | "error";
  evidence?: string;
}

export interface ReasoningRequest {
  goal: string;
  url: string;
  title: string;
  ready_state?: string;
  headings: string[];
  text_blocks: string[];
  interactive_elements: Record<string, any>[];
  tabs: TabSummary[];
  history: StepRecord[];
  constraints: string[];
  failed_strategies?: string[];      // signatures of exhausted strategies
  observation_level?: PerceptionLevel;
  subgoal?: string;                    // Phase 3: active sub-objective
  accumulated_evidence?: EvidenceItem[]; // Phase 3: facts verified across steps/tabs
}

export interface SessionCheckpoint {
  checkpointId: string;
  taskId: string;
  userGoal: string;
  tabId: string;
  url: string;
  title: string;
  subgoal?: string | null;
  takeoverReason: string;
  takeoverKind: "captcha" | "login" | "consent" | "ambiguous" | "user_request" | "unknown";
  createdAt: string;
  actionHistory: StepRecord[];
  evidence: EvidenceItem[];
  failedStrategies: string[];
  actionAttempts: Record<string, number>;
  strategyFailures: Record<string, number>;
  stepIndex: number;
  version: number;
}
