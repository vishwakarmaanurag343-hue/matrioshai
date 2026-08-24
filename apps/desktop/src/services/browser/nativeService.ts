import { invoke } from "@tauri-apps/api/core";
import { listen, UnlistenFn } from "@tauri-apps/api/event";

export type ProfileType = "REGULAR" | "PRIVATE" | "GUEST";

export interface BrowserProfile {
  id: string;
  name: string;
  profile_type: ProfileType;
  storage_path: string;
  created_at: number;
  last_used_at: number;
  is_default: boolean;
}

export type PermissionAction = "ASK" | "ALLOW" | "DENY";

export interface PermissionState {
  profile_id: string;
  origin: string;
  permission: string;
  state: PermissionAction;
  updated_at: number;
}

export type ShieldLevel = "STANDARD" | "STRICT" | "CUSTOM" | "OFF";

export interface ShieldStats {
  ads_blocked: number;
  trackers_blocked: number;
  malicious_blocked: number;
  total_evaluated: number;
}

export type ActionRiskLevel = "ReadOnly" | "Low" | "Medium" | "High" | "Critical";

export interface InteractiveElement {
  element_id: string;
  role: string;
  name: string;
  tag?: string;
  aria_label?: string;
  title?: string;
  href?: string;
  input_type?: string;
  placeholder?: string;
  value?: string;
  disabled?: boolean;
  visible?: boolean;
  selector: string;
  rect?: { x: number; y: number; width: number; height: number };
  sensitive: boolean;
  accessible_name?: string;
  enabled?: boolean;
  is_searchbox?: boolean;
}

export interface SemanticPageModel {
  schema_version: string;
  page_id: string;
  page_version: number;
  tab_id: string;
  url: string;
  origin: string;
  title: string;
  page_type: string;
  headings: string[];
  text_blocks: string[];
  interactive_elements: InteractiveElement[];
  forms_count: number;
  tables_count: number;
  links_count: number;
  trust_level: string;
  timestamp: number;
  observation_status?: string;
  observation_failed?: boolean;
}

export type AgentTaskStatus =
  | "IDLE"
  | "UNDERSTANDING"
  | "PLANNING"
  | "WAITING_FOR_APPROVAL"
  | "EXECUTING"
  | "OBSERVING"
  | "VERIFYING"
  | "RECOVERING"
  | "REPLANNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "BLOCKED";

export interface PlanStep {
  step_id: string;
  description: string;
  tool: string;
  target?: string;
  value?: string;
  risk_level: ActionRiskLevel;
  status: string;
}

export interface ExecutionPlan {
  plan_id: string;
  task_id: string;
  version: number;
  objective: string;
  steps: PlanStep[];
  current_step_index: number;
}

export interface TaskSpec {
  task_id: string;
  user_goal: string;
  tab_id: string;
  status: AgentTaskStatus;
  active_plan?: ExecutionPlan;
  created_at: number;
  updated_at: number;
}

export interface BrowserContextSummary {
  tab_id: string;
  url: string;
  title: string;
  origin: string;
  visible_text_snippet: string;
  headings: string[];
  interactive_elements_count: number;
  trust_level: string;
}

export interface AIActionResult {
  success: boolean;
  action: string;
  tab_id: string;
  risk_level: ActionRiskLevel;
  approval_required: boolean;
  message: string;
  data?: any;
}

export type TabStatus =
  | "CREATING"
  | "LOADING"
  | "READY"
  | "NAVIGATING"
  | "ERROR"
  | "CRASHED"
  | "CLOSING"
  | "CLOSED";

export interface RectBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TabGroup {
  id: string;
  name: string;
  color: string;
  collapsed: boolean;
}

export interface NativeBrowserTab {
  id: string;
  webview_id: string;
  profile_id: string;
  url: string;
  title: string;
  favicon?: string | null;
  loading: boolean;
  progress: number;
  can_go_back: boolean;
  can_go_forward: boolean;
  active: boolean;
  visible: boolean;
  pinned: boolean;
  group_id?: string | null;
  zoom_factor: number;
  created_at: number;
  last_active_at: number;
  navigation_generation: number;
  status: TabStatus;
  shield_stats: ShieldStats;
}

export interface BrowserNavigationEvent {
  event_type: string;
  tab_id: string;
  navigation_generation: number;
  url: string;
  title: string;
  loading: boolean;
  can_go_back: boolean;
  can_go_forward: boolean;
}

