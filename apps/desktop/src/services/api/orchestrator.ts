import { apiRequest } from "./client";

export interface DailyBriefing {
  greeting: string;
  priorities: string[];
  important_messages: number;
  open_decisions: number;
  upcoming_deadlines: number;
  pending_approvals: number;
  top_recommendation: string;
  executive_insight: string;
}

export interface GlobalSearchResult {
  id: string;
  source: string;
  title: string;
  snippet: string;
  confidence: number;
}

export interface GlobalSearchResponse {
  query: string;
  results: GlobalSearchResult[];
}

export const orchestratorApi = {
  getDailyBriefing: (): Promise<DailyBriefing> =>
    apiRequest<DailyBriefing>("/orchestrator/briefing"),

  globalSearch: (query: string): Promise<GlobalSearchResponse> =>
    apiRequest<GlobalSearchResponse>(`/orchestrator/search?query=${encodeURIComponent(query)}`),

  createTask: (user_prompt: string): Promise<any> =>
    apiRequest<any>(`/orchestrator/tasks?user_prompt=${encodeURIComponent(user_prompt)}`, {
      method: "POST",
    }),

  cancelTask: (taskId: string): Promise<any> =>
    apiRequest<any>(`/orchestrator/tasks/${taskId}/cancel`, {
      method: "POST",
    }),
};
