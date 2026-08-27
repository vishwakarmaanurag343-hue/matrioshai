import { describe, it, expect, beforeEach } from "vitest";
import { BrowserAgentHarness } from "../agentHarness";
import { AgentTask, AgentDecision, PageModel } from "../types";

describe("Phase 4 Step 3 — Deterministic Failure Recovery Suite", () => {
  let harness: BrowserAgentHarness;
  let task: AgentTask;

  beforeEach(() => {
    harness = BrowserAgentHarness.getInstance();
    task = {
      taskId: "test_recovery_task_1",
      userGoal: "Test failure recovery pipeline",
      status: "running",
      steps: [],
      visitedUrls: [],
      sources: [],
      extractedFacts: [],
      evidence: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  });

  it("stale element recovery: re-resolution succeeds on fresh page model", () => {
    const staleModel: PageModel = {
      url: "https://example.com",
      title: "Example",
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

    const freshModel: PageModel = {
      ...staleModel,
      buttons: [
        {
          id: "el_btn_1",
          name: "Submit Order",
          role: "button",
          tag: "button",
          text: "Submit Order",
          href: "",
          selector: "button.submit",
          sensitive: false,
          boundingBox: { x: 10, y: 10, width: 100, height: 30 },
          visible: true,
          enabled: true,
        },
      ],
    };

    // Stale resolution fails
    const initialRes = harness.resolveTarget("Submit Order", staleModel);
    expect(initialRes).toBeNull();

    // Fresh resolution succeeds after re-observation
    const recoveryRes = harness.resolveTarget("Submit Order", freshModel);
    expect(recoveryRes).not.toBeNull();
    expect(recoveryRes?.element.id).toBe("el_btn_1");
  });

  it("stale element recovery: ambiguous candidates fail closed without guessing", () => {
    const ambiguousModel: PageModel = {
      url: "https://example.com",
      title: "Example",
      sections: [],
      links: [
        {
          id: "el_link_1",
          name: "Read Documentation Page 1",
          role: "link",
          tag: "a",
          text: "Read Documentation Page 1",
          href: "/doc1",
          selector: "a.doc1",
          sensitive: false,
          boundingBox: { x: 0, y: 0, width: 50, height: 20 },
          visible: true,
          enabled: true,
        },
        {
          id: "el_link_2",
          name: "Read Documentation Page 2",
          role: "link",
          tag: "a",
          text: "Read Documentation Page 2",
          href: "/doc2",
          selector: "a.doc2",
          sensitive: false,
          boundingBox: { x: 0, y: 30, width: 50, height: 20 },
          visible: true,
          enabled: true,
        },
      ],
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

    // Resolving ambiguous text query fails closed (returns null)
    const res = harness.resolveTarget("Read Documentation Page", ambiguousModel);
    expect(res).toBeNull();
  });

  it("bounded retry budget: trackFailure triggers strategy change warning after 2 consecutive identical failures", () => {
    const d: AgentDecision = {
      action: "CLICK",
      target: "el_missing",
      reason: "Click missing button",
      expected_effect: { type: "none" },
      requires_approval: false,
    };

    const fn = (harness as any).trackFailure.bind(harness);
    (harness as any).history = [
      { action: "CLICK", target: "el_missing", verified: false },
      { action: "CLICK", target: "el_missing", verified: false },
    ];

    const currentFailures = fn(d, 1);
    expect(currentFailures).toBe(2);
    expect((harness as any).history[(harness as any).history.length - 1].note).toContain("REPEATED FAILURE");
  });
});