export interface InstalledExtension {
  id: string;
  name: string;
  version: string;
  description: string;
  icon_url?: string | null;
  enabled: boolean;
  path: string;
  popup_path?: string | null;
  content_scripts?: Array<{ matches?: string[]; js?: string[]; css?: string[] }>;
  permissions: string[];
  installed_at: number;
}

export const nativeBrowserService = {
  // Phase 8: Autonomous Agent Runtime
  createAgentTask: async (
    userGoal: string,
    tabId?: string,
    steps?: any[]
  ): Promise<TaskSpec> => {
    return invoke<TaskSpec>("agent_create_task", {
      userGoal,
      tabId,
      steps,
    });
  },

  executeNextStep: async (taskId: string): Promise<TaskSpec> => {
    return invoke<TaskSpec>("agent_execute_next_step", {
      taskId,
    });
  },

  cancelAgentTask: async (taskId: string): Promise<TaskSpec> => {
    return invoke<TaskSpec>("agent_cancel_task", {
      taskId,
    });
  },

  // Semantic Page Understanding & Native WKWebView Inspection
  getSemanticPage: async (tabId?: string): Promise<SemanticPageModel> => {
    return invoke<SemanticPageModel>("browser_get_semantic_page", {
      tabId,
    });
  },

  inspectPage: async (tabId?: string): Promise<SemanticPageModel> => {
    return invoke<SemanticPageModel>("browser_inspect_page", {
      tabId,
    });
  },

  debugEval: async (tabId?: string, customJs?: string): Promise<{ title: string; body_text_len: number; elements_count: number; custom_js_result: string; status: string; tab_id: string; url: string; ready_state: string; links_count: number; buttons_count: number; inputs_count: number }> => {
    return invoke("browser_debug_eval", {
      tabId,
      customJs,
    });
  },

  // AI Bridge & Policy Gateway
  getAIContext: async (tabId?: string): Promise<BrowserContextSummary> => {
    return invoke<BrowserContextSummary>("ai_browser_get_context", {
      tabId,
    });
  },

  executeAIAction: async (
    tabId: string,
    action: string,
    target?: string,
    value?: string,
    userApproved?: boolean
  ): Promise<AIActionResult> => {
    return invoke<AIActionResult>("ai_browser_execute_action", {
      tabId,
      action,
      target,
      value,
      userApproved,
    });
  },

  // Shields & Privacy
  getShieldStats: async (tabId?: string): Promise<ShieldStats> => {
    return invoke<ShieldStats>("browser_get_shield_stats", {
      tabId,
    });
  },

  setSiteShield: async (
    profileId: string,
    origin: string,
    level: ShieldLevel
  ): Promise<void> => {
    return invoke<void>("browser_set_site_shield", {
      profileId,
      origin,
      level,
    });
  },

  // Profiles
  createProfile: async (
    profileId: string,
    name: string,
    isPrivate: boolean = false
  ): Promise<BrowserProfile> => {
    return invoke<BrowserProfile>("browser_create_profile", {
      profileId,
      name,
      isPrivate,
    });
  },

  getProfiles: async (): Promise<BrowserProfile[]> => {
    return invoke<BrowserProfile[]>("browser_get_profiles");
  },

  switchProfile: async (profileId: string): Promise<BrowserProfile> => {
    return invoke<BrowserProfile>("browser_switch_profile", {
      profileId,
    });
  },

  // Permissions & Site Data
  setPermission: async (
    profileId: string,
    origin: string,
    permission: string,
    action: PermissionAction
  ): Promise<void> => {
    return invoke<void>("browser_set_permission", {
      profileId,
      origin,
      permission,
      action,
    });
  },

  getPermissions: async (profileId: string): Promise<PermissionState[]> => {
    return invoke<PermissionState[]>("browser_get_permissions", {
      profileId,
    });
  },

  clearSiteData: async (
    profileId: string,
    origin?: string
  ): Promise<void> => {
    return invoke<void>("browser_clear_site_data", {
      profileId,
      origin,
    });
  },

  // Tabs
  createTab: async (
    tabId: string,
    url: string,
    bounds: RectBounds,
    activate: boolean = true,
    profileId?: string
  ): Promise<NativeBrowserTab> => {
    return invoke<NativeBrowserTab>("browser_create_tab", {
      tabId,
      url,
      bounds,
      activate,
      profileId,
    });
  },

  activateTab: async (tabId: string): Promise<NativeBrowserTab> => {
    return invoke<NativeBrowserTab>("browser_activate_tab", {
      tabId,
    });
  },

  closeTab: async (tabId: string): Promise<string | null> => {
    return invoke<string | null>("browser_close_tab", {
      tabId,
    });
  },

  navigate: async (tabId: string, url: string, bounds?: RectBounds): Promise<number> => {
    return invoke<number>("browser_navigate", {
      tabId,
      url,
      bounds: bounds ?? null,
    });
  },

  stopLoading: async (tabId: string): Promise<void> => {
    return invoke<void>("browser_stop_loading", {
      tabId,
    });
  },

  updateBounds: async (tabId: string, bounds: RectBounds): Promise<void> => {
    return invoke<void>("browser_update_bounds", {
      tabId,
      bounds,
    });
  },

  getContentViewOffset: async (): Promise<number> => {
    return invoke<number>("get_content_view_offset");
  },

  hideAllWebviews: async (): Promise<void> => {
    return invoke<void>("browser_hide_all_webviews");
  },

  reorderTabs: async (newOrder: string[]): Promise<void> => {
    return invoke<void>("browser_reorder_tabs", {
      newOrder,
    });
  },

  duplicateTab: async (
    sourceTabId: string,
    newTabId: string
  ): Promise<NativeBrowserTab> => {
    return invoke<NativeBrowserTab>("browser_duplicate_tab", {
      sourceTabId,
      newTabId,
    });
  },

  goBack: async (tabId: string): Promise<void> => {
    return invoke<void>("browser_go_back", {
      tabId,
    });
  },

  goForward: async (tabId: string): Promise<void> => {
    return invoke<void>("browser_go_forward", {
      tabId,
    });
  },

  reload: async (tabId: string): Promise<void> => {
    return invoke<void>("browser_reload", {
      tabId,
    });
  },

  hardReload: async (tabId: string): Promise<void> => {
    return invoke<void>("browser_hard_reload", {
      tabId,
    });
  },

  setTabPinned: async (tabId: string, pinned: boolean): Promise<void> => {
    return invoke<void>("browser_set_tab_pinned", {
      tabId,
      pinned,
    });
  },

  setTabGroup: async (tabId: string, groupId?: string | null): Promise<void> => {
    return invoke<void>("browser_set_tab_group", {
      tabId,
      groupId: groupId || null,
    });
  },

  upsertTabGroup: async (group: TabGroup): Promise<void> => {
    return invoke<void>("browser_upsert_tab_group", {
      group,
    });
  },

  getTabGroups: async (): Promise<TabGroup[]> => {
    return invoke<TabGroup[]>("browser_get_tab_groups");
  },

  reopenLastClosedTab: async (newTabId: string): Promise<NativeBrowserTab | null> => {
    return invoke<NativeBrowserTab | null>("browser_reopen_last_closed_tab", {
      newTabId,
    });
  },

  setZoom: async (tabId: string, zoomFactor: number): Promise<void> => {
    return invoke<void>("browser_set_zoom", {
      tabId,
      zoomFactor,
    });
  },

  print: async (tabId: string): Promise<void> => {
    return invoke<void>("browser_print", {
      tabId,
    });
  },

  getAllTabs: async (): Promise<NativeBrowserTab[]> => {
    return invoke<NativeBrowserTab[]>("browser_get_all_tabs");
  },

  getActiveTab: async (): Promise<NativeBrowserTab | null> => {
    return invoke<NativeBrowserTab | null>("browser_get_active_tab");
  },

  getTabLiveUrl: async (tabId: string): Promise<string> => {
    return invoke<string>("browser_get_tab_live_url", { tabId });
  },

  // Extensions Management API
  loadExtension: async (extensionPath: string): Promise<InstalledExtension> => {
    return invoke<InstalledExtension>("browser_load_extension", {
      extensionPath,
    });
  },

  getExtensions: async (): Promise<InstalledExtension[]> => {
    return invoke<InstalledExtension[]>("browser_get_extensions");
  },

  toggleExtension: async (extensionId: string, enabled: boolean): Promise<void> => {
    return invoke<void>("browser_toggle_extension", {
      extensionId,
      enabled,
    });
  },

  removeExtension: async (extensionId: string): Promise<void> => {
    return invoke<void>("browser_remove_extension", {
      extensionId,
    });
  },

  onNavigationStarted: async (
    callback: (event: BrowserNavigationEvent) => void
  ): Promise<UnlistenFn> => {
    return listen<BrowserNavigationEvent>("browser://navigation-started", (e) => {
      callback(e.payload);
    });
  },

  onUrlChanged: async (
    callback: (event: { tab_id: string; url: string; title: string }) => void
  ): Promise<UnlistenFn> => {
    return listen<{ tab_id: string; url: string; title: string }>("browser://url-changed", (e) => {
      callback(e.payload);
    });
  },
};
