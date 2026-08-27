import { describe, it, expect } from "vitest";
import { detectIntentsForLine } from "../intentParser";
import { getCapability } from "../capabilities";

describe("Notepad @browser deferred (Slice 1)", () => {
  it("@browser is recognized but never enters the executable path", () => {
    const cap = getCapability("browser");
    expect(cap).not.toBeNull();
    expect(cap!.enabled).toBe(false);
    expect(cap!.deferralMessage).toBeTruthy();
  });

  it("a @browser line produces an intent with status=DEFERRED", () => {
    const intent = detectIntentsForLine("Open example.com @browser", 1, "n1");
    expect(intent).not.toBeNull();
    expect(intent!.status).toBe("DEFERRED");
    expect(intent!.capability_id).toBe("browser");
  });
});
