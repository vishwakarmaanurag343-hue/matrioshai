/**
 * Deterministic, local-only line classifier for Notepad Intents.
 *
 * No LLM is used for detection. This is the single entry point that decides
 * whether a line of note text becomes a Notepad Intent.
 *
 * Rules (slice 1):
 *   - Plain text (no @, no TODO prefix)         -> NOTE
 *   - # TODO / - TODO / TODO / [ ] / [x]        -> TODO
 *   - /word                                      -> COMMAND (reserved; no-op in slice 1)
 *   - @<token> ... with token = a-z[a-z0-9_-]{1,32}
 *       - if token is a registered capability:
 *           - enabled      -> TASK (or specialized type by verb)
 *           - disabled     -> TASK with status=DEFERRED
 *       - else              -> NOTE (silently treated as plain text)
 */

import { getCapability, isExecutable } from "./capabilities";
import type { RiskLevel, Capability } from "./capabilities";

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

export interface DetectedIntent {
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
  created_at: string;
  updated_at: string;
  result: null;
  failure: null;
  task_id: null;
  confirmation_id: null;
}

function atTokenMatch(line: string): RegExpMatchArray | null {
  // Anchor to start-of-line first so leading @ai works.
  const start = line.match(/^@([a-z][a-z0-9_-]{1,32})\b(.*)$/);
  if (start) return start;
  // Otherwise look for an @-token preceded by whitespace.
  const m = line.match(/(?<=\s)@([a-z][a-z0-9_-]{1,32})\b(.*)$/);
  return m;
}
const TODO_PATTERN = /^\s*(?:[-*]\s*)?(?:#\s*)?(?:\[(?:\s|x)?\]\s*)?TODO\b[:\s]*(.*)$/i;
const COMMAND_PATTERN = /^\/([a-z][a-z0-9_-]{0,32})\b(.*)$/;

function uuid(): string {
  // Simple, dependency-free UUIDv4-ish. Sufficient for client-side intent ids.
  const rnd = () => Math.floor(Math.random() * 0x10000).toString(16).padStart(4, "0");
  return `${rnd()}${rnd()}-${rnd()}-4${rnd().slice(1)}-${(8 + Math.floor(Math.random() * 4)).toString(16)}${rnd().slice(1)}-${rnd()}${rnd()}${rnd()}`;
}

function nowIso(): string {
  return new Date().toISOString();
}

function inferVerbForCapability(cap: Capability, rest: string): string {
  // The first word after @cap is treated as the verb when supported,
  // otherwise "summarize" is the safe default for @ai.
  const firstWord = (rest.trim().split(/\s+/)[0] ?? "").toLowerCase();
  if (cap.supportedActions.includes(firstWord)) {
    return firstWord;
  }
  return cap.supportedActions[0] ?? "";
}

function classifyRisk(capabilityId: string, verb: string, text: string): { risk: RiskLevel; approval: boolean } {
  const lower = (text || "").toLowerCase();
  const hasInjection =
    lower.includes("ignore previous") ||
    lower.includes("ignore all previous") ||
    lower.includes("system prompt") ||
    lower.includes("disregard the above");
  if (hasInjection) {
    return { risk: "HIGH", approval: true };
  }
  if (capabilityId === "ai") {
    if (verb === "research") return { risk: "MEDIUM", approval: true };
    if (verb === "summarize" || verb === "draft" || verb === "rewrite" || verb === "extract") {
      return { risk: "LOW", approval: false };
    }
    return { risk: "LOW", approval: false };
  }
  return { risk: "MEDIUM", approval: true };
}

function typeForVerb(capabilityId: string, verb: string): IntentType {
  if (capabilityId !== "ai") {
    return "EXTERNAL_ACTION";
  }
  switch (verb) {
    case "research":
      return "RESEARCH_REQUEST";
    case "draft":
      return "DRAFT_REQUEST";
    case "summarize":
    case "rewrite":
    case "extract":
      return "TASK";
    default:
      return "TASK";
  }
}

export function detectIntentsForLine(
  rawLine: string,
  lineNumber: number,
  noteId: string
): DetectedIntent | null {
  const trimmed = rawLine.replace(/\r$/, "");
  if (trimmed.trim().length === 0) return null;

  // TODO classification first (so a TODO line containing @ is still a TODO
  // only if it begins with TODO — the AT matcher below will catch @-first
  // lines and prefer them, per spec R10).
  const todoMatch = trimmed.match(TODO_PATTERN);
  if (todoMatch) {
    return {
      id: uuid(),
      note_id: noteId,
      line_number: lineNumber,
      raw_text: trimmed,
      type: "TODO",
      entities: { rest: todoMatch[1] ?? "" },
      capability_id: null,
      requested_action: "",
      risk: "LOW",
      approval_required: false,
      confidence: 1.0,
      status: "DETECTED",
      created_at: nowIso(),
      updated_at: nowIso(),
      result: null,
      failure: null,
      task_id: null,
      confirmation_id: null,
    };
  }

  // Command (reserved; safe no-op in slice 1).
  if (COMMAND_PATTERN.test(trimmed)) {
    return {
      id: uuid(),
      note_id: noteId,
      line_number: lineNumber,
      raw_text: trimmed,
      type: "COMMAND",
      entities: {},
      capability_id: null,
      requested_action: "",
      risk: "LOW",
      approval_required: false,
      confidence: 1.0,
      status: "SKIPPED",
      created_at: nowIso(),
      updated_at: nowIso(),
      result: null,
      failure: null,
      task_id: null,
      confirmation_id: null,
    };
  }

  // @-capability classification.
  const atMatch = atTokenMatch(trimmed);
  if (atMatch) {
    const token = atMatch[1].toLowerCase();
    const rest = atMatch[2] ?? "";
    const cap = getCapability(token);
    if (cap) {
      const verb = inferVerbForCapability(cap, rest);
      const { risk, approval } = classifyRisk(cap.id, verb, trimmed);
      const executable = isExecutable(cap.id);
      return {
        id: uuid(),
        note_id: noteId,
        line_number: lineNumber,
        raw_text: trimmed,
        type: typeForVerb(cap.id, verb),
        entities: { verb, rest: rest.trim() },
        capability_id: cap.id,
        requested_action: verb,
        risk,
        approval_required: approval,
        confidence: executable ? 1.0 : 0.0,
        status: executable ? "DETECTED" : "DEFERRED",
        created_at: nowIso(),
        updated_at: nowIso(),
        result: null,
        failure: null,
        task_id: null,
        confirmation_id: null,
      };
    }
    // Unknown @capability: fall through and treat as plain NOTE.
  }

  return null;
}

export function detectIntentsInNote(text: string, noteId: string): DetectedIntent[] {
  if (!text) return [];
  const lines = text.split("\n");
  const out: DetectedIntent[] = [];
  for (let i = 0; i < lines.length; i++) {
    const intent = detectIntentsForLine(lines[i], i + 1, noteId);
    if (intent) out.push(intent);
  }
  return out;
}
