import { describe, it, expect } from "vitest";
import { CAPABILITIES, getCapability, isExecutable } from "../capabilities";

describe("Notepad capability resolution (Slice 1)", () => {
  it("registers @ai as enabled and executable", () => {
    const cap = getCapability("ai");
    expect(cap).not.toBeNull();
    expect(cap!.enabled).toBe(true);
    expect(isExecutable("ai")).toBe(true);
  });

  it("registers @browser as DISABLED (never executes in slice 1)", () => {
    const cap = getCapability("browser");
    expect(cap).not.toBeNull();
    expect(cap!.enabled).toBe(false);
    expect(isExecutable("browser")).toBe(false);
  });

  it("returns null for unknown capabilities", () => {
    expect(getCapability("gmail")).toBeNull();
    expect(getCapability("calendar")).toBeNull();
    expect(getCapability("unknown")).toBeNull();
    expect(isExecutable("gmail")).toBe(false);
  });

  it("the registry contains exactly two entries in slice 1", () => {
    expect(Object.keys(CAPABILITIES).sort()).toEqual(["ai", "browser"]);
  });

  it("@browser has a deferral message", () => {
    const cap = getCapability("browser");
    expect(cap!.deferralMessage).toContain("not enabled");
  });
});
