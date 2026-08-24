import { apiRequest } from "./client";

export interface BrowserTab {
  id: string;
  title: string;
  url: string;
  favicon?: string;
  is_active: boolean;
  is_loading: boolean;
  is_secure: boolean;
  created_at: string;
}

export interface PageContextSummary {
  title: string;
  url: string;
  visible_text_summary: string;
  headings: string[];
  links_count: number;
  forms_count: number;
  tables_count: number;
  is_secure_https: boolean;
  ads_blocked_count: number;
}

export interface AdBlockStats {
  total_blocked: number;
  trackers_blocked: number;
  ads_blocked: number;
  rules_loaded: number;
}

export const browserApi = {
  listTabs: (): Promise<BrowserTab[]> => apiRequest<BrowserTab[]>("/browser/tabs"),

  createTab: (url?: string, title?: string): Promise<BrowserTab> =>
    apiRequest<BrowserTab>("/browser/tabs", {
      method: "POST",
      body: JSON.stringify({ url, title }),
    }),

  closeTab: (tabId: string): Promise<{ success: boolean }> =>
    apiRequest<{ success: boolean }>(`/browser/tabs/${tabId}`, {
      method: "DELETE",
    }),

  switchTab: (tabId: string): Promise<BrowserTab> =>
    apiRequest<BrowserTab>(`/browser/tabs/${tabId}/switch`, {
      method: "POST",
    }),

  navigateTab: (tabId: string, url: string): Promise<BrowserTab> =>
    apiRequest<BrowserTab>(`/browser/tabs/${tabId}/navigate`, {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  getPageContext: (htmlContent?: string): Promise<PageContextSummary> =>
    apiRequest<PageContextSummary>("/browser/context", {
      method: "POST",
      body: JSON.stringify({ html_content: htmlContent }),
    }),

  getAdBlockStats: (): Promise<AdBlockStats> =>
    apiRequest<AdBlockStats>("/browser/adblock/stats"),

  recordHistory: (
    url: string,
    title: string,
    profileId: string = "default",
    isPrivate: boolean = false
  ): Promise<{ status: string; id?: string }> =>
    apiRequest<{ status: string; id?: string }>("/browser/history", {
      method: "POST",
      body: JSON.stringify({ url, title, profile_id: profileId, is_private: isPrivate }),
    }),

  listHistory: (
    limit: number = 100,
    profileId?: string
  ): Promise<Array<{ id: string; url: string; title: string; profile_id: string; visited_at: string; visit_count: number }>> =>
    apiRequest<Array<{ id: string; url: string; title: string; profile_id: string; visited_at: string; visit_count: number }>>(
      `/browser/history?limit=${limit}${profileId ? `&profile_id=${profileId}` : ""}`
    ),

  clearHistory: (profileId?: string): Promise<{ status: string; cleared: boolean }> =>
    apiRequest<{ status: string; cleared: boolean }>(
      `/browser/history${profileId ? `?profile_id=${profileId}` : ""}`,
      { method: "DELETE" }
    ),

  aiAssist: (payload: {
    action: string;
    url: string;
    title: string;
    headings?: string[];
    text_blocks?: string[];
    interactive_elements?: any[];
    interactive_elements_count?: number;
  }): Promise<{ status: string; response: string; tool_call?: { name: string; arguments: Record<string, any> } | null }> =>
    apiRequest<{ status: string; response: string; tool_call?: { name: string; arguments: Record<string, any> } | null }>("/browser/ai-assist", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  planAgent: (data: {
    user_goal: string;
    url: string;
    title: string;
    headings: string[];
    text_blocks: string[];
    interactive_elements: any[];
    action_history: string[];
  }): Promise<{ status: string; steps: any[] }> =>
    apiRequest<{ status: string; steps: any[] }>("/browser/plan-agent", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  installWebstoreExtension: (extensionIdOrUrl: string): Promise<{
    status: string;
    path?: string;
    extension_id?: string;
    name?: string;
    version?: string;
    description?: string;
    message?: string;
  }> =>
    apiRequest<{
      status: string;
      path?: string;
      extension_id?: string;
      name?: string;
      version?: string;
      description?: string;
      message?: string;
    }>("/browser/extensions/install-webstore", {
      method: "POST",
      body: JSON.stringify({ extension_id_or_url: extensionIdOrUrl }),
    }),
};
