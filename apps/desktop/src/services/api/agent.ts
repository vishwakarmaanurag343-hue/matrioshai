import { apiRequest } from "./client";
import { AgentTask } from "../../types";

export const agentApi = {
  createTask: (user_goal: string, workspace_id?: string, max_steps: number = 20): Promise<AgentTask> =>
    apiRequest<AgentTask>("/agent/tasks", {
      method: "POST",
      body: JSON.stringify({ user_goal, workspace_id, max_steps }),
    }),

  listTasks: (): Promise<AgentTask[]> =>
    apiRequest<AgentTask[]>("/agent/tasks"),

  getTask: (taskId: string): Promise<AgentTask> =>
    apiRequest<AgentTask>(`/agent/tasks/${taskId}`),

  pauseTask: (taskId: string): Promise<AgentTask> =>
    apiRequest<AgentTask>(`/agent/tasks/${taskId}/pause`, {
      method: "POST",
    }),

  resumeTask: (taskId: string): Promise<AgentTask> =>
    apiRequest<AgentTask>(`/agent/tasks/${taskId}/resume`, {
      method: "POST",
    }),

  cancelTask: (taskId: string): Promise<AgentTask> =>
    apiRequest<AgentTask>(`/agent/tasks/${taskId}/cancel`, {
      method: "POST",
    }),

  approveStep: (taskId: string, stepId: string, approved: boolean): Promise<AgentTask> =>
    apiRequest<AgentTask>(`/agent/tasks/${taskId}/steps/${stepId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    }),
};
