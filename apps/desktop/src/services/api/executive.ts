import { apiRequest } from "./client";
import {
  RoleMetadata,
  ExecutiveResponse,
  SynthesisResponse,
  DecisionResponse,
  ExecutiveRoleType
} from "../../types";

export const executiveApi = {
  getRoles: (): Promise<RoleMetadata[]> =>
    apiRequest<RoleMetadata[]>("/executive/roles"),

  analyzeRole: (role: ExecutiveRoleType, prompt: string, conversationId?: string): Promise<ExecutiveResponse> =>
    apiRequest<ExecutiveResponse>("/executive/analyze", {
      method: "POST",
      body: JSON.stringify({ role, prompt, conversation_id: conversationId }),
    }),

  run5cCouncil: (prompt: string, decisionTitle?: string, conversationId?: string): Promise<SynthesisResponse> =>
    apiRequest<SynthesisResponse>("/executive/5c", {
      method: "POST",
      body: JSON.stringify({ prompt, decision_title: decisionTitle, conversation_id: conversationId, save_as_decision: true }),
    }),

  listDecisions: (): Promise<DecisionResponse[]> =>
    apiRequest<DecisionResponse[]>("/executive/decisions"),

  getDecision: (decisionId: string): Promise<DecisionResponse> =>
    apiRequest<DecisionResponse>(`/executive/decisions/${decisionId}`),

  updateDecisionStatus: (decisionId: string, status: string): Promise<DecisionResponse> =>
    apiRequest<DecisionResponse>(`/executive/decisions/${decisionId}/status?status=${status}`, {
      method: "PATCH",
    }),

  promoteDecisionToMemory: (decisionId: string): Promise<{ status: string; decision_id: string }> =>
    apiRequest(`/executive/decisions/${decisionId}/promote-to-memory`, {
      method: "POST",
    }),

  revisitDecision: (decisionId: string): Promise<SynthesisResponse> =>
    apiRequest<SynthesisResponse>(`/executive/decisions/${decisionId}/revisit`, {
      method: "POST",
    }),
};
