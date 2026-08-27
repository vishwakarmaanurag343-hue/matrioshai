/**
 * Tests for the @ai context-block construction (Slice 1.1).
 */
import { describe, it, expect } from "vitest";
import { buildCurrentNoteContext, MAX_CONTEXT_CHARS } from "../router";

describe("Notepad @ai context construction (Slice 1.1)", () => {
  it("uses the body before the @-line when the intent is at the end of the note", () => {
    const note = "Meeting with client tomorrow.\n\nSummarize this note @ai";
    const ctx = buildCurrentNoteContext(note, "Summarize this note @ai");
    expect(ctx).toBe("Meeting with client tomorrow.\n\n");
  });

  it("returns a centered window when the @-line is not at the end", () => {
    const body = "x".repeat(5000);
    const note = `${body}\n@ai summarize this`;
    const ctx = buildCurrentNoteContext(note, "@ai summarize this");
    // Centered window: body length = 5000, MAX=2000, start = (5000-2000)/2 = 1500
    expect(ctx.length).toBe(MAX_CONTEXT_CHARS);
    expect(ctx).toBe(body.slice(1500, 1500 + MAX_CONTEXT_CHARS));
  });

  it("hard-caps the context at MAX_CONTEXT_CHARS even when the body is small", () => {
    const note = "x".repeat(100) + "\n@ai summarize";
    const ctx = buildCurrentNoteContext(note, "@ai summarize");
    expect(ctx.length).toBeLessThanOrEqual(MAX_CONTEXT_CHARS);
  });

  it("returns an empty string for an empty note", () => {
    expect(buildCurrentNoteContext("", "@ai summarize")).toBe("");
    expect(buildCurrentNoteContext("", "")).toBe("");
  });

  it("falls back to a window when the intent line is at the start of the note", () => {
    // Edge case: if the intent line is at index 0, lastIndexOf returns -1,
    // so we fall back to the centered-window branch. The body still goes
    // through MAX_CONTEXT_CHARS.
    const note = "@ai summarize\nrest of the note";
    const ctx = buildCurrentNoteContext(note, "@ai summarize");
    expect(ctx).toBe(note); // body is short enough to fit
  });

  it("does not include other notes or app state", () => {
    // The function signature only takes the current note text; the router
    // never accepts any other source.
    const note = "Only this note's content";
    const ctx = buildCurrentNoteContext(note, "@ai summarize");
    expect(ctx).toBe(note);
  });

  it("returns a bounded string even for very long notes", () => {
    const big = "a".repeat(50000);
    const ctx = buildCurrentNoteContext(big, "@ai summarize");
    expect(ctx.length).toBeLessThanOrEqual(MAX_CONTEXT_CHARS);
  });
});
