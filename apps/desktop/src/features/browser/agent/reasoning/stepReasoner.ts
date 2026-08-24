import { apiRequest } from "../../../../services/api/client";
import { AgentDecision, ReasoningRequest } from "../types";

export interface StepReasonerResponse {
  status: string;
  decision: AgentDecision;
}

/**
 * Client for the DeepSeek-Harness per-iteration reasoning endpoint
 * (POST /api/v1/browser/agent/next-step). The backend validates the model's
 * structured output and returns exactly ONE decision — it never executes.
 */
export class StepReasoner {
  static async nextStep(req: ReasoningRequest): Promise<AgentDecision> {
    const res = await apiRequest<StepReasonerResponse>("/browser/agent/next-step", {
      method: "POST",
      body: JSON.stringify({
        goal: req.goal,
        url: req.url || "",
        title: req.title || "",
        ready_state: req.ready_state || "complete",
        headings: (req.headings || []).slice(0, 10),
        text_blocks: (req.text_blocks || []).slice(0, 8),
        interactive_elements: (req.interactive_elements || []).slice(0, 40),
        tabs: req.tabs || [],
        history: req.history.slice(-10),
        constraints: req.constraints || [],
        failed_strategies: (req.failed_strategies || []).slice(-8),
        observation_level: req.observation_level || "dom",
      }),
    });
    if (!res || res.status !== "ok" || !res.decision || !res.decision.action) {
      throw new Error("Reasoning endpoint returned no usable decision");
    }
    return res.decision;
  }
}
