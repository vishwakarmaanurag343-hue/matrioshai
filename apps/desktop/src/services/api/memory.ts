import { apiRequest } from "./client";
import { MemoryItem } from "../../types";

export interface MemorySearchResult {
  id: string;
  content: string;
  memory_tier: 'CORE' | 'RECALL' | 'ARCHIVAL';
  source_type: string;
  source_id?: string;
  relevance_score: number;
  created_at: string;
  metadata?: Record<string, any>;
}

export const memoryApi = {
  create: (data: { content: string; memory_tier: string; source_type?: string }): Promise<MemoryItem> =>
    apiRequest<MemoryItem>("/memory", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getCore: (): Promise<MemoryItem[]> =>
    apiRequest<MemoryItem[]>("/memory/core"),

  setCore: (data: { user_preferences?: string; active_goals?: string; important_facts?: string }): Promise<MemoryItem[]> =>
    apiRequest<MemoryItem[]>("/memory/core", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  search: (query: string, tier?: string, limit = 10): Promise<MemorySearchResult[]> =>
    apiRequest<MemorySearchResult[]>("/memory/search", {
      method: "POST",
      body: JSON.stringify({ query, tier, limit }),
    }),

  delete: (id: string): Promise<void> =>
    apiRequest<void>(`/memory/${id}`, {
      method: "DELETE",
    }),
};
