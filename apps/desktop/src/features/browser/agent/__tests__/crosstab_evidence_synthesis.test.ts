import { describe, it, expect, beforeEach } from "vitest";
import { BrowserAgentHarness } from "../agentHarness";
import { AgentTask, EvidenceItem } from "../types";

describe("Phase 4 Step 2 — Cross-Tab Evidence Synthesis & Contradiction Pipeline", () => {
  let harness: BrowserAgentHarness;
  let task: AgentTask;

  beforeEach(() => {
    harness = BrowserAgentHarness.getInstance();
    task = {
      taskId: "test_crosstab_task_1",
      userGoal: "Compare Python price across sources",
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

  it("normalizes currency values without destroying original string", () => {
    const fn = (harness as any).normalizeValue.bind(harness);
    expect(fn("$1,299.00")).toBe("1299.00 USD");
    expect(fn("₹15,999")).toBe("15999 INR");
    expect(fn("€250")).toBe("250 EUR");
    expect(fn("plain text")).toBe("plain text");
  });

  it("assigns tab_id, timestamp, evidence_type, and validity during mergeEvidence", () => {
    const items: EvidenceItem[] = [
      { label: "official price", value: "$100", source: "https://source-a.com" },
    ];
    (harness as any).mergeEvidence(task, items, "tab_100");

    expect(task.evidence).toHaveLength(1);
    const ev = task.evidence[0];
    expect(ev.tab_id).toBe("tab_100");
    expect(ev.source).toBe("https://source-a.com");
    expect(ev.evidence_type).toBe("OBSERVED");
    expect(ev.validity).toBe("CURRENT");
    expect(ev.normalized_value).toBe("100 USD");
  });

  it("deduplicates identical evidence from the same source", () => {
    const items: EvidenceItem[] = [
      { label: "official price", value: "$100", source: "https://source-a.com" },
      { label: "official price", value: "$100", source: "https://source-a.com" },
    ];
    (harness as any).mergeEvidence(task, items, "tab_100");

    expect(task.evidence).toHaveLength(1);
  });

  it("detects cross-source contradiction when values differ for the same label", () => {
    const itemA: EvidenceItem[] = [
      { label: "product price", value: "$100", source: "https://source-a.com" },
    ];
    const itemB: EvidenceItem[] = [
      { label: "product price", value: "$120", source: "https://source-b.com" },
    ];

    (harness as any).mergeEvidence(task, itemA, "tab_1");
    (harness as any).mergeEvidence(task, itemB, "tab_2");

    expect(task.evidence).toHaveLength(2);
    expect(task.evidence[0].validity).toBe("CONTRADICTED");
    expect(task.evidence[1].validity).toBe("CONTRADICTED");
    expect(task.evidence[0].source).toBe("https://source-a.com");
    expect(task.evidence[1].source).toBe("https://source-b.com");
  });

  it("preserves evidence across tab switching without erasing historical tab facts", () => {
    const itemTab1: EvidenceItem[] = [
      { label: "fact A", value: "Value A", source: "https://tab1.com" },
    ];
    const itemTab2: EvidenceItem[] = [
      { label: "fact B", value: "Value B", source: "https://tab2.com" },
    ];

    (harness as any).mergeEvidence(task, itemTab1, "tab_1");
    (harness as any).mergeEvidence(task, itemTab2, "tab_2");

    // Switching back to tab_1 and executing merge should retain both tab_1 and tab_2 facts
    (harness as any).mergeEvidence(task, [{ label: "fact C", value: "Value C", source: "https://tab1.com" }], "tab_1");

    expect(task.evidence).toHaveLength(3);
    expect(task.evidence.map((e) => e.label)).toEqual(["fact A", "fact B", "fact C"]);
  });
});
