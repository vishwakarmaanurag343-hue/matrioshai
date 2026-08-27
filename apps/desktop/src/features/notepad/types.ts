/**
 * Frontend types for the Notepad capability layer (Slice 1).
 * Mirrors apps/backend/app/notepad/schemas.py.
 */

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export type IntentType =
  | "NOTE"
  | "TODO"
  | "TASK"
  | "COMMAND"
  | "RESEARCH_REQUEST"
  | "DRAFT_REQUEST"
  | "AUTOMATION_REQUEST"
  | "EXTERNAL_ACTION"
  | "MULTI_ACTION_WORKFLOW";

export type IntentStatus =
  | "DETECTED"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "SKIPPED"
  | "ROUTED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "DEFERRED";

export interface Intent {
  id: string;
  note_id: string;
  line_number: number;
  raw_text: string;
  type: IntentType;
  entities: Record<string, string>;
  capability_id: string | null;
  requested_action: string;
  risk: RiskLevel;
  approval_required: boolean;
  confidence: number;
  status: IntentStatus;
  task_id: string | null;
  confirmation_id: string | null;
  result: NotepadAIResponse | null;
  failure: { category: string; message: string } | null;
  created_at: string;
  updated_at: string;
}

export interface NotepadAIResponse {
  summary: string;
  suggestions: string[];
  confidence: number;
  model: string;
  provider: string;
}

export interface NotepadAIError {
  category:
    | "PROVIDER_UNAVAILABLE"
    | "SCHEMA_VIOLATION"
    | "TIMEOUT"
    | "INTERNAL"
    | "UNKNOWN_INTENT"
    | "DEFERRED_CAPABILITY";
  message: string;
  trace_id?: string;
}
