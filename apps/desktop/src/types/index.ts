export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  archived: boolean;
  messages?: Message[];
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  model?: string;
  metadata_json?: string;
}

export interface Note {
  id: string;
  file_path: string;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
  source: string;
  tags: string[];
}

export interface MemoryItem {
  id: string;
  source_type: string;
  source_id?: string;
  content: string;
  memory_tier: 'CORE' | 'RECALL' | 'ARCHIVAL';
  created_at: string;
  updated_at: string;
  metadata_json?: string;
}

export interface ComponentStatus {
  name: string;
  status: string;
  details?: string;
}

export interface SystemStatus {
  app_name: string;
  app_version: string;
  backend: ComponentStatus;
  database: ComponentStatus;
  ollama: ComponentStatus;
  model: ComponentStatus;
  memory: ComponentStatus;
  notes: ComponentStatus;
  privacy_gate?: ComponentStatus;
  secret_store?: ComponentStatus;
  audit_log?: ComponentStatus;
  tool_execution?: ComponentStatus;
}

export interface AppSettings {
  ollama_base_url: string;
  ollama_model: string;
  database_path: string;
  notes_path: string;
  memory_path: string;
  claude_code_configured?: boolean;
  claude_code_last_verified?: string | null;
  custom_settings: Record<string, string>;
}

export interface SecurityAuditEvent {
  id: string;
  timestamp: string;
  event_type: string;
  actor: string;
  action: string;
  resource?: string;
  decision: string;
  reason?: string;
}

export interface ToolDefinition {
  name: string;
  description: string;
  permission_level: 'READ' | 'WRITE' | 'EXTERNAL_ACTION' | 'DESTRUCTIVE';
  autonomy_tier: 'TIER_1' | 'TIER_2' | 'TIER_3';
  requires_confirmation: boolean;
  accesses_private_data: boolean;
  causes_side_effects: boolean;
}

export interface ConfirmationRequest {
  id: string;
  tool_name: string;
  action_summary: string;
  affected_resource: string;
  risk_level: string;
  parameters: Record<string, any>;
  created_at: string;
  approved?: boolean;
}

// 5C Executive Intelligence Types
export type ExecutiveRoleType = 'CEO' | 'COO' | 'CFO' | 'CMO' | 'CTO';

export interface RoleMetadata {
  role: ExecutiveRoleType;
  title: string;
  focus_areas: string[];
  core_questions: string[];
  evidence_criteria: string;
  memory_priorities: string[];
}

export interface ExecutiveResponse {
  role: ExecutiveRoleType;
  summary: string;
  key_findings: string[];
  assumptions: string[];
  risks: string[];
  recommendations: string[];
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  confidence_reason?: string;
  missing_information: string[];
}

export interface SynthesisResponse {
  question: string;
  summary: string;
  agreements: string[];
  conflicts: string[];
  critical_risks: string[];
  missing_information: string[];
  final_recommendation: string;
  next_actions: string[];
  executive_assessments: Record<ExecutiveRoleType, ExecutiveResponse>;
}

export interface DecisionInputItem {
  id: string;
  role: ExecutiveRoleType;
  summary: string;
  key_findings: string[];
  assumptions: string[];
  risks: string[];
  recommendations: string[];
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  missing_information: string[];
}

export interface DecisionResponse {
  id: string;
  title: string;
  question: string;
  status: 'OPEN' | 'DECIDED' | 'DEFERRED' | 'REJECTED' | 'REVISIT';
  final_recommendation?: string;
  reasoning_summary?: string;
  agreements: string[];
  conflicts: string[];
  critical_risks: string[];
  next_actions: string[];
  executive_inputs: DecisionInputItem[];
  created_at: string;
  updated_at: string;
}

