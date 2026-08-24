import { apiRequest } from "./client";

export interface GraphEntity {
  id: string;
  name: string;
  entity_type: string;
  canonical_name: string;
  aliases: string[];
  confidence: number;
  provenance?: string;
  created_at: string;
}

export interface GraphRelationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: string;
  confidence: number;
  provenance?: string;
  created_at: string;
}

export interface KnowledgeGraphResponse {
  entities: GraphEntity[];
  relationships: GraphRelationship[];
}

export interface ProactiveSuggestion {
  id: string;
  signal_type: string;
  priority: 'LOW' | 'NORMAL' | 'IMPORTANT' | 'URGENT';
  title: string;
  reason: string;
  evidence: string;
  suggested_action: string;
  created_at: string;
  is_dismissed: boolean;
  is_snoozed: boolean;
}

export const knowledgeApi = {
  getGraph: (): Promise<KnowledgeGraphResponse> =>
    apiRequest<KnowledgeGraphResponse>("/knowledge/graph"),

  searchEntities: (query: string): Promise<GraphEntity[]> =>
    apiRequest<GraphEntity[]>(`/knowledge/search?query=${encodeURIComponent(query)}`),
};

export const proactiveApi = {
  getSuggestions: (): Promise<ProactiveSuggestion[]> =>
    apiRequest<ProactiveSuggestion[]>("/proactive"),

  dismissSuggestion: (id: string): Promise<any> =>
    apiRequest<any>(`/proactive/${id}/dismiss`, { method: "POST" }),

  snoozeSuggestion: (id: string): Promise<any> =>
    apiRequest<any>(`/proactive/${id}/snooze`, { method: "POST" }),
};
