import { describe, it, expect, beforeEach } from "vitest";
import { BrowserAgentHarness } from "../agentHarness";
import { AgentTask, EvidenceItem } from "../types";

describe("Phase 4 Step 5 — Adaptive Research & Source Quality Suite", () => {
  let harness: BrowserAgentHarness;
  let task: AgentTask;

  beforeEach(() => {
    harness = BrowserAgentHarness.getInstance();
    task = {
      taskId: "test_research_task_1",
      userGoal: "Compare Python and Rust official features and release years",
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

  it("source quality model: handles evidence enrichment and source provenance", () => {
    const items: EvidenceItem[] = [
      {
        label: "Python Created Year",
        value: "1991",
        source: "https://www.python.org",
      },
    ];

    (harness as any).mergeEvidence(task, items, "tab_1");

    expect(task.evidence.length).toBe(1);
    expect(task.evidence[0].source).toBe("https://www.python.org");
    expect(task.evidence[0].tab_id).toBe("tab_1");
    expect(task.evidence[0].evidence_type).toBe("OBSERVED");
    expect(task.evidence[0].validity).toBe("CURRENT");
  });

  it("contradiction escalation: tags cross-source conflicts as CONTRADICTED without deleting either item", () => {
    const source1: EvidenceItem[] = [
      {
        label: "Rust Release Year",
        value: "2015",
        source: "https://www.rust-lang.org",
      },
    ];

    const source2: EvidenceItem[] = [
      {
        label: "Rust Release Year",
        value: "2010",
        source: "https://someblog.com/rust",
      },
    ];

    (harness as any).mergeEvidence(task, source1, "tab_1");
    (harness as any).mergeEvidence(task, source2, "tab_2");

    expect(task.evidence.length).toBe(2);
    expect(task.evidence[0].validity).toBe("CONTRADICTED");
    expect(task.evidence[1].validity).toBe("CONTRADICTED");
  });
});
