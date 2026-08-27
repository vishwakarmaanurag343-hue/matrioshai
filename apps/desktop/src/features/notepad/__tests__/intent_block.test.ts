import { describe, it, expect } from "vitest";
import { splitBodyAndIntents, writeNoteWithIntents, serializeIntentBlock } from "../intentBlock";

describe("Notepad intent block round-trip", () => {
  it("returns the body unchanged when there is no block", () => {
    const md = "# Title\n\nSome text\n";
    const r = splitBodyAndIntents(md);
    expect(r.cleanBody).toBe(md);
    expect(r.intents).toEqual([]);
    expect(r.hadMalformedBlock).toBe(false);
  });

  it("extracts a valid block and returns the body without it", () => {
    const md = "# Title\n\nSome text\n\n<!-- matrioshai:intents v1\n[{\"id\":\"a\",\"status\":\"COMPLETED\"}]\n-->\n";
    const r = splitBodyAndIntents(md);
    expect(r.intents).toHaveLength(1);
    expect(r.intents[0].id).toBe("a");
    expect(r.cleanBody).not.toContain("matrioshai:intents");
  });

  it("treats a malformed block as a no-op and still returns the body", () => {
    const md = "# Title\n\nSome text\n\n<!-- matrioshai:intents v1\n[not-json]\n-->\n";
    const r = splitBodyAndIntents(md);
    expect(r.intents).toEqual([]);
    expect(r.hadMalformedBlock).toBe(true);
    expect(r.cleanBody).toContain("Some text");
  });

  it("round-trip: a body with no intents is byte-identical", () => {
    const md = "Meeting notes for the client.\n";
    const out = writeNoteWithIntents(md, []);
    expect(out).toBe(md);
  });

  it("round-trip: a body with intents preserves the body and re-emits the block", () => {
    const md = "Some text\n";
    const intents = [{ id: "x", status: "COMPLETED", result: { summary: "ok" } }];
    const out = writeNoteWithIntents(md, intents);
    expect(out).toContain("Some text");
    const r = splitBodyAndIntents(out);
    expect(r.intents).toHaveLength(1);
    expect(r.cleanBody).toBe("Some text");
  });

  it("serializing an empty list returns an empty string (no block emitted)", () => {
    expect(serializeIntentBlock([])).toBe("");
  });
});
