import { describe, it, expect, vi, beforeEach } from "vitest";
import { IntentRouter } from "../router";
import { notepadApi } from "../../../services/api/notepad";
import type { Intent, NotepadAIResponse } from "../types";

vi.mock("../../../services/api/notepad", () => ({
  notepadApi: {
    executeAI: vi.fn(),
  },
}));

function makeIntent(overrides: Partial<Intent> = {}): Intent {
  return {
    id: "i1",
    note_id: "n1",
    line_number: 1,
    raw_text: "Summarize this note @ai",
    type: "TASK",
    entities: { verb: "summarize" },
    capability_id: "ai",
    requested_action: "summarize",
    risk: "LOW",
    approval_required: false,
    confidence: 1.0,
    status: "DETECTED",
    task_id: null,
    confirmation_id: null,
    result: null,
    failure: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("Notepad IntentRouter (Slice 1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("routes @ai and transitions to COMPLETED with the result", async () => {
    const response: NotepadAIResponse = {
      summary: "A short summary.",
      suggestions: [],
      confidence: 0.9,
      model: "stealth/ox-alpha",
      provider: "openrouter",
    };
    (notepadApi.executeAI as any).mockResolvedValueOnce(response);

    const router = new IntentRouter();
    router.ingest(makeIntent());
    const terminal = await router.route("i1");

    expect(terminal.status).toBe("COMPLETED");
    expect(terminal.result).toEqual(response);
    expect(terminal.failure).toBeNull();
    expect(notepadApi.executeAI).toHaveBeenCalledOnce();
  });

  it("marks @ai as FAILED when the provider returns an error", async () => {
    (notepadApi.executeAI as any).mockRejectedValueOnce(
      new Error(JSON.stringify({ detail: { category: "SCHEMA_VIOLATION", message: "bad" } }))
    );

    const router = new IntentRouter();
    router.ingest(makeIntent());
    const terminal = await router.route("i1");

    expect(terminal.status).toBe("FAILED");
    expect(terminal.failure).not.toBeNull();
    expect(terminal.failure!.category).toBe("SCHEMA_VIOLATION");
  });

  it("marks @browser as DEFERRED and never calls executeAI", async () => {
    const router = new IntentRouter();
    router.ingest(
      makeIntent({
        id: "b1",
        capability_id: "browser",
        requested_action: "",
        risk: "MEDIUM",
        approval_required: false,
        confidence: 0,
        status: "DEFERRED",
      })
    );
    const terminal = await router.route("b1");
    expect(terminal.status).toBe("DEFERRED");
    expect(terminal.result).toBeNull();
    expect(notepadApi.executeAI).not.toHaveBeenCalled();
  });

  it("marks unknown capability as FAILED with UNKNOWN_INTENT", async () => {
    const router = new IntentRouter();
    router.ingest(
      makeIntent({ id: "u1", capability_id: "gmail", status: "DETECTED" })
    );
    const terminal = await router.route("u1");
    expect(terminal.status).toBe("FAILED");
    expect(terminal.failure?.category).toBe("UNKNOWN_INTENT");
    expect(notepadApi.executeAI).not.toHaveBeenCalled();
  });

  it("emits listener updates for each status transition", async () => {
    (notepadApi.executeAI as any).mockResolvedValueOnce({
      summary: "ok",
      suggestions: [],
      confidence: 0.8,
      model: "x",
      provider: "y",
    });
    const router = new IntentRouter();
    const seen: string[] = [];
    router.subscribe((i) => seen.push(i.status));
    router.ingest(makeIntent());
    await router.route("i1");
    expect(seen).toEqual(expect.arrayContaining(["DETECTED", "ROUTED", "RUNNING", "COMPLETED"]));
  });
});
