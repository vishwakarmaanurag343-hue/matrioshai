/**
 * Security: Intent objects must not introduce secret-like fields.
 *
 * The Intent persists the user's raw_text verbatim (it is their note). This
 * test verifies that the Intent *schema* does not include credential-like
 * fields, and that no part of the detection/routing path synthesizes or
 * persists API keys, tokens, or secrets.
 */
import { describe, it, expect } from "vitest";
import { detectIntentsForLine } from "../intentParser";

const FORBIDDEN_KEYS = [
  "api_key",
  "apikey",
  "apiKey",
  "secret",
  "password",
  "token",
  "openrouter_api_key",
  "groq_api_key",
  "nvidia_api_key",
  "ollama_api_key",
];

describe("Notepad secrets guard (Slice 1)", () => {
  it("detected intents never introduce credential-like fields", () => {
    const lines = [
      "Summarize this @ai",
      "@ai draft an email",
      "Open example.com @browser",
      "- TODO: ship slice 1",
    ];
    for (const line of lines) {
      const intent = detectIntentsForLine(line, 1, "n1");
      if (!intent) continue;
      const keys = Object.keys(intent);
      for (const k of keys) {
        expect(FORBIDDEN_KEYS.includes(k), `Intent has forbidden key '${k}'`).toBe(false);
      }
    }
  });

  it("the canonical Intent surface (no runtime mutation) does not synthesize keys", () => {
    const intent = detectIntentsForLine("@ai summarize this", 1, "n1");
    expect(intent).not.toBeNull();
    // The detection path must never produce fields that look like credentials.
    const blob = JSON.stringify(intent);
    expect(blob).not.toMatch(/sk-or-v1-[A-Za-z0-9-]{20,}/);
    expect(blob).not.toMatch(/gsk_[A-Za-z0-9]{20,}/);
    expect(blob).not.toMatch(/nvapi-[A-Za-z0-9-]{20,}/);
  });
});
