import { apiRequest } from "./client";
import { AppSettings } from "../../types";

export const settingsApi = {
  get: (): Promise<AppSettings> => apiRequest<AppSettings>("/settings"),

  update: (updates: {
    ollama_base_url?: string;
    ollama_model?: string;
    claude_code_api_key?: string;
  }): Promise<AppSettings> =>
    apiRequest<AppSettings>("/settings", {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),

  testClaudeCodeConnection: (): Promise<{ connected: boolean; message: string; tested_at: string }> =>
    apiRequest<{ connected: boolean; message: string; tested_at: string }>("/settings/coding-agents/claude-code/test", {
      method: "POST",
    }),
};
