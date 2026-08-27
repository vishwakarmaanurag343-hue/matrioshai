/**
 * Notepad intent router (Slice 1).
 *
 * Routes an Intent to its capability's execute() function. The router is the
 * single place where a capability can transition from DETECTED to ROUTED /
 * RUNNING / COMPLETED / FAILED / DEFERRED.
 *
 * Slice 1 invariants:
 *   - @ai       -> calls notepadApi.executeAI
 *   - @browser  -> marks status=DEFERRED, never executes
 *   - unknown   -> not routed (no Intent created upstream)
 *
 * No browser module is imported. No AgentTask is created for the simple
 * @ai summarize path. The router only writes to its own Intent map and
 * returns the updated Intent; persistence is the caller's job.
 */

import { notepadApi } from "../../services/api/notepad";
import { getCapability, isExecutable } from "./capabilities";
import type { Intent, NotepadAIResponse } from "./types";

export type RouterListener = (intent: Intent) => void;

/**
 * Maximum size, in characters, of the note-context excerpt that the
 * desktop Notepad will pass to the AI route. This is the *frontend* cap;
 * the backend independently caps the joined user message at 4000 chars
 * and the `current_note_context` field at 2000 chars.
 *
 * Slice 1.1 invariant: the context is derived ONLY from the current
 * note text and the intent's own raw_text. No other notes, no app
 * state, no secrets.
 */
export const MAX_CONTEXT_CHARS = 2000;

/**
 * Build the bounded, labeled `current_note_context` for a given note
 * and the user's @-intent line.
 *
 * Strategy:
 *   1. If the note is empty, return "".
 *   2. If the intent line is found at the end of the note (so the
 *      rest of the note is the body the user wrote), return the body
 *      verbatim (still capped at MAX_CONTEXT_CHARS).
 *   3. Otherwise, return a centered window of the body of length
 *      MAX_CONTEXT_CHARS. This keeps intent-recognition local without
 *      silently dropping earlier content.
 */
export function buildCurrentNoteContext(noteText: string, intentRaw: string): string {
  const safe = noteText ?? "";
  if (safe.length === 0) return "";

  // If the intent line appears at the end, the body is everything
  // before it. We strip the intent line itself but keep the body intact
  // (including its trailing newlines).
  if (intentRaw && safe.endsWith(intentRaw)) {
    const body = safe.slice(0, safe.length - intentRaw.length);
    return body.slice(0, MAX_CONTEXT_CHARS);
  }

  // Centered window of the whole note.
  if (safe.length <= MAX_CONTEXT_CHARS) return safe;
  const start = Math.max(0, Math.floor((safe.length - MAX_CONTEXT_CHARS) / 2));
  return safe.slice(start, start + MAX_CONTEXT_CHARS);
}

export class IntentRouter {
  private intents: Map<string, Intent> = new Map();
  private listeners: Set<RouterListener> = new Set();
  // The current note text is provided by the host (NotesView) on every change.
  // The router NEVER reads from anywhere else — there is no global state, no
  // memory of past notes, no app-state side channel.
  private currentNoteText: string = "";

  // --- subscription ---

  setCurrentNoteText(text: string): void {
    this.currentNoteText = text ?? "";
  }

  subscribe(listener: RouterListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(intent: Intent): void {
    for (const l of this.listeners) {
      try {
        l(intent);
      } catch {
        // ignore listener errors so a single bad subscriber doesn't break the router
      }
    }
  }

  // --- intent ingestion ---

  ingest(intent: Intent): void {
    this.intents.set(intent.id, intent);
    this.emit(intent);
  }

  replaceAll(intents: Intent[]): void {
    this.intents.clear();
    for (const i of intents) {
      this.intents.set(i.id, i);
    }
    for (const i of this.intents.values()) {
      this.emit(i);
    }
  }

  list(): Intent[] {
    return Array.from(this.intents.values()).sort((a, b) => a.line_number - b.line_number);
  }

  get(id: string): Intent | undefined {
    return this.intents.get(id);
  }

  // --- routing ---

  /**
   * Route an Intent. Returns a promise that resolves when the Intent reaches
   * a terminal status (COMPLETED, FAILED, DEFERRED, REJECTED, SKIPPED).
   */
  async route(intentId: string): Promise<Intent> {
    const intent = this.intents.get(intentId);
    if (!intent) {
      throw new Error(`Intent not found: ${intentId}`);
    }

    const cap = intent.capability_id ? getCapability(intent.capability_id) : null;
    if (!cap) {
      // Unknown capability; should not be routed. Mark failed safely.
      return this.terminate(intent, "FAILED", {
        failure: { category: "UNKNOWN_INTENT", message: "Unknown capability." },
      });
    }

    if (!isExecutable(cap.id)) {
      // Deferred capability (e.g. @browser). Never execute. Never import.
      return this.terminate(intent, "DEFERRED", {
        result: null,
        failure: null,
      });
    }

    if (cap.id === "ai") {
      return this.routeAI(intent);
    }

    return this.terminate(intent, "FAILED", {
      failure: { category: "UNKNOWN_INTENT", message: `No router for capability '${cap.id}'.` },
    });
  }

  private async routeAI(intent: Intent): Promise<Intent> {
    // Mark ROUTED -> RUNNING.
    this.update(intent.id, { status: "ROUTED" });
    this.update(intent.id, { status: "RUNNING" });

    // Build the bounded, labeled context for this call. The context is
    // derived ONLY from the current note text and the intent's own
    // raw_text. No other notes, no app state, no secrets. The
    // MAX_CONTEXT_CHARS=2000 cap is enforced inside buildCurrentNoteContext.
    const currentNoteContext = buildCurrentNoteContext(
      this.currentNoteText,
      intent.raw_text
    );

    try {
      const result: NotepadAIResponse = await notepadApi.executeAI({
        intent_id: intent.id,
        note_id: intent.note_id,
        verb: intent.requested_action || "summarize",
        text: intent.raw_text,
        current_note_context: currentNoteContext,
        intent: intent.raw_text,
        requested_action: intent.requested_action || "summarize",
        context_block: "", // legacy; empty
        temperature: 0.2,
      });
      return this.terminate(intent, "COMPLETED", { result, failure: null });
    } catch (e: any) {
      // The backend returns a structured error in e.message. Try to surface
      // the category; otherwise INTERNAL.
      let failure: { category: string; message: string } = {
        category: "INTERNAL",
        message: String(e?.message ?? "Unknown error"),
      };
      try {
        const parsed = JSON.parse(e?.message ?? "");
        if (parsed && parsed.detail && parsed.detail.category) {
          failure = { category: parsed.detail.category, message: parsed.detail.message ?? "" };
        }
      } catch {
        // not JSON; keep default
      }
      return this.terminate(intent, "FAILED", { failure });
    }
  }

  // --- helpers ---

  private update(id: string, patch: Partial<Intent>): Intent {
    const existing = this.intents.get(id);
    if (!existing) {
      throw new Error(`Intent not found: ${id}`);
    }
    const updated: Intent = {
      ...existing,
      ...patch,
      updated_at: new Date().toISOString(),
    };
    this.intents.set(id, updated);
    this.emit(updated);
    return updated;
  }

  private terminate(
    intent: Intent,
    status: Intent["status"],
    extra: { result?: NotepadAIResponse | null; failure?: { category: string; message: string } | null }
  ): Intent {
    return this.update(intent.id, {
      status,
      result: extra.result === undefined ? intent.result : extra.result,
      failure: extra.failure === undefined ? intent.failure : extra.failure,
    });
  }
}

export const intentRouter = new IntentRouter();
