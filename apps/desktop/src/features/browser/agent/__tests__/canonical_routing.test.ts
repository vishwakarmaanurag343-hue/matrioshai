import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { AgentTask } from "../types";

/**
 * PHASE 1 REGRESSION PIN — canonical entrypoint routing.
 *
 * BrowserTaskManager and BrowserAgentHarness are singletons; these tests load
 * them through vi.resetModules() so every case sees a fresh instance and can
 * never pollute (or be polluted by) the lifecycle suites.
 *
 * Pinned contract: EVERY user prompt enters exactly ONE execution runtime —
 *   BrowserTaskManager.startGoal() → BrowserAgentHarness.executeGoal()
 * and a waiting_user run continues the SAME task via provideUserResponse.
 */

function fakeTask(overrides: Partial<AgentTask> = {}): AgentTask {
  return {
    taskId: `goal_${Math.random().toString(36).slice(2, 8)}`,
    userGoal: "test goal",
    mode: "general",
    steps: [],
    currentStepIndex: 0,
    status: "running",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    visitedUrls: [],
    extractedFacts: [],
    sources: [],
    ...overrides,
  };
}

let mgrMod: typeof import("../state/browserTaskState");
let harnessMod: typeof import("../agentHarness");

beforeEach(async () => {
  vi.resetModules();
  mgrMod = await import("../state/browserTaskState");
  harnessMod = await import("../agentHarness");
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Canonical routing: startGoal → executeGoal (single execution path)", () => {
  it("routes every goal into harness.executeGoal with goal/tab/constraints intact", async () => {
    const manager = mgrMod.BrowserTaskManager.getInstance();
    const harness = harnessMod.BrowserAgentHarness.getInstance();
    const spy = vi.spyOn(harness, "executeGoal").mockResolvedValue(fakeTask());

    const goal = "Search Google for RTX 5090, open the first relevant result and tell me the price.";
    await manager.startGoal(goal, "tab_1", ["Goal given while viewing: https://www.google.com"]);

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith(goal, "tab_1", ["Goal given while viewing: https://www.google.com"]);
  });

  it("continues a waiting_user run on the SAME task instead of starting a competing goal", async () => {
    const manager = mgrMod.BrowserTaskManager.getInstance();
    const harness = harnessMod.BrowserAgentHarness.getInstance();

    let listener: ((task: AgentTask | null) => void) | undefined;
    vi.spyOn(harness, "subscribe").mockImplementation((l) => {
      listener = l as never;
      return () => {};
    });
    vi.spyOn(harness, "executeGoal").mockResolvedValue(fakeTask({ status: "waiting_user" }));
    const respondSpy = vi.spyOn(harness, "provideUserResponse").mockImplementation(() => {});

    await manager.startGoal("Compare three RTX 5090 prices across sites.", "tab_1");
    expect(listener).toBeTypeOf("function");

    // Harness pushes a task update — exactly what the live loop does.
    listener!(fakeTask({ status: "waiting_user", userGoal: "compare RTX 5090" }));
    expect(manager.isGoalWaitingForUser()).toBe(true);

    manager.provideUserAnswer("budget is ₹300000", "tab_1");
    expect(respondSpy).toHaveBeenCalledWith("budget is ₹300000", "tab_1");
  });

  it("accepts travel-class goals verbatim — no frontend keyword gate decides routing", async () => {
    const manager = mgrMod.BrowserTaskManager.getInstance();
    const harness = harnessMod.BrowserAgentHarness.getInstance();
    const spy = vi.spyOn(harness, "executeGoal").mockResolvedValue(fakeTask());

    const goal = "Plan a 7-day trip to Munich. Find suitable hotels, attractions and estimated costs.";
    await manager.startGoal(goal, "tab_2");

    expect(spy.mock.calls[0][0]).toBe(goal);
    expect(spy.mock.calls[0][1]).toBe("tab_2");
  });

  it("exposes exactly ONE task entrypoint — the deprecated startTask is gone", () => {
    const manager = mgrMod.BrowserTaskManager.getInstance() as unknown as Record<string, unknown>;
    expect(typeof manager.startGoal).toBe("function");
    expect(manager.startTask).toBeUndefined();
  });
});