// Phase 4 Developer Intelligence Types
export interface Workspace {
  id: string;
  name: string;
  root_path: string;
  project_type?: string;
  language?: string;
  framework?: string;
  package_manager?: string;
  is_git: boolean;
  git_branch?: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectTreeNode {
  name: string;
  path: string;
  is_dir: boolean;
  size?: number;
  is_sensitive: boolean;
  children?: ProjectTreeNode[];
}

export interface FileContent {
  path: string;
  size: number;
  content: string;
  is_truncated: boolean;
  is_binary: boolean;
}

export interface SearchResultItem {
  file_path: string;
  line_number: number;
  line_content: string;
}

export interface GitStatus {
  branch: string;
  is_clean: boolean;
  modified: string[];
  staged: string[];
  untracked: string[];
}

export interface GitDiff {
  diff: string;
  files_changed: string[];
}

export interface CommandExecution {
  command: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  is_truncated: boolean;
  execution_time_ms: number;
}

export interface CodeChangeProposal {
  id: string;
  workspace_id: string;
  title: string;
  reason: string;
  risk_level: string;
  diff_content: string;
  files: string[];
  status: 'PROPOSED' | 'APPROVED' | 'REJECTED' | 'APPLIED' | 'ROLLED_BACK' | 'FAILED';
  backup_path?: string;
  created_at: string;
  updated_at: string;
}

// Phase 5 Agent Runtime Types
export type AgentTaskStatus =
  | 'CREATED'
  | 'PLANNING'
  | 'AWAITING_APPROVAL'
  | 'RUNNING'
  | 'PAUSED'
  | 'VALIDATING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'EXPIRED';

export type AgentStepStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'AWAITING_APPROVAL'
  | 'COMPLETED'
  | 'FAILED'
  | 'SKIPPED';

export interface AgentStep {
  id: string;
  task_id: string;
  sequence: number;
  objective: string;
  action_type: string;
  tool_name: string;
  arguments: Record<string, any>;
  status: AgentStepStatus;
  risk_level: string;
  approval_required: boolean;
  approval_id?: string;
  started_at?: string;
  completed_at?: string;
  result?: string;
  error?: string;
}

export interface AgentTask {
  id: string;
  workspace_id?: string;
  user_goal: string;
  status: AgentTaskStatus;
  risk_level: string;
  current_step: number;
  max_steps: number;
  steps_completed: number;
  retry_count: number;
  max_retries: number;
  requires_approval: boolean;
  result?: string;
  failure_reason?: string;
  steps: AgentStep[];
  created_at: string;
  updated_at: string;
}

// Phase 6 Computer Use Types
export type ComputerPrivacyMode = 'PRIVATE' | 'LOCAL_ONLY' | 'CLOUD_ALLOWED' | 'PAUSED';

export interface ScreenshotCapture {
  id: string;
  timestamp: string;
  width: number;
  height: number;
  base64_image: string;
  source: string;
  application?: string;
  window_title?: string;
}

export interface UIElement {
  type: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
}

export interface VisionAnalysis {
  application?: string;
  description: string;
  elements: UIElement[];
  suggested_actions: string[];
  is_dialog_present: boolean;
}

export interface ApplicationContext {
  application: string;
  bundle_id?: string;
  window_title?: string;
  window_bounds?: Record<string, number>;
  is_active: boolean;
}

export interface ComputerStatus {
  computer_control_enabled: boolean;
  screen_recording_permission: string;
  accessibility_permission: string;
  privacy_mode: ComputerPrivacyMode;
  active_session?: string;
}

// Phase 7 Communication Types
export type ProviderType = 'whatsapp' | 'telegram' | 'email' | 'mock';

export interface CommunicationMessage {
  id: string;
  provider: ProviderType;
  conversation_id: string;
  sender: string;
  recipient: string;
  text: string;
  timestamp: string;
  is_read: boolean;
  direction: 'INCOMING' | 'OUTGOING';
  priority: 'URGENT' | 'IMPORTANT' | 'NORMAL' | 'LOW_VALUE' | 'NOISE';
}

export interface CommunicationConversation {
  id: string;
  provider: ProviderType;
  title: string;
  participants: string[];
  last_message_at: string;
  unread_count: number;
  is_muted: boolean;
  is_archived: boolean;
  recent_messages: CommunicationMessage[];
}

export interface CommunicationProviderStatus {
  provider: ProviderType;
  connected: boolean;
  status: string;
  can_read: boolean;
  can_send: boolean;
  can_search: boolean;
}

export interface ReplyOption {
  style: string;
  reply_text: string;
}

export interface ReplySuggestion {
  conversation_id: string;
  options: ReplyOption[];
}

export interface ConversationSummary {
  conversation_id: string;
  summary: string;
  important_points: string[];
  open_questions: string[];
  action_items: string[];
  confidence: string;
}

export interface SendMessageResponse {
  id: string;
  provider: ProviderType;
  conversation_id: string;
  recipient: string;
  status: string;
  message_hash: string;
}
