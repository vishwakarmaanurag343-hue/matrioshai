import { describe, it, expect, beforeEach } from "vitest";
import { BrowserAgentHarness } from "../agentHarness";
import { PageModel } from "../perception/pageModel";

describe("Phase 8E — Human Takeover & Session Recovery Suite", () => {
  let harness: BrowserAgentHarness;

  beforeEach(() => {
    harness = BrowserAgentHarness.getInstance();
    harness.stop();
  });

  it("1. takeover trigger and checkpoint creation", () => {
    // Start task mock
    void harness.executeGoal("Book flight ticket", "tab_1");
    expect(["PLANNING", "OBSERVING"]).toContain(harness.getState());

    // Manually trigger checkpoint creation for auth takeover
    const checkpoint = harness.createCheckpoint(
      "tab_1",
      "https://example.com/login",
      "Login Page",
      "CAPTCHA detected — human verification required.",
      "captcha"
    );

    expect(checkpoint).not.toBeNull();
    expect(checkpoint?.checkpointId).toMatch(/^chk_/);
    expect(checkpoint?.tabId).toBe("tab_1");
    expect(checkpoint?.takeoverKind).toBe("captcha");
    expect(checkpoint?.url).toBe("https://example.com/login");
    expect(harness.getActiveCheckpoint()?.checkpointId).toBe(checkpoint?.checkpointId);
  });

  it("2. safe pause stops autonomous action dispatch", () => {
    void harness.executeGoal("Test pause task", "tab_1");
    harness.pause();

    expect(harness.getState()).toBe("PAUSED");
    const chk = harness.getActiveCheckpoint();
    expect(chk).not.toBeNull();
    expect(chk?.takeoverKind).toBe("user_request");
  });

  it("3. sensitive data redaction in action history checkpoint", () => {
    void harness.executeGoal("Submit sensitive form", "tab_1");
    (harness as any).history.push({
      iteration: 1,
      action: "TYPE",
      target: "password_input",
      value: "super_secret_password_123",
      sensitive: true,
      dispatched: true,
      verified: true,
      note: "Typed password",
    });

    const chk = harness.createCheckpoint("tab_1", "https://example.com/auth", "Auth", "Password input", "login");
    expect(chk).not.toBeNull();
    const typedStep = chk?.actionHistory.find((h) => h.action === "TYPE");
    expect(typedStep?.value).toBe("[REDACTED]");
  });

  it("4. fresh perception before resume & target re-resolution", async () => {
    void harness.executeGoal("Resume task", "tab_1");
    harness.createCheckpoint("tab_1", "https://example.com/cart", "Cart", "User verification", "login");

    const freshModel: PageModel = {
      url: "https://example.com/cart/success",
      title: "Cart Success",
      sections: ["Order Confirmed"],
      links: [],
      buttons: [],
      inputs: [],
      selects: [],
      searchResults: [],
      advertisements: [],
      peopleAlsoAsk: [],
      videos: [],
      formsCount: 0,
      tablesCount: 0,
      timestamp: new Date().toISOString(),
    };

    const resumed = await harness.validateAndResumeFromCheckpoint("tab_1", freshModel);
    expect(resumed).toBe(true);
    expect(harness.getState()).toBe("OBSERVING");
  });

  it("5. stale checkpoint rejection on invalid url or empty tab state", async () => {
    void harness.executeGoal("Stale task", "tab_1");
    harness.createCheckpoint("tab_1", "https://example.com/cart", "Cart", "User verification", "login");

    const emptyModel: PageModel = {
      url: "",
      title: "",
      sections: [],
      links: [],
      buttons: [],
      inputs: [],
      selects: [],
      searchResults: [],
      advertisements: [],
      peopleAlsoAsk: [],
      videos: [],
      formsCount: 0,
      tablesCount: 0,
      timestamp: new Date().toISOString(),
    };

    const resumed = await harness.validateAndResumeFromCheckpoint("tab_1", emptyModel);
    expect(resumed).toBe(false);
  });
});
