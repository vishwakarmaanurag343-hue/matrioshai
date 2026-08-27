/**
 * HARD GUARD: Notepad Slice 1 must not import any Browser module.
 *
 * This test is structural. It greps the source for forbidden imports and
 * fails the build if any are present. The list of forbidden paths is
 * derived from the approved Phase 3 specification §13.
 */
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const NOTEPAD_DIR = path.resolve(__dirname, "..");

const FORBIDDEN_PATTERNS: RegExp[] = [
  /from\s+["'][^"']*features\/browser\/agent/,
  /from\s+["'][^"']*services\/browser/,
  /from\s+["'][^"']*tauri/,
  /require\([^)]*features\/browser\/agent/,
  /require\([^)]*services\/browser/,
  /@tauri-apps\/api/,
];

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "__tests__") continue; // this file is the guard itself
      walk(full, out);
    } else if (entry.isFile() && /\.(ts|tsx)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

describe("Notepad Browser-import guard (Slice 1)", () => {
  it("no file in the notepad feature imports any browser module", () => {
    const files = walk(NOTEPAD_DIR);
    const offenders: string[] = [];
    for (const f of files) {
      const text = fs.readFileSync(f, "utf8");
      for (const pat of FORBIDDEN_PATTERNS) {
        if (pat.test(text)) {
          offenders.push(`${f}: matched ${pat}`);
        }
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });
});
