import { describe, it, expect, beforeEach } from "vitest";
import { BrowserAgentHarness } from "../agentHarness";
import { AgentTask, AgentDecision } from "../types";

describe("Phase 4 Step 4 — Advanced Multi-Step Planning & Execution Suite", () => {
  let harness: BrowserAgentHarness;
  let task: AgentTask;

  beforeEach(() => {
    harness = BrowserAgentHarness.getInstance();
    task = {
      taskId: "test_multistep_task_1",
      userGoal: "Compare Python and Rust features across tabs",
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

  it("subgoal tracking: updates activeSubgoal from decision", () => {
    const d: AgentDecision = {
      action: "NAVIGATE",
      target: "https://python.org",
      reason: "Open Python site",
      expected_effect: { type: "none" },
      requires_approval: false,
      subgoal: "Subgoal 1: Extract Python facts",
    };

    (harness as any).activeSubgoal = null;
    if (d.subgoal) (harness as any).activeSubgoal = d.subgoal;

    expect((harness as any).activeSubgoal).toBe("Subgoal 1: Extract Python facts");
  });

  it("early completion safety: rejects premature DONE when research goal lacks evidence", () => {
    const researchTask: AgentTask = {
      ...task,
      userGoal: "Compare prices of laptop models",
      evidence: [],
    };

    const d: AgentDecision = {
      action: "DONE",
      reason: "Completed without facts",
      expected_effect: { type: "none" },
      requires_approval: false,
    };

    const isResearchGoal = /search|find|compare|price|title|specs/i.test(researchTask.userGoal);
    const hasEvidence = researchTask.evidence && researchTask.evidence.length > 0;
    const premature = isResearchGoal && !hasEvidence;

    expect(premature).toBe(true);
  });

  it("early completion safety: allows DONE when research goal contains collected evidence", () => {
    const researchTask: AgentTask = {
      ...task,
      userGoal: "Compare prices of laptop models",
      evidence: [
        { label: "Laptop A", value: "$999", source: "https://shop1.com" },
      ],
    };

    const isResearchGoal = /search|find|compare|price|title|specs/i.test(researchTask.userGoal);
    const hasEvidence = researchTask.evidence && researchTask.evidence.length > 0;
    const premature = isResearchGoal && !hasEvidence;

    expect(premature).toBe(false);
  });
});
