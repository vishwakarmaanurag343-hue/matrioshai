import { AgentTask, PlanStep } from "../types";

export class TaskPlanner {
  /**
   * Classifies task category.
   */
  static classifyGoal(userGoal: string): "general" | "research" | "comparison" | "travel" {
    const g = userGoal.toLowerCase();
    if (g.includes("trip") || g.includes("travel") || g.includes("itinerary") || g.includes("flight") || g.includes("hotel")) {
      return "travel";
    }
    if (g.includes("compare") || g.includes("vs") || g.includes("difference between") || g.includes("best options")) {
      return "comparison";
    }
    if (g.includes("research") || g.includes("paper") || g.includes("study") || g.includes("deep dive") || g.includes("explain")) {
      return "research";
    }
    return "general";
  }

  /**
   * Decomposes user goal into a concrete multi-step execution plan.
   */
  static async createPlan(userGoal: string, currentUrl: string, pageTitle: string): Promise<AgentTask> {
    const taskId = `task_${Date.now()}`;
    const mode = this.classifyGoal(userGoal);
    const g = userGoal.toLowerCase();

    let steps: PlanStep[] = [];

    if (mode === "travel") {
      steps = [
        {
          id: "step_1",
          goal: `Search travel guides and top attractions for ${userGoal}`,
          tool: "navigate",
          target: `https://www.google.com/search?q=${encodeURIComponent(userGoal + " itinerary guide")}`,
          riskLevel: "Low",
          status: "pending",
        },
        {
          id: "step_2",
          goal: "Inspect top search results and travel recommendations",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        },
        {
          id: "step_3",
          goal: "Extract hotel and flight estimates",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        },
        {
          id: "step_4",
          goal: "Compile structured day-by-day itinerary and estimated budget",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        },
      ];
    } else if (mode === "comparison") {
      steps = [
        {
          id: "step_1",
          goal: `Search options and specifications for ${userGoal}`,
          tool: "navigate",
          target: `https://www.google.com/search?q=${encodeURIComponent(userGoal)}`,
          riskLevel: "Low",
          status: "pending",
        },
        {
          id: "step_2",
          goal: "Inspect search results for top candidates",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        },
        {
          id: "step_3",
          goal: "Extract specifications, prices, and features for each option",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        },
        {
          id: "step_4",
          goal: "Synthesize structured comparison matrix with pros and cons",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        },
      ];
    } else if (mode === "research") {
      steps = [
        {
          id: "step_1",
          goal: `Search credible sources and articles for ${userGoal}`,
          tool: "navigate",
          target: `https://www.google.com/search?q=${encodeURIComponent(userGoal)}`,
          riskLevel: "Low",
          status: "pending",
        },
        {
          id: "step_2",
          goal: "Extract key findings from primary search results",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        },
        {
          id: "step_3",
          goal: "Cross-reference facts across multiple sources",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        },
        {
          id: "step_4",
          goal: "Generate comprehensive research synthesis with citations",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        },
      ];
    } else {
      // General multi-step goal
      const isSearchIntent = !g.startsWith("http") && !g.startsWith("www") && !currentUrl.includes("google.com/search");
      if (isSearchIntent) {
        steps.push({
          id: "step_1",
          goal: `Search the web for "${userGoal}"`,
          tool: "navigate",
          target: `https://www.google.com/search?q=${encodeURIComponent(userGoal)}`,
          riskLevel: "Low",
          status: "pending",
        });
        steps.push({
          id: "step_2",
          goal: "Inspect search results and identify best matching link",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        });
        steps.push({
          id: "step_3",
          goal: "Open target result and analyze information",
          tool: "click",
          target: "el_0",
          riskLevel: "Medium",
          status: "pending",
        });
        steps.push({
          id: "step_4",
          goal: "Extract required details and summarize answer",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        });
      } else {
        steps.push({
          id: "step_1",
          goal: "Inspect current page content and interactive elements",
          tool: "extract",
          riskLevel: "ReadOnly",
          status: "pending",
        });
        steps.push({
          id: "step_2",
          goal: `Complete requested action: "${userGoal}"`,
          tool: "extract",
          riskLevel: "Low",
          status: "pending",
        });
      }
    }

    return {
      taskId,
      userGoal,
      mode,
      steps,
      currentStepIndex: 0,
      status: "planning",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      visitedUrls: currentUrl ? [currentUrl] : [],
      extractedFacts: [],
      sources: currentUrl ? [{ title: pageTitle || "Initial Page", url: currentUrl }] : [],
    };
  }
}
