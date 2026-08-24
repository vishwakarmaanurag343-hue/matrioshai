import { apiRequest } from "./client";
import { SecurityAuditEvent, ToolDefinition, ConfirmationRequest } from "../../types";

export const securityApi = {
  getAuditLogs: (limit = 50): Promise<SecurityAuditEvent[]> =>
    apiRequest<SecurityAuditEvent[]>(`/security/audit-log?limit=${limit}`),

  getTools: (): Promise<ToolDefinition[]> =>
    apiRequest<ToolDefinition[]>("/security/tools"),

  getPendingConfirmations: (): Promise<ConfirmationRequest[]> =>
    apiRequest<ConfirmationRequest[]>("/security/confirmations"),

  resolveConfirmation: (requestId: string, approved: boolean): Promise<ConfirmationRequest> =>
    apiRequest<ConfirmationRequest>(`/security/confirmations/${requestId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    }),

  evaluateContext: (text: string, destination = "LOCAL") =>
    apiRequest("/security/evaluate-context", {
      method: "POST",
      body: JSON.stringify({ text, destination, classification: "PRIVATE" }),
    }),
};
