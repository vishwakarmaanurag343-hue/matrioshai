import { apiRequest } from "./client";
import type { NotepadAIResponse, Intent } from "../../features/notepad/types";

/**
 * Frontend Notepad API client.
 *
 * The base /notepad/ai endpoint goes through the EXISTING call_llm_structured
 * provider chain on the backend. No new LLM gateway is created here.
 *
 * Slice 1.1 adds:
 *   - explicit labeled context fields on /notepad/ai
 *   - sidecar JSON persistence endpoints at /notepad/notes/{id}/intents
 */
export const notepadApi = {
  executeAI: (params: {
    intent_id: string;
    note_id: string;
    verb: string;
    text: string;
    current_note_context?: string;
    intent?: string;
    requested_action?: string;
    context_block?: string;
    temperature?: number;
  }): Promise<NotepadAIResponse> =>
    apiRequest<NotepadAIResponse>("/notepad/ai", {
      method: "POST",
      body: JSON.stringify({
        intent_id: params.intent_id,
        note_id: params.note_id,
        verb: params.verb,
        text: params.text,
        current_note_context: params.current_note_context ?? "",
        intent: params.intent ?? "",
        requested_action: params.requested_action ?? "",
        context_block: params.context_block ?? "",
        temperature: params.temperature ?? 0.2,
      }),
    }),

  // --- sidecar persistence (Slice 1.1) ---

  loadIntents: (noteId: string): Promise<{ intents: Intent[]; malformed: boolean }> =>
    apiRequest<{ intents: Intent[]; malformed: boolean }>(
      `/notepad/notes/${encodeURIComponent(noteId)}/intents`
    ),

  saveIntents: (noteId: string, intents: Intent[]): Promise<{ saved: number }> =>
    apiRequest<{ saved: number }>(
      `/notepad/notes/${encodeURIComponent(noteId)}/intents`,
      {
        method: "PUT",
        body: JSON.stringify({ intents }),
      }
    ),
};
