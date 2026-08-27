import React, { useState, useEffect, useRef } from "react";
import {
  ArrowLeft,
  ArrowRight,
  RotateCw,
  Lock,
  Plus,
  X,
  Sparkles,
  Shield,
  Copy,
  Square,
  Pin,
  Bookmark,
  Menu,
  Puzzle,
} from "lucide-react";
import { browserApi, AdBlockStats } from "../../services/api/browser";
import { SearchEngineResolver } from "../../services/browser/resolver";
import {
  nativeBrowserService,
  NativeBrowserTab,
  RectBounds,
  BrowserProfile,
  InstalledExtension,
} from "../../services/browser/nativeService";
import ReactMarkdown from "react-markdown";
import type { BookmarkItem } from "./BookmarksManagerModal";
import type { HistoryEntry } from "./HistoryManagerModal";
import type { PasswordEntry } from "./PasswordManagerModal";
import type { DownloadItem } from "./DownloadManagerDrawer";
import { BrowserTaskManager, BrowserAgentHarness, AgentTask, ActionVerifier, AgentExecutionCard } from "./agent";

export const BrowserView: React.FC = () => {
  const [tabs, setTabs] = useState<NativeBrowserTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [urlInput, setUrlInput] = useState<string>("https://matrioshai.local");
  const [liveUrl, setLiveUrl] = useState<string>("");  // Ground-truth URL from OS webview
  const [isEditingAddress, setIsEditingAddress] = useState<boolean>(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [assistantInput, setAssistantInput] = useState<string>("");
  const [adBlockStats, setAdBlockStats] = useState<AdBlockStats | null>(null);
  const [loadingAi, setLoadingAi] = useState<boolean>(false);
  const [searchEngine, setSearchEngine] = useState<"duckduckgo" | "google" | "brave" | "bing" | "startpage" | "ecosia">("google");
  const [showSettings, setShowSettings] = useState<boolean>(false);

  // Multi-View Right Sidebar: 'ai' | 'menu' | 'downloads' | 'bookmarks' | 'history' | 'passwords' | 'shields' | 'profiles' | 'extensions' | null
  const [sidebarTab, setSidebarTab] = useState<
    "ai" | "menu" | "downloads" | "bookmarks" | "history" | "passwords" | "shields" | "profiles" | "extensions" | null
  >("ai");

  // Extensions State
  const [extensions, setExtensions] = useState<InstalledExtension[]>([]);
  const [extensionPathInput, setExtensionPathInput] = useState<string>("");
  const [isInstallingExtension, setIsInstallingExtension] = useState<boolean>(false);

  // Profiles, Bookmarks, History, Passwords & Downloads
  const [profiles, setProfiles] = useState<BrowserProfile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<string>("default");
  const [bookmarks, setBookmarks] = useState<BookmarkItem[]>(() => {
    try {
      const saved = localStorage.getItem("matrioshai_bookmarks");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [history, setHistory] = useState<HistoryEntry[]>(() => {
    try {
      const saved = localStorage.getItem("matrioshai_history");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [passwords, setPasswords] = useState<PasswordEntry[]>(() => {
    try {
      const saved = localStorage.getItem("matrioshai_passwords");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [pendingApproval, setPendingApproval] = useState<{
    tabId?: string; // absent for goal-mode approvals (the harness executes after resolution)
    action: string;
    target?: string;
    value?: string;
    description: string;
    riskLevel: string;
    resolve?: (approved: boolean) => void; // goal-mode approval bridge
  } | null>(null);
  const [actionLogs, setActionLogs] = useState<Array<{ id: string; action: string; desc: string; time: string; status: "success" | "error" | "pending" }>>([]);
  const [chatMessages, setChatMessages] = useState<Array<{ id: string; role: "user" | "assistant"; content: string; time: string }>>([
    {
      id: "init_1",
      role: "assistant",
      content: "Hello! I am your **Matrioshai Browser AI Copilot**. You can ask me to summarize the current webpage, extract data, analyze links, or give me autonomous multi-step goals like *'Find the cheapest flight from Delhi to Munich'*, *'Search for an RTX 5090 and compare options'*, or *'Plan a 7-day trip to Japan'*.",
      time: new Date().toLocaleTimeString(),
    },
  ]);

  const [activeAgentTask, setActiveAgentTask] = useState<AgentTask | null>(null);
  const [agentActionDesc, setAgentActionDesc] = useState<string>("");
  const [showDebugPanel, setShowDebugPanel] = useState<boolean>(false);
  const [inspectionDebug, setInspectionDebug] = useState<{
    url: string;
    title: string;
    elementsCount: number;
    linksCount: number;
    buttonsCount: number;
    inputsCount: number;
    visibleCount: number;
    timestamp: string;
  } | null>(null);
  const [diagnosticResult, setDiagnosticResult] = useState<{
    title: string;
    body_text_len: number;
    elements_count: number;
    custom_js_result: string;
    status: string;
  } | null>(null);

  useEffect(() => {
    const unsub = BrowserTaskManager.getInstance().subscribe((task, desc) => {
      setActiveAgentTask(task);
      if (desc) setAgentActionDesc(desc);
    });
    return unsub;
  }, []);

  // UNIFIED AGENT RUNTIME wiring: chat sink, approval gate and tab-creation
  // bridges are UI-owned capabilities injected into the harness once.
  useEffect(() => {
    const harness = BrowserAgentHarness.getInstance();

    harness.setMessageSink((text) => {
      setChatMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", content: text, time: new Date().toLocaleTimeString() },
      ]);
    });

    harness.setApprovalBridge((req) =>
      new Promise<boolean>((resolve) => {
        setPendingApproval({
          action: req.action,
          target: req.target ?? undefined,
          value: req.value ?? undefined,
          description: req.description,
          riskLevel: "High",
          resolve,
        });
      })
    );

    harness.setCreateTabBridge(async (targetUrl) => {
      const newTabId = crypto.randomUUID();
      const bounds = calculateBounds();
      const targetProfile = activeProfileId === "private" ? "default" : activeProfileId;
      const newTab = await nativeBrowserService.createTab(newTabId, targetUrl, bounds, true, targetProfile);
      setActiveTabId(newTab.id || newTabId);
      setUrlInput(targetUrl);
      setLiveUrl(targetUrl);
      await refreshTabs();
      return newTab.id || newTabId;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [zoomLevel, setZoomLevel] = useState<number>(1.0);
  const activeTab = tabs.find((t) => t.id === activeTabId) || null;

  const containerRef = useRef<HTMLDivElement>(null);
  const activeTabIdRef = useRef<string | null>(null);
  activeTabIdRef.current = activeTabId;

  const isEditingAddressRef = useRef<boolean>(false);
  isEditingAddressRef.current = isEditingAddress;

  const initRanRef = useRef(false);

  const titlebarOffsetRef = useRef<number>(0);

  const MARGIN_TOP = 34;
  const MARGIN_SIDES = 4;
  const MARGIN_BOTTOM = 4;

  const calculateBounds = (): RectBounds => {
    if (!containerRef.current) return { x: 0, y: 0, width: 800, height: 600 };
    const rect = containerRef.current.getBoundingClientRect();
    return {
      x: Math.round(rect.left + MARGIN_SIDES),
      y: Math.round(rect.top + MARGIN_TOP),
      width: Math.max(100, Math.round(rect.width - MARGIN_SIDES * 2)),
      height: Math.max(100, Math.round(rect.height - MARGIN_BOTTOM)),
    };
  };

  const updateNativeBounds = async (tabId: string) => {
    const bounds = calculateBounds();
    try {
      await nativeBrowserService.updateBounds(tabId, bounds);
    } catch (e) {
      console.error("[BOUNDS UPDATE FAILED]", tabId, bounds, e);
    }
  };

  const refreshTabs = async () => {
    try {
      const nativeTabs = await nativeBrowserService.getAllTabs();
      setTabs(nativeTabs);
      const active = nativeTabs.find((t) => t.active);
      if (active) {
        setActiveTabId(active.id);
        if (!isEditingAddressRef.current) {
          setUrlInput(active.url);
        }
      } else if (nativeTabs.length > 0) {
        setActiveTabId(nativeTabs[0].id);
        if (!isEditingAddressRef.current) {
          setUrlInput(nativeTabs[0].url);
        }
      } else {
        setActiveTabId(null);
        if (!isEditingAddressRef.current) {
          setUrlInput("about:blank");
        }
      }

      const stats = await browserApi.getAdBlockStats().catch(() => null);
      if (stats) setAdBlockStats(stats);
    } catch (e) {
      console.error("Failed to refresh native tabs", e);
    }
  };

  useEffect(() => {
    if (initRanRef.current) return;
    initRanRef.current = true;

    const initBrowser = async () => {
      // Query titlebar / window content view offset from native window geometry
      try {
        const offset = await nativeBrowserService.getContentViewOffset();
        titlebarOffsetRef.current = offset;
      } catch (e) {
        // Fallback default 0
      }

      // let layout settle before first measurement
      await new Promise(requestAnimationFrame);

      try {
        const existing = await nativeBrowserService.getAllTabs();
        if (existing.length === 0) {
          const initialTabId = crypto.randomUUID();
          const bounds = calculateBounds();
          const tab = await nativeBrowserService.createTab(
            initialTabId,
            "https://matrioshai.local",
            bounds,
            true
          );
          setTabs([tab]);
          setActiveTabId(tab.id);
          setUrlInput(tab.url);
        } else {
          setTabs(existing);
          const active = existing.find((t) => t.active) || existing[0];
          setActiveTabId(active.id);
          setUrlInput(active.url);
          if (active.url !== "https://matrioshai.local" && active.url !== "about:blank") {
            nativeBrowserService.activateTab(active.id).catch(() => {});
            updateNativeBounds(active.id);
          }
        }
      } catch (e) {
        console.error("Error initializing native browser tabs", e);
      }
    };

    // Rehydrate history from durable SQLite backend on mount
    const fetchHistoryFromDb = () => {
      browserApi.listHistory(100).then((sqliteItems) => {
        if (sqliteItems && sqliteItems.length > 0) {
          const formatted: HistoryEntry[] = sqliteItems.map((item) => ({
            id: item.id,
            url: item.url,
            title: item.title,
            visitedAt: new Date(item.visited_at).getTime(),
          }));
          setHistory(formatted);
          localStorage.setItem("matrioshai_history", JSON.stringify(formatted));
        }
      }).catch(() => {});
    };

    fetchHistoryFromDb();
    initBrowser();

    // Listen for normalized browser navigation events
    let unlistenNav: (() => void) | null = null;
    nativeBrowserService.onNavigationStarted((event) => {
      setTabs((prev) =>
        prev.map((t) => {
          if (t.id === event.tab_id && event.navigation_generation >= t.navigation_generation) {
            return {
              ...t,
              url: event.url,
              title: event.title || t.title,
              loading: event.loading,
              can_go_back: event.can_go_back,
              can_go_forward: event.can_go_forward,
            };
          }
          return t;
        })
      );

      if (activeTabIdRef.current === event.tab_id && !isEditingAddressRef.current) {
        setUrlInput(event.url);
      }
      if (event.url && event.url !== "https://matrioshai.local" && event.url !== "about:blank") {
        recordHistory(event.url, event.title);
      }
    }).then((unlisten) => {
      unlistenNav = unlisten;
    });

    let unlistenUrlChanged: (() => void) | null = null;
    nativeBrowserService.onUrlChanged((event) => {
      if (event.url && event.url !== "https://matrioshai.local" && event.url !== "about:blank") {
        setTabs((prev) =>
          prev.map((t) => (t.id === event.tab_id || (!event.tab_id && t.active) ? { ...t, url: event.url, title: event.title || t.title, loading: false } : t))
        );
        if (!isEditingAddressRef.current) {
          setUrlInput(event.url);
        }
        recordHistory(event.url, event.title);
      }
    }).then((unlisten) => {
      unlistenUrlChanged = unlisten;
    });


    // NOTE: URL polling interval is in its own useEffect below (avoids React Strict Mode cleanup issue)

    const handleResize = () => {
      if (activeTabIdRef.current) {
        updateNativeBounds(activeTabIdRef.current);
      }
    };

    window.addEventListener("resize", handleResize);

    let resizeObserver: ResizeObserver | null = null;
    requestAnimationFrame(() => {
      if (containerRef.current) {
        resizeObserver = new ResizeObserver(() => {
          if (activeTabIdRef.current) {
            updateNativeBounds(activeTabIdRef.current);
          }
        });
        resizeObserver.observe(containerRef.current);
      }
    });

    const handleCustomNav = (e: any) => {
      const url = e.detail?.url;
      if (url && activeTabIdRef.current) {
        setUrlInput(url);
        const bounds = calculateBounds();
        nativeBrowserService.navigate(activeTabIdRef.current, url, bounds).then(() => refreshTabs());
      }
    };
    window.addEventListener("matrioshai:navigate", handleCustomNav);

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("matrioshai:navigate", handleCustomNav);
      if (resizeObserver) resizeObserver.disconnect();
      if (unlistenNav) unlistenNav();
      if (unlistenUrlChanged) unlistenUrlChanged();
      nativeBrowserService.hideAllWebviews().catch(() => {});
    };
  }, []);

  // ── URL Live-Polling ──────────────────────────────────────────────────────
  // Separate useEffect so React Strict Mode cleanup doesn't kill the interval.
  // Reads webview.url() directly from macOS WebKit every 300ms.
  useEffect(() => {
    let lastRecordedUrl = "";
    const syncInterval = setInterval(async () => {
      try {
        const tabId = activeTabIdRef.current;
        if (tabId) {
          const url = await nativeBrowserService.getTabLiveUrl(tabId);
          if (url && url !== "about:blank" && !url.startsWith("https://matrioshai.local")) {
            setLiveUrl(url);
            setTabs((prev) =>
              prev.map((t) => (t.id === tabId ? { ...t, url, loading: false } : t))
            );
            if (!isEditingAddressRef.current) {
              setUrlInput(url);
            }
            if (url !== lastRecordedUrl) {
              lastRecordedUrl = url;
              const hostTitle = url.replace(/^https?:\/\/(www\.)?/, "").split("/")[0];
              recordHistory(url, hostTitle);
            }
          }
        }
      } catch (err) {
        console.error("[LiveURL ERROR]", err);
      }
    }, 300);
    return () => clearInterval(syncInterval);
  }, []);

  // Re-sync history from SQLite whenever user opens history or menu panel
  useEffect(() => {
    if (sidebarTab === "history" || sidebarTab === "menu") {
      browserApi.listHistory(100).then((sqliteItems) => {
        if (sqliteItems && sqliteItems.length > 0) {
          const formatted: HistoryEntry[] = sqliteItems.map((item) => ({
            id: item.id,
            url: item.url,
            title: item.title,
            visitedAt: new Date(item.visited_at).getTime(),
          }));
          setHistory(formatted);
          localStorage.setItem("matrioshai_history", JSON.stringify(formatted));
        }
      }).catch(() => {});
    }
    if (sidebarTab === "extensions") {
      nativeBrowserService.getExtensions().then((exts) => {
        if (exts) setExtensions(exts);
      }).catch(() => {});
    }
    if (sidebarTab === "shields") {
      nativeBrowserService.getShieldStats(activeTabId || undefined).then((stats) => {
        if (stats) {
          setAdBlockStats({
            total_blocked: (stats.ads_blocked || 0) + (stats.trackers_blocked || 0),
            trackers_blocked: stats.trackers_blocked || 0,
            ads_blocked: stats.ads_blocked || 0,
            rules_loaded: stats.total_evaluated || 14850,
          });
        }
      }).catch(() => {});
    }
  }, [sidebarTab, activeTabId]);

  // Live suggestions query
  useEffect(() => {
    if (!isEditingAddress || !urlInput.trim() || urlInput.startsWith("http")) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      const res = await SearchEngineResolver.fetchSuggestions(urlInput);
      setSuggestions(res);
    }, 150);
    return () => clearTimeout(timer);
  }, [urlInput, isEditingAddress]);

  const handleTogglePin = async (e: React.MouseEvent, tabId: string) => {
    e.stopPropagation();
    const tab = tabs.find((t) => t.id === tabId);
    if (!tab) return;
    const newPinned = !tab.pinned;
    await nativeBrowserService.setTabPinned(tabId, newPinned);
    await refreshTabs();
  };

  const handleReopenLastClosedTab = async () => {
    try {
      const newId = crypto.randomUUID();
      const tab = await nativeBrowserService.reopenLastClosedTab(newId);
      if (tab) {
        setActiveTabId(tab.id);
        setUrlInput(tab.url);
        await refreshTabs();
      }
    } catch (e) {
      console.error("Failed to reopen closed tab", e);
    }
  };

  const handleZoom = async (delta: number) => {
    if (!activeTabId) return;
    const newZoom = Math.min(2.0, Math.max(0.5, Math.round((zoomLevel + delta) * 10) / 10));
    setZoomLevel(newZoom);
    await nativeBrowserService.setZoom(activeTabId, newZoom);
  };

  const handlePrint = async () => {
    if (!activeTabId) return;
    await nativeBrowserService.print(activeTabId);
  };

  const handleAddBookmark = (title: string, url: string, folder?: string) => {
    const newItem: BookmarkItem = {
      id: crypto.randomUUID(),
      title: title || url,
      url,
      folder,
      createdAt: Date.now(),
    };
    const updated = [newItem, ...bookmarks];
    setBookmarks(updated);
    localStorage.setItem("matrioshai_bookmarks", JSON.stringify(updated));
  };

  const handleDeleteBookmark = (id: string) => {
    const updated = bookmarks.filter((b) => b.id !== id);
    setBookmarks(updated);
    localStorage.setItem("matrioshai_bookmarks", JSON.stringify(updated));
  };

  const recordHistory = (url: string, title: string) => {
    if (url === "https://matrioshai.local" || url === "about:blank") return;

    // Strict Privacy: Never record history for Private or Guest profiles
    const activeProfile = profiles.find((p) => p.id === activeProfileId);
    const isPrivate = activeProfile?.profile_type === "PRIVATE" || activeProfile?.profile_type === "GUEST" || activeProfileId === "private";
    if (isPrivate) {
      return;
    }

    const entry: HistoryEntry = {
      id: crypto.randomUUID(),
      url,
      title: title || url,
      visitedAt: Date.now(),
    };
    const updated = [entry, ...history.filter((h) => h.url !== url).slice(0, 100)];
    setHistory(updated);
    localStorage.setItem("matrioshai_history", JSON.stringify(updated));
    window.dispatchEvent(new CustomEvent("matrioshai:history-updated"));

    // Save to SQLite backend asynchronously with profile tag
    browserApi.recordHistory(url, title || url, activeProfileId, false).catch(() => {});
  };

  const handleSelectTab = async (tabId: string) => {
    if (tabId === activeTabId) return;
    setIsEditingAddress(false);
    try {
      const activated = await nativeBrowserService.activateTab(tabId);
      setActiveTabId(activated.id);
      const tabUrl = activated.url !== "https://matrioshai.local" ? activated.url : "";
      setUrlInput(activated.url);
      setLiveUrl(tabUrl);  // Reset to the tab's stored URL; polling will update to live URL
      await refreshTabs();
      updateNativeBounds(activated.id);
    } catch (e) {
      console.error("Failed to activate tab", e);
    }
  };

  const handleNewTab = async (isPrivate: boolean = false) => {
    setIsEditingAddress(false);
    setLiveUrl("");  // Clear address bar immediately for new tab
    try {
      const newTabId = crypto.randomUUID();
      const bounds = calculateBounds();
      const targetProfile = isPrivate ? "private" : (activeProfileId === "private" ? "default" : activeProfileId);
      setActiveProfileId(targetProfile);
      const newTab = await nativeBrowserService.createTab(
        newTabId,
        "https://matrioshai.local",
        bounds,
        true,
        targetProfile
      );
      setActiveTabId(newTab.id);
      setUrlInput("");  // Empty address bar for new tab
      await refreshTabs();
    } catch (e) {
      console.error("Failed to create tab", e);
    }
  };

  const handleCloseTab = async (e: React.MouseEvent, tabId: string) => {
    e.stopPropagation();
    try {
      const nextActive = await nativeBrowserService.closeTab(tabId);
      if (nextActive) {
        setActiveTabId(nextActive);
      }
      await refreshTabs();
      if (nextActive) {
        updateNativeBounds(nextActive);
      }
    } catch (e) {
      console.error("Failed to close tab", e);
    }
  };

  const handleDuplicateTab = async (e: React.MouseEvent, tabId: string) => {
    e.stopPropagation();
    setIsEditingAddress(false);
    try {
      const newTabId = crypto.randomUUID();
      const dup = await nativeBrowserService.duplicateTab(tabId, newTabId);
      setActiveTabId(dup.id);
      setUrlInput(dup.url);
      setLiveUrl(dup.url);
      await refreshTabs();
      updateNativeBounds(dup.id);
    } catch (e) {
      console.error("Failed to duplicate tab", e);
    }
  };

  const handleNavigate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTabId || !urlInput) return;

    setIsEditingAddress(false);
    const targetUrl = SearchEngineResolver.resolve(urlInput, searchEngine);

    // Measure bounds RIGHT NOW before any state changes
    const currentBounds = calculateBounds();

    try {
      // First update stored bounds in Rust, THEN navigate
      await nativeBrowserService.navigate(activeTabId, targetUrl, currentBounds);
      setUrlInput(targetUrl);
      setLiveUrl(targetUrl);
      
      const tabIdSnapshot = activeTabId;
      [50, 200, 500].forEach((delay) => {
        setTimeout(() => updateNativeBounds(tabIdSnapshot), delay);
      });
      await refreshTabs();
    } catch (err: any) {
      alert(err.message || "Failed to navigate.");
    }
  };

  const handleBack = () => {
    if (activeTabId) nativeBrowserService.goBack(activeTabId).catch(() => {});
  };

  const handleForward = () => {
    if (activeTabId) nativeBrowserService.goForward(activeTabId).catch(() => {});
  };

  const handleReloadOrStop = () => {
    if (!activeTabId) return;
    if (activeTab?.loading) {
      nativeBrowserService.stopLoading(activeTabId)
        .then(() => setTabs((prev) => prev.map((t) => t.id === activeTabId ? { ...t, loading: false } : t)))
        .catch(() => {});
    } else {
      nativeBrowserService.reload(activeTabId)
        .then(() => setTabs((prev) => prev.map((t) => t.id === activeTabId ? { ...t, loading: true } : t)))
        .catch(() => {});
    }
  };

  /**
 * DEBUG/TEST ONLY — NOT the canonical execution path.
 *
 * Used exclusively by the AI sidebar's interactive "Click" / "Type" test buttons
 * (triggered via handleSendToAI when action starts with "Click " or "Type ").
 *
 * The canonical production execution path is:
 *   BrowserTaskManager.startGoal() → BrowserAgentHarness.executeGoal()
 *   → harness.executeAction() → nativeBrowserService.executeAIAction() + ActionVerifier
 *
 * This function duplicates execute→verify logic for manual element testing only.
 * It MUST NOT be called from any autonomous/goal-driven code path.
 * Test 15 (e2e_agent_validation.test.ts) guards against production references.
 */
const handleExecuteAction = async (actionName: string, targetElId?: string, valueText?: string, userApproved: boolean = false) => {
    if (!activeTabId) return;
    try {
      // 1. Capture before state
      const beforeSem = await nativeBrowserService.inspectPage(activeTabId);

      const res = await nativeBrowserService.executeAIAction(activeTabId, actionName, targetElId, valueText, userApproved);
      if (res.approval_required) {
        setPendingApproval({
          tabId: activeTabId,
          action: actionName,
          target: targetElId,
          value: valueText,
          description: (res.data as any)?.description || `${actionName} on ${targetElId || "element"}`,
          riskLevel: res.risk_level,
        });
      } else {
        setPendingApproval(null);

        // 2. Wait for page layout & navigation stabilization
        await new Promise((r) => setTimeout(r, 800));

        // 3. Capture after state & verify transition
        const afterSem = await nativeBrowserService.inspectPage(activeTabId);
        const beforeSnap = {
          url: beforeSem.url,
          title: beforeSem.title,
          headings: beforeSem.headings || [],
          text_blocks: beforeSem.text_blocks || [],
          interactive_elements: beforeSem.interactive_elements || [],
          forms_count: beforeSem.forms_count || 0,
          tables_count: beforeSem.tables_count || 0,
          links_count: beforeSem.links_count || 0,
          timestamp: new Date().toISOString(),
        };
        const afterSnap = {
          url: afterSem.url,
          title: afterSem.title,
          headings: afterSem.headings || [],
          text_blocks: afterSem.text_blocks || [],
          interactive_elements: afterSem.interactive_elements || [],
          forms_count: afterSem.forms_count || 0,
          tables_count: afterSem.tables_count || 0,
          links_count: afterSem.links_count || 0,
          timestamp: new Date().toISOString(),
        };

        const verification = ActionVerifier.verifyTransition(actionName, targetElId, beforeSnap as any, afterSnap as any);

        const logEntry = {
          id: crypto.randomUUID(),
          action: actionName,
          desc: verification.success
            ? `${actionName} ${targetElId ? `on [${targetElId}]` : ""}: ${verification.message}`
            : `Failed: ${verification.message}`,
          time: new Date().toLocaleTimeString(),
          status: (verification.success ? "success" : "error") as "success" | "error",
        };
        setActionLogs((prev) => [logEntry, ...prev.slice(0, 20)]);
        setChatMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: verification.success
              ? `✓ **Action Verified:** ${verification.message}`
              : `❌ **Action Failed:** ${verification.message}`,
            time: new Date().toLocaleTimeString(),
          },
        ]);
      }
    } catch (e: any) {
      const logEntry = {
        id: crypto.randomUUID(),
        action: actionName,
        desc: `Failed: ${e.message || e}`,
        time: new Date().toLocaleTimeString(),
        status: "error" as const,
      };
      setActionLogs((prev) => [logEntry, ...prev.slice(0, 20)]);
      setChatMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `❌ **Action Failed:** ${e.message || e}`,
          time: new Date().toLocaleTimeString(),
        },
      ]);
    }
  };

  const handleRunDiagnosticCheck = async () => {
    if (!activeTabId) return;
    try {
      const res = await nativeBrowserService.debugEval(activeTabId, "document.querySelectorAll('*').length.toString()");
      setDiagnosticResult(res);
      console.log("[DIAGNOSTIC_CHECK_RESULT]", res);
    } catch (e: any) {
      console.error("[DIAGNOSTIC_CHECK_ERROR]", e);
    }
  };

  const handleApproveAction = async () => {
    if (!pendingApproval) return;
    // Goal-mode approvals: resolve the harness's promise; IT performs the
    // action through the verified executor (single execution path).
    if (pendingApproval.resolve) {
      const resolve = pendingApproval.resolve;
      setPendingApproval(null);
      setChatMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", content: "✓ **Approved** — resuming agent…", time: new Date().toLocaleTimeString() },
      ]);
      resolve(true);
      return;
    }
    const { tabId, action, target, value } = pendingApproval;
    if (!tabId) return;
    setPendingApproval(null);
    try {
      const res = await nativeBrowserService.executeAIAction(tabId, action, target, value, true);
      // Truthful reporting: the Rust executor now VERIFIES the interaction on
      // the live DOM before answering (res.success / res.data.verified). Only
      // show success when verification actually passed.
      const verified = res.success && (res.data as any)?.verified !== false;
      const logEntry = {
        id: crypto.randomUUID(),
        action,
        desc: verified
          ? `[Approved & Verified] ${action} ${target ? `on [${target}]` : ""}${value ? ` with "${value}"` : ""}`
          : `[Approved but NOT verified] ${action} ${target ? `on [${target}]` : ""}: ${res.message}`,
        time: new Date().toLocaleTimeString(),
        status: (verified ? "success" : "error") as "success" | "error",
      };
      setActionLogs((prev) => [logEntry, ...prev.slice(0, 20)]);
      setChatMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: verified
            ? `✓ **Approved & Verified:** ${res.message || "Action confirmed on live DOM."}`
            : `❌ **Approved but FAILED verification:** ${res.message}`,
          time: new Date().toLocaleTimeString(),
        },
      ]);
      // Refresh page state so DEBUG panel / AI context cannot diverge from
      // the WebView after an action.
      nativeBrowserService.inspectPage(tabId).catch(() => {});
    } catch (e: any) {
      setChatMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `⚠️ **Error executing approved action:** ${e.message || e}`,
          time: new Date().toLocaleTimeString(),
        },
      ]);
    }
  };

  const handleDenyAction = () => {
    if (!pendingApproval) return;
    if (pendingApproval.resolve) {
      const resolve = pendingApproval.resolve;
      setPendingApproval(null);
      setChatMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", content: "✕ **Denied** — asking the agent to find another way…", time: new Date().toLocaleTimeString() },
      ]);
      resolve(false);
      return;
    }
    const logEntry = {
      id: crypto.randomUUID(),
      action: pendingApproval.action,
      desc: `[Denied by User] ${pendingApproval.description}`,
      time: new Date().toLocaleTimeString(),
      status: "error" as const,
    };
    setActionLogs((prev) => [logEntry, ...prev.slice(0, 20)]);
    setPendingApproval(null);
    setChatMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `✕ **Action Cancelled:** Execution was denied by user.`,
        time: new Date().toLocaleTimeString(),
      },
    ]);
  };

  const handleAiAction = async (action: string) => {
    // Prevent giving another task if one is already running
    const isCurrentTaskRunning = loadingAi || (activeAgentTask && ["running", "paused"].includes(activeAgentTask.status));
    if (isCurrentTaskRunning) {
      setChatMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "⚠️ **Task in progress:** A task is currently executing. Please wait for it to complete or click **Stop** before starting a new task.",
          time: new Date().toLocaleTimeString(),
        },
      ]);
      return;
    }

    setLoadingAi(true);
    try {
      // Check if user clicked an interactive test action
      if (action.startsWith("Click ")) {
        const elId = action.split(" ")[1];
        await handleExecuteAction("CLICK", elId);
        return;
      } else if (action.startsWith("Type ")) {
        const parts = action.split(" ");
        const elId = parts[1];
        const val = parts.slice(2).join(" ");
        await handleExecuteAction("TYPE", elId, val);
        return;
      }

      // Add user's question to message list
      const userPrompt = action.startsWith("Custom Query: ") ? action.replace("Custom Query: ", "") : action;
      setChatMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "user",
          content: userPrompt,
          time: new Date().toLocaleTimeString(),
        },
      ]);

      // 1. Fetch real extracted DOM from native WKWebView via inspectPage
      // (refreshes the inspection DEBUG panel; the agent loop observes itself)
      const effectiveLiveUrl = liveUrl || activeTab?.url || urlInput;
      let title = activeTab?.title || "Current Page";
      let url = effectiveLiveUrl;
      let interactiveElements: any[] = [];
      let interactiveCount = 0;

      try {
        const sem = await nativeBrowserService.inspectPage(activeTabId || undefined);
        if (sem) {
          title = sem.title || title;
          url = sem.url || effectiveLiveUrl;
          interactiveElements = sem.interactive_elements || [];
          interactiveCount = interactiveElements.length;

          setInspectionDebug({
            url: sem.url,
            title: sem.title,
            elementsCount: interactiveCount,
            linksCount: sem.links_count || 0,
            buttonsCount: interactiveElements.filter((e) => e.role === "button" || e.tag === "button").length,
            inputsCount: sem.forms_count || 0,
            visibleCount: interactiveElements.filter((e) => e.visible !== false).length,
            timestamp: new Date().toLocaleTimeString(),
          });

          console.log("[NATIVE_BROWSER_INSPECT]", {
            tab: activeTabId,
            url: sem.url,
            title: sem.title,
            elements: interactiveCount,
            links: sem.links_count,
            sample_elements: interactiveElements.slice(0, 5),
            observation_status: sem.observation_status,
            observation_failed: sem.observation_failed,
          });
        }
      } catch (err) {
        console.warn("Native WKWebView inspection fallback", err);
      }

      // If title is generic, extract meaningful title from URL
      if ((!title || title === "Current Page" || title === "Webpage") && url && !url.includes("matrioshai.local")) {
        try {
          const parsed = new URL(url);
          const qParam = parsed.searchParams.get("q") || parsed.searchParams.get("query") || parsed.searchParams.get("k");
          if (qParam) {
            title = `${qParam} - Search Results`;
          } else {
            title = parsed.hostname;
          }
        } catch {}
      }

      // =====================================================================
      // UNIFIED AGENT RUNTIME — every prompt is an agent goal. The backend
      // step-reasoner decides each next action, the native verified executor
      // acts, and the harness verifies the expected effect before continuing.
      // (The former keyword gate → template planner, the direct ElementResolver
      // click shortcut, and the one-shot /ai-assist + tool_call path are gone.)
      // =====================================================================
      if (!activeTabId) {
        setChatMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: "assistant", content: "⚠️ No active browser tab — open a tab first.", time: new Date().toLocaleTimeString() },
        ]);
        return;
      }

      const taskManager = BrowserTaskManager.getInstance();
      const goalStr =
        action === "Research"
          ? `Research key findings on ${title}`
          : userPrompt.replace(/^Agent:\s*/i, "");

      // A run waiting on the user (ASK_USER answer or post-takeover) continues
      // the SAME task — it does not start a competing goal.
      if (taskManager.isGoalWaitingForUser()) {
        taskManager.provideUserAnswer(userPrompt, activeTabId);
        return;
      }

      await taskManager.startGoal(goalStr, activeTabId, [
        `Goal given while viewing: ${url}`,
      ]);
    } catch (e: any) {
      const rawMsg = e.message || "Failed to reach LLM";
      const isNetFail = rawMsg.toLowerCase().includes("load failed") || rawMsg.toLowerCase().includes("failed to fetch");
      const cleanMsg = isNetFail
        ? "Backend server is unreachable (127.0.0.1:8000). Please check your backend terminal."
        : rawMsg;

      setChatMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `⚠️ AI Assistant Error: ${cleanMsg}`,
          time: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setLoadingAi(false);
    }
  };

  return (
    <div style={{ flex: 1, height: "100%", display: "flex", overflow: "hidden", position: "relative" }}>
      {/* Main Browser Window */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", padding: "16px 20px" }}>
        
        {/* Top Tab Bar */}
        <div style={{ display: "flex", gap: "6px", alignItems: "center", marginBottom: "10px", overflowX: "auto" }}>
          {tabs.map((tab) => (
            <div
              key={tab.id}
              onClick={() => handleSelectTab(tab.id)}
              style={{
                background: tab.id === activeTabId ? "var(--bg-pill-hover)" : "var(--bg-card-secondary)",
                padding: tab.pinned ? "6px 8px" : "6px 12px",
                borderRadius: "var(--radius-pill)",
                fontSize: "12px",
                fontWeight: 600,
                color: tab.id === activeTabId ? "var(--text-primary)" : "var(--text-muted)",
                cursor: "pointer",
                border: "1px solid rgba(0, 0, 0, 0.06)",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                minWidth: tab.pinned ? "32px" : "110px",
                maxWidth: tab.pinned ? "40px" : "200px",
                height: "28px",
                justifyContent: tab.pinned ? "center" : "flex-start",
              }}
            >
              {tab.pinned ? (
                <button
                  onClick={(e) => handleTogglePin(e, tab.id)}
                  title="Unpin Tab"
                  style={{ background: "transparent", border: "none", cursor: "pointer", padding: 0 }}
                >
                  <Pin size={11} color="var(--accent-primary)" />
                </button>
              ) : (
                <>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, display: "flex", alignItems: "center", gap: "5px" }}>
                    {tab.profile_id === "private" && (
                      <span title="Private Tab" style={{ fontSize: "11px" }}>🕶️</span>
                    )}
                    <span>{tab.title || (tab.profile_id === "private" ? "Private Tab" : "New Tab")}</span>
                  </span>
                  
                  {/* Pin Action */}
                  <button
                    onClick={(e) => handleTogglePin(e, tab.id)}
                    title="Pin Tab"
                    style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 0 }}
                  >
                    <Pin size={10} />
                  </button>

                  {/* Duplicate Tab Action */}
                  <button
                    onClick={(e) => handleDuplicateTab(e, tab.id)}
                    title="Duplicate Tab"
                    style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 0 }}
                  >
                    <Copy size={10} />
                  </button>

                  {/* Close Tab Action */}
                  <button
                    onClick={(e) => handleCloseTab(e, tab.id)}
                    title="Close Tab"
                    style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 0 }}
                  >
                    <X size={11} />
                  </button>
                </>
              )}
            </div>
          ))}

          {/* New Tab Button */}
          <button
            onClick={() => handleNewTab(false)}
            title="New Tab"
            style={{
              background: "var(--bg-card-secondary)",
              border: "1px solid rgba(0, 0, 0, 0.06)",
              borderRadius: "50%",
              width: "26px",
              height: "26px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <Plus size={13} />
          </button>

          {/* Reopen Closed Tab Button */}
          <button
            onClick={handleReopenLastClosedTab}
            title="Reopen Closed Tab (Ctrl+Shift+T / Cmd+Shift+T)"
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "var(--text-muted)",
              padding: "4px",
            }}
          >
            <RotateCw size={11} />
          </button>
        </div>

        {/* Navigation Bar / Clean Brave Omnibox */}
        <div style={{ display: "flex", gap: "6px", alignItems: "center", marginBottom: "10px", position: "relative" }}>
          {/* Back, Forward, Reload */}
          <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
            <button
              className="action-btn"
              title="Back"
              style={{
                padding: "6px 8px",
                background: "var(--bg-card-secondary)",
                border: "1px solid rgba(0,0,0,0.06)",
                borderRadius: "var(--radius-pill)",
                color: "#1e293b",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              onClick={handleBack}
            >
              <ArrowLeft size={14} />
            </button>
            <button
              className="action-btn"
              title="Forward"
              style={{
                padding: "6px 8px",
                background: "var(--bg-card-secondary)",
                border: "1px solid rgba(0,0,0,0.06)",
                borderRadius: "var(--radius-pill)",
                color: "#1e293b",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              onClick={handleForward}
            >
              <ArrowRight size={14} />
            </button>
            <button
              className="action-btn"
              title={activeTab?.loading ? "Stop Loading" : "Reload Page"}
              style={{
                padding: "6px 8px",
                background: "var(--bg-card-secondary)",
                border: "1px solid rgba(0,0,0,0.06)",
                borderRadius: "var(--radius-pill)",
                color: activeTab?.loading ? "var(--status-red)" : "#1e293b",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              onClick={handleReloadOrStop}
            >
              {activeTab?.loading ? <Square size={13} fill="var(--status-red)" /> : <RotateCw size={14} />}
            </button>
          </div>

          {/* Clean Rounded Address Bar */}
          <form onSubmit={handleNavigate} style={{ flex: 1, display: "flex", position: "relative", minWidth: "200px" }}>
            <div
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background: "var(--bg-card-secondary)",
                borderRadius: "var(--radius-pill)",
                padding: "6px 14px",
                border: "1px solid rgba(0,0,0,0.06)",
                boxShadow: "inset 0 1px 2px rgba(0,0,0,0.02)",
              }}
            >
              {activeTab?.profile_id === "private" ? (
                <div style={{ display: "flex", alignItems: "center", gap: "4px", background: "rgba(139, 92, 246, 0.15)", color: "#7c3aed", padding: "2px 8px", borderRadius: "12px", fontSize: "10.5px", fontWeight: 700 }}>
                  <span>🕶️</span>
                  <span>Private</span>
                </div>
              ) : (
                <Lock size={12} color="#10b981" />
              )}
              <input
                type="text"
                value={isEditingAddress ? urlInput : (liveUrl || urlInput)}
                placeholder={activeTab?.profile_id === "private" ? "Search privately or enter address..." : "Search web or enter address..."}
                style={{
                  flex: 1,
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  fontSize: "12px",
                  color: "var(--text-primary)",
                  userSelect: "text",
                  WebkitUserSelect: "text",
                  cursor: "text",
                }}
                onFocus={(e) => {
                  setUrlInput(liveUrl || urlInput);
                  setIsEditingAddress(true);
                  e.target.select();
                }}
                onBlur={() => setTimeout(() => setIsEditingAddress(false), 200)}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleNavigate(e);
                  }
                }}
              />

              {/* Direct Reload Button inside Address Bar */}
              <button
                type="button"
                onClick={handleReloadOrStop}
                title={activeTab?.loading ? "Stop Loading" : "Reload"}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: activeTab?.loading ? "var(--status-red)" : "#475569",
                  padding: "4px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {activeTab?.loading ? <Square size={13} fill="var(--status-red)" /> : <RotateCw size={13} />}
              </button>

              {/* Copy URL Icon inside Address Bar */}
              <button
                type="button"
                onClick={async () => {
                  const targetToCopy = liveUrl || urlInput;
                  if (targetToCopy) {
                    await navigator.clipboard.writeText(targetToCopy);
                    alert(`✓ URL copied:\n${targetToCopy}`);
                  }
                }}
                title="Copy current URL"
                style={{ background: "transparent", border: "none", cursor: "pointer", color: "#475569", padding: "4px" }}
              >
                <Copy size={13} />
              </button>

              {/* Bookmark Icon inside Address Bar */}
              <button
                type="button"
                onClick={() => handleAddBookmark(activeTab?.title || urlInput, urlInput)}
                title="Bookmark this tab"
                style={{ background: "transparent", border: "none", cursor: "pointer", color: "#475569", padding: "4px" }}
              >
                <Bookmark size={13} />
              </button>

              {/* Shields Lion Icon inside Address Bar */}
              <button
                type="button"
                onClick={() => setSidebarTab(sidebarTab === "shields" ? null : "shields")}
                title="Matrioshai Shields"
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  color: "#f97316",
                  display: "flex",
                  alignItems: "center",
                  padding: "4px",
                }}
              >
                <Shield size={14} fill="#f97316" color="#f97316" />
              </button>
            </div>

            {/* Suggestions Autocomplete Dropdown */}
            {suggestions.length > 0 && isEditingAddress && (
              <div
                style={{
                  position: "absolute",
                  top: "38px",
                  left: 0,
                  right: 0,
                  background: "rgba(255, 255, 255, 0.98)",
                  backdropFilter: "blur(20px)",
                  borderRadius: "12px",
                  boxShadow: "0 8px 24px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.06)",
                  zIndex: 99999,
                  overflow: "hidden",
                  padding: "4px 0",
                }}
              >
                {suggestions.map((s, idx) => (
                  <div
                    key={idx}
                    onMouseDown={() => {
                      const target = SearchEngineResolver.resolve(s, searchEngine);
                      setUrlInput(target);
                      if (activeTabId) {
                        const bounds = calculateBounds();
                        nativeBrowserService.navigate(activeTabId, target, bounds).then(() => refreshTabs());
                      }
                    }}
                    style={{
                      padding: "8px 14px",
                      fontSize: "12px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      color: "var(--text-primary)",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-secondary)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <Sparkles size={11} color="var(--accent-primary)" />
                    <span>{s}</span>
                  </div>
                ))}
              </div>
            )}
          </form>

          {/* Right Toolbar: Extensions + AI Side Panel Toggle + Hamburger Menu */}
          <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
            {/* Extensions Manager Button */}
            <button
              className="action-btn"
              onClick={() => {
                setSidebarTab(sidebarTab === "extensions" ? null : "extensions");
                nativeBrowserService.getExtensions().then(setExtensions).catch(() => {});
              }}
              title="Extensions Manager"
              style={{
                padding: "6px 8px",
                background: sidebarTab === "extensions" ? "var(--bg-pill-hover)" : "transparent",
                border: "none",
                borderRadius: "var(--radius-pill)",
                color: sidebarTab === "extensions" ? "var(--accent-primary)" : "var(--text-primary)",
              }}
            >
              <Puzzle size={14} />
            </button>

            {/* AI Side Panel Trigger */}
            <button
              className="action-btn"
              onClick={() => setSidebarTab(sidebarTab === "ai" ? null : "ai")}
              title="Toggle AI Sidebar"
              style={{
                padding: "6px 8px",
                background: sidebarTab === "ai" ? "var(--bg-pill-hover)" : "transparent",
                border: "none",
                borderRadius: "var(--radius-pill)",
                color: sidebarTab === "ai" ? "var(--accent-primary)" : "var(--text-primary)",
              }}
            >
              <Sparkles size={14} />
            </button>

            {/* Brave Hamburger Menu Trigger */}
            <button
              className="action-btn"
              onClick={() => setSidebarTab(sidebarTab === "menu" ? null : "menu")}
              title="Customize and control Matrioshai Browser"
              style={{
                padding: "6px 8px",
                background: sidebarTab === "menu" ? "var(--bg-pill-hover)" : "transparent",
                border: "none",
                borderRadius: "var(--radius-pill)",
                color: "var(--text-primary)",
              }}
            >
              <Menu size={15} />
            </button>
          </div>
        </div>

        {/* Search Engine Selector Bar */}
        {showSettings && (
          <div
            style={{
              background: "var(--bg-card-secondary)",
              borderRadius: "14px",
              padding: "12px 18px",
              marginBottom: "12px",
              border: "1px solid var(--border-light)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              boxShadow: "0 4px 12px rgba(0,0,0,0.06)",
            }}
          >
            <div>
              <div style={{ fontSize: "13px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "4px" }}>
                Default Search Engine
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                Choose which search provider processes queries typed into the address bar.
              </div>
            </div>

            <div style={{ display: "flex", gap: "8px" }}>
              {[
                { id: "google", label: "Google" },
                { id: "bing", label: "Bing" },
                { id: "duckduckgo", label: "DuckDuckGo" },
                { id: "brave", label: "Brave Search" },
                { id: "startpage", label: "Startpage" },
                { id: "ecosia", label: "Ecosia" },
              ].map((engine) => (
                <button
                  key={engine.id}
                  onClick={() => {
                    setSearchEngine(engine.id as any);
                    setShowSettings(false);
                  }}
                  style={{
                    background: searchEngine === engine.id ? "var(--accent-primary)" : "#ffffff",
                    color: searchEngine === engine.id ? "#ffffff" : "var(--text-primary)",
                    border: "1px solid var(--border-light)",
                    borderRadius: "var(--radius-pill)",
                    padding: "6px 14px",
                    fontSize: "11px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  {engine.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Native Browser Viewport Container */}
        <div
          ref={containerRef}
          style={{
            flex: 1,
            background: "#ffffff",
            borderRadius: "14px",
            border: "none",
            display: "flex",
            flexDirection: "column",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {activeTab && (activeTab.url === "https://matrioshai.local" || activeTab.url === "about:blank") ? (
            activeTab.profile_id === "private" ? (
              /* Dedicated Private Window Dashboard */
              <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 20px", background: "linear-gradient(180deg, #18181b 0%, #09090b 100%)", color: "#f4f4f5" }}>
                <div style={{ width: "64px", height: "64px", borderRadius: "50%", background: "rgba(139, 92, 246, 0.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "32px", marginBottom: "16px", border: "1px solid rgba(139, 92, 246, 0.3)" }}>
                  🕶️
                </div>
                <div style={{ fontSize: "26px", fontWeight: 800, letterSpacing: "-0.5px", marginBottom: "6px", color: "#ffffff" }}>
                  You've gone Private
                </div>
                <div style={{ fontSize: "12.5px", color: "#a1a1aa", maxWidth: "460px", textAlign: "center", lineHeight: 1.5, marginBottom: "28px" }}>
                  Matrioshai won't remember the pages you visit, your search queries, or cookies after you close this window.
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", maxWidth: "480px", width: "100%", marginBottom: "28px" }}>
                  <div style={{ background: "rgba(255,255,255,0.05)", padding: "12px 14px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.08)" }}>
                    <div style={{ fontSize: "11.5px", fontWeight: 700, color: "#c084fc", marginBottom: "3px" }}>🔒 What Matrioshai does:</div>
                    <div style={{ fontSize: "10.5px", color: "#d4d4d8", lineHeight: 1.4 }}>
                      • Zero history saved<br />
                      • Cookies wiped on exit<br />
                      • Isolated temporary cache
                    </div>
                  </div>
                  <div style={{ background: "rgba(255,255,255,0.05)", padding: "12px 14px", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.08)" }}>
                    <div style={{ fontSize: "11.5px", fontWeight: 700, color: "#38bdf8", marginBottom: "3px" }}>🛡️ Active Protections:</div>
                    <div style={{ fontSize: "10.5px", color: "#d4d4d8", lineHeight: 1.4 }}>
                      • Strict Ad & Tracker Shield<br />
                      • Fingerprinting defense<br />
                      • YouTube Ad skip active
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", justifyContent: "center", maxWidth: "480px" }}>
                  {[
                    { name: "DuckDuckGo", url: "https://duckduckgo.com" },
                    { name: "Startpage", url: "https://www.startpage.com" },
                    { name: "Brave Search", url: "https://search.brave.com" },
                    { name: "Google", url: "https://www.google.com" },
                  ].map((site) => (
                    <button
                      key={site.name}
                      onClick={() => {
                        setUrlInput(site.url);
                        if (activeTabId) {
                          const currentBounds = calculateBounds();
                          nativeBrowserService.navigate(activeTabId, site.url, currentBounds).then(() => {
                            const tabIdSnapshot = activeTabId;
                            [50, 200, 500].forEach((delay) => {
                              setTimeout(() => updateNativeBounds(tabIdSnapshot), delay);
                            });
                            refreshTabs();
                          });
                        }
                      }}
                      style={{
                        background: "rgba(255,255,255,0.1)",
                        border: "1px solid rgba(255,255,255,0.15)",
                        borderRadius: "var(--radius-pill)",
                        padding: "8px 16px",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: "pointer",
                        color: "#ffffff",
                      }}
                    >
                      {site.name}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* Standard Start Page */
              <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 20px" }}>
                <div style={{ fontSize: "28px", fontWeight: 800, color: "var(--text-primary)", letterSpacing: "-0.5px", marginBottom: "8px" }}>
                  MATRIOSHAI BROWSER
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "24px" }}>
                  Privacy-First • Native Browser Engine • Synchronized Navigation
                </div>
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", justifyContent: "center", maxWidth: "480px" }}>
                  {[
                    { name: "Google", url: "https://www.google.com" },
                    { name: "Bing", url: "https://www.bing.com" },
                    { name: "DuckDuckGo", url: "https://duckduckgo.com" },
                    { name: "Wikipedia", url: "https://en.wikipedia.org" },
                    { name: "GitHub", url: "https://github.com" },
                  ].map((site) => (
                    <button
                      key={site.name}
                      onClick={() => {
                        setUrlInput(site.url);
                        if (activeTabId) {
                          const currentBounds = calculateBounds();
                          nativeBrowserService.navigate(activeTabId, site.url, currentBounds).then(() => {
                            const tabIdSnapshot = activeTabId;
                            [50, 200, 500].forEach((delay) => {
                              setTimeout(() => updateNativeBounds(tabIdSnapshot), delay);
                            });
                            refreshTabs();
                          });
                        }
                      }}
                      style={{
                        background: "var(--bg-card-secondary)",
                        border: "1px solid var(--border-light)",
                        borderRadius: "var(--radius-pill)",
                        padding: "8px 16px",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: "pointer",
                        color: "var(--text-primary)",
                      }}
                    >
                      {site.name}
                    </button>
                  ))}
                </div>
              </div>
            )
          ) : (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "13px" }}>
              Native Browser Viewport Active
            </div>
          )}
        </div>
      </div>

      {/* Universal Right Sidebar for AI, Menu, Downloads, Bookmarks, History, Passwords, Shields, Profiles */}
      {sidebarTab && (
        <div
          style={{
            width: "320px",
            height: "100%",
            background: "var(--bg-card-secondary)",
            borderLeft: "1px solid var(--border-light)",
            display: "flex",
            flexDirection: "column",
            padding: "16px 14px",
            justifyContent: "space-between",
            zIndex: 10,
          }}
        >
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", fontWeight: 700, textTransform: "capitalize" }}>
              {sidebarTab === "menu" && "Browser Menu"}
              {sidebarTab === "downloads" && "Downloads"}
              {sidebarTab === "bookmarks" && "Bookmarks"}
              {sidebarTab === "history" && "Browsing History"}
              {sidebarTab === "passwords" && "Passwords & Vault"}
              {sidebarTab === "shields" && "Privacy Shields"}
              {sidebarTab === "profiles" && "Profiles"}
              {sidebarTab === "ai" && "Browser AI Assistant"}
            </div>
            <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
              {sidebarTab !== "menu" && sidebarTab !== "ai" && (
                <button
                  onClick={() => setSidebarTab("menu")}
                  style={{ background: "transparent", border: "none", cursor: "pointer", fontSize: "11px", color: "var(--text-muted)", textDecoration: "underline" }}
                >
                  Back to Menu
                </button>
              )}
              <button
                onClick={() => setSidebarTab(null)}
                style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }}
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* VIEW: MAIN MENU */}
          {sidebarTab === "menu" && (
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ background: "#ffffff", borderRadius: "10px", padding: "6px 0", border: "1px solid var(--border-light)" }}>
                <div
                  onClick={() => {
                    handleNewTab();
                    setSidebarTab(null);
                  }}
                  style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between", cursor: "pointer", fontSize: "12px" }}
                >
                  <span>New Tab</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>⌘T</span>
                </div>
                <div
                  onClick={() => {
                    handleNewTab(true);
                    setSidebarTab(null);
                  }}
                  style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between", cursor: "pointer", fontSize: "12px", color: "#8b5cf6", fontWeight: 600 }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span>🕶️</span>
                    <span>New Private Window</span>
                  </div>
                  <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>⇧⌘N</span>
                </div>
              </div>

              <div style={{ background: "#ffffff", borderRadius: "10px", padding: "6px 0", border: "1px solid var(--border-light)" }}>
                <div
                  onClick={() => setSidebarTab("shields")}
                  style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between", cursor: "pointer", fontSize: "12px" }}
                >
                  <span>Matrioshai Shields</span>
                  <span style={{ color: "#10b981", fontWeight: 700 }}>{adBlockStats?.total_blocked || 0}</span>
                </div>
                <div
                  onClick={() => setSidebarTab("downloads")}
                  style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between", cursor: "pointer", fontSize: "12px" }}
                >
                  <span>Downloads</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>{downloads.length}</span>
                </div>
                <div
                  onClick={() => setSidebarTab("bookmarks")}
                  style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between", cursor: "pointer", fontSize: "12px" }}
                >
                  <span>Bookmarks</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>{bookmarks.length}</span>
                </div>
                <div
                  onClick={() => setSidebarTab("history")}
                  style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between", cursor: "pointer", fontSize: "12px" }}
                >
                  <span>History</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>{history.length}</span>
                </div>
                <div
                  onClick={() => setSidebarTab("passwords")}
                  style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between", cursor: "pointer", fontSize: "12px" }}
                >
                  <span>Passwords & Vault</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>{passwords.length}</span>
                </div>
                <div
                  onClick={() => setSidebarTab("profiles")}
                  style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between", cursor: "pointer", fontSize: "12px" }}
                >
                  <span>Profiles & Containers</span>
                </div>
              </div>

              {/* Zoom & Print */}
              <div style={{ background: "#ffffff", borderRadius: "10px", padding: "10px 12px", border: "1px solid var(--border-light)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <span style={{ fontSize: "12px", fontWeight: 600 }}>Zoom</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <button onClick={() => handleZoom(-0.1)} style={{ padding: "2px 6px", cursor: "pointer" }}>-</button>
                    <span style={{ fontSize: "11px", fontWeight: 700 }}>{Math.round(zoomLevel * 100)}%</span>
                    <button onClick={() => handleZoom(0.1)} style={{ padding: "2px 6px", cursor: "pointer" }}>+</button>
                  </div>
                </div>
                <div
                  onClick={() => {
                    handlePrint();
                    setSidebarTab(null);
                  }}
                  style={{ display: "flex", justifyContent: "space-between", cursor: "pointer", fontSize: "12px", paddingTop: "6px", borderTop: "1px solid var(--border-light)" }}
                >
                  <span>Print...</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>⌘P</span>
                </div>
              </div>
            </div>
          )}

          {/* VIEW: DOWNLOADS */}
          {sidebarTab === "downloads" && (
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px" }}>
              {downloads.length === 0 ? (
                <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-muted)", fontSize: "12px" }}>
                  No recent downloads.
                </div>
              ) : (
                downloads.map((d) => (
                  <div key={d.id} style={{ background: "#ffffff", padding: "10px", borderRadius: "10px", border: "1px solid var(--border-light)" }}>
                    <div style={{ fontWeight: 600, fontSize: "12px" }}>{d.filename}</div>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>{d.status}</div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* VIEW: DOWNLOADS */}
          {sidebarTab === "downloads" && (
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "10px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>Recent Files</span>
                {downloads.length > 0 && (
                  <button
                    onClick={() => setDownloads([])}
                    style={{ background: "transparent", border: "none", color: "var(--text-muted)", fontSize: "11px", cursor: "pointer", textDecoration: "underline" }}
                  >
                    Clear All
                  </button>
                )}
              </div>
              {downloads.length === 0 ? (
                <div style={{ textAlign: "center", padding: "32px 0", color: "var(--text-muted)", fontSize: "12px" }}>
                  <div style={{ fontSize: "20px", marginBottom: "6px" }}>📥</div>
                  No active or recent downloads.
                </div>
              ) : (
                downloads.map((d) => (
                  <div key={d.id} style={{ background: "#ffffff", padding: "10px 12px", borderRadius: "10px", border: "1px solid var(--border-light)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "12px", color: "var(--text-primary)" }}>{d.filename}</div>
                      <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>{d.status}</div>
                    </div>
                    <span style={{ fontSize: "11px", color: "#10b981", fontWeight: 700 }}>✓ Done</span>
                  </div>
                ))
              )}
            </div>
          )}

          {/* VIEW: BOOKMARKS */}
          {sidebarTab === "bookmarks" && (
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
              {/* Quick Add Current Tab */}
              <button
                onClick={() => handleAddBookmark(activeTab?.title || urlInput, urlInput)}
                style={{
                  background: "var(--accent-primary)",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "8px 12px",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "6px",
                  marginBottom: "4px",
                }}
              >
                <Bookmark size={12} />
                <span>Bookmark Current Tab</span>
              </button>

              {bookmarks.length === 0 ? (
                <div style={{ textAlign: "center", padding: "32px 0", color: "var(--text-muted)", fontSize: "12px" }}>
                  <div style={{ fontSize: "20px", marginBottom: "6px" }}>🔖</div>
                  No bookmarks saved yet.
                </div>
              ) : (
                bookmarks.map((b) => (
                  <div
                    key={b.id}
                    onClick={() => {
                      setUrlInput(b.url);
                      if (activeTabId) {
                        const bounds = calculateBounds();
                        nativeBrowserService.navigate(activeTabId, b.url, bounds).then(() => refreshTabs());
                      }
                    }}
                    style={{
                      background: "#ffffff",
                      padding: "10px 12px",
                      borderRadius: "10px",
                      border: "1px solid var(--border-light)",
                      cursor: "pointer",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, paddingRight: "8px" }}>
                      <div style={{ fontWeight: 600, fontSize: "12px", color: "var(--text-primary)" }}>{b.title}</div>
                      <div style={{ fontSize: "10px", color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis" }}>{b.url}</div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteBookmark(b.id);
                      }}
                      style={{ background: "transparent", border: "none", cursor: "pointer", color: "#ef4444", fontSize: "11px", padding: "2px 4px" }}
                    >
                      Delete
                    </button>
                  </div>
                ))
              )}
            </div>
          )}

          {/* VIEW: HISTORY */}
          {sidebarTab === "history" && (
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>{history.length} Visits Logged</span>
                <button
                  onClick={async () => {
                    setHistory([]);
                    localStorage.removeItem("matrioshai_history");
                    window.dispatchEvent(new CustomEvent("matrioshai:history-cleared"));
                    await browserApi.clearHistory().catch(() => {});
                  }}
                  style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444", border: "none", borderRadius: "6px", padding: "4px 8px", fontSize: "11px", cursor: "pointer" }}
                >
                  Clear All History
                </button>
              </div>
              {history.length === 0 ? (
                <div style={{ textAlign: "center", padding: "32px 0", color: "var(--text-muted)", fontSize: "12px" }}>
                  <div style={{ fontSize: "20px", marginBottom: "6px" }}>🕒</div>
                  No browsing history found.
                </div>
              ) : (
                history.map((h) => (
                  <div
                    key={h.id}
                    onClick={() => {
                      setUrlInput(h.url);
                      if (activeTabId) {
                        const bounds = calculateBounds();
                        nativeBrowserService.navigate(activeTabId, h.url, bounds).then(() => refreshTabs());
                      }
                    }}
                    style={{
                      background: "#ffffff",
                      padding: "8px 10px",
                      borderRadius: "8px",
                      border: "1px solid var(--border-light)",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: "12px", color: "var(--text-primary)" }}>{h.title}</div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{h.url}</div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* VIEW: PASSWORDS & AUTOFILL */}
          {sidebarTab === "passwords" && (
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "10px" }}>
              {/* Add New Password Form */}
              <div style={{ background: "#ffffff", padding: "12px", borderRadius: "10px", border: "1px solid var(--border-light)", display: "flex", flexDirection: "column", gap: "8px" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-primary)" }}>Add Credential to Vault</div>
                <input
                  id="vault-dom"
                  type="text"
                  placeholder="Website domain (e.g. google.com)"
                  style={{ padding: "6px 8px", fontSize: "11px", border: "1px solid var(--border-light)", borderRadius: "6px", outline: "none" }}
                />
                <input
                  id="vault-user"
                  type="text"
                  placeholder="Username or email"
                  style={{ padding: "6px 8px", fontSize: "11px", border: "1px solid var(--border-light)", borderRadius: "6px", outline: "none" }}
                />
                <input
                  id="vault-pass"
                  type="password"
                  placeholder="Password"
                  style={{ padding: "6px 8px", fontSize: "11px", border: "1px solid var(--border-light)", borderRadius: "6px", outline: "none" }}
                />
                <button
                  onClick={() => {
                    const domEl = document.getElementById("vault-dom") as HTMLInputElement;
                    const userEl = document.getElementById("vault-user") as HTMLInputElement;
                    const passEl = document.getElementById("vault-pass") as HTMLInputElement;
                    if (domEl?.value && userEl?.value && passEl?.value) {
                      const newEntry: PasswordEntry = {
                        id: crypto.randomUUID(),
                        domain: domEl.value,
                        username: userEl.value,
                        password: passEl.value,
                        createdAt: Date.now(),
                        lastUsedAt: Date.now(),
                      };
                      const updated = [newEntry, ...passwords];
                      setPasswords(updated);
                      localStorage.setItem("matrioshai_passwords", JSON.stringify(updated));
                      domEl.value = "";
                      userEl.value = "";
                      passEl.value = "";
                    }
                  }}
                  style={{ background: "var(--accent-primary)", color: "#ffffff", border: "none", padding: "6px", borderRadius: "6px", fontSize: "11px", fontWeight: 600, cursor: "pointer" }}
                >
                  Save Credential
                </button>
              </div>

              {/* Stored Credentials List */}
              <div style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-muted)" }}>Saved Logins ({passwords.length})</div>
              {passwords.length === 0 ? (
                <div style={{ textAlign: "center", padding: "20px 0", color: "var(--text-muted)", fontSize: "12px" }}>
                  No credentials saved in vault.
                </div>
              ) : (
                passwords.map((p) => (
                  <div key={p.id} style={{ background: "#ffffff", padding: "10px 12px", borderRadius: "10px", border: "1px solid var(--border-light)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "12px", color: "var(--text-primary)" }}>{p.domain}</div>
                      <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>{p.username}</div>
                    </div>
                    <button
                      onClick={() => {
                        const updated = passwords.filter((x) => x.id !== p.id);
                        setPasswords(updated);
                        localStorage.setItem("matrioshai_passwords", JSON.stringify(updated));
                      }}
                      style={{ background: "transparent", border: "none", color: "#ef4444", fontSize: "11px", cursor: "pointer" }}
                    >
                      Delete
                    </button>
                  </div>
                ))
              )}
            </div>
          )}

          {/* VIEW: SHIELDS */}
          {sidebarTab === "shields" && (
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "10px" }}>
              {/* Live Blocked Total Card */}
              <div style={{ background: "#ffffff", padding: "14px", borderRadius: "12px", border: "1px solid var(--border-light)", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
                <div style={{ fontSize: "32px", fontWeight: 800, color: "#10b981", marginBottom: "2px" }}>
                  {adBlockStats?.total_blocked || 0}
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>Total Trackers & Ads Blocked</div>
                <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginTop: "4px" }}>
                  Protected on: <code style={{ fontWeight: 600 }}>{liveUrl && !liveUrl.includes("matrioshai.local") ? new URL(liveUrl).hostname : "Current Site"}</code>
                </div>
              </div>

              {/* Detailed Breakdown */}
              <div style={{ background: "#ffffff", padding: "12px", borderRadius: "12px", border: "1px solid var(--border-light)", display: "flex", flexDirection: "column", gap: "8px" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-primary)" }}>Protection Breakdown</div>
                
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", background: "var(--bg-card-secondary)", padding: "6px 8px", borderRadius: "6px" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Cosmetic Ads Blocked</span>
                  <span style={{ fontWeight: 700, color: "#10b981" }}>{adBlockStats?.ads_blocked || 0}</span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", background: "var(--bg-card-secondary)", padding: "6px 8px", borderRadius: "6px" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Trackers Isolated</span>
                  <span style={{ fontWeight: 700, color: "#3b82f6" }}>{adBlockStats?.trackers_blocked || 0}</span>
                </div>
              </div>

              {/* Active Shield Capabilities */}
              <div style={{ background: "#ffffff", padding: "12px", borderRadius: "12px", border: "1px solid var(--border-light)", display: "flex", flexDirection: "column", gap: "8px" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-primary)" }}>Active Shields Protection</div>
                <div style={{ fontSize: "11px", color: "#10b981", display: "flex", alignItems: "center", gap: "6px" }}>
                  <span>●</span> <span>Brave-grade cosmetic ad-block</span>
                </div>
                <div style={{ fontSize: "11px", color: "#10b981", display: "flex", alignItems: "center", gap: "6px" }}>
                  <span>●</span> <span>YouTube video ad skip & dialog suppressor</span>
                </div>
                <div style={{ fontSize: "11px", color: "#10b981", display: "flex", alignItems: "center", gap: "6px" }}>
                  <span>●</span> <span>Fingerprinting & tracker isolation</span>
                </div>
              </div>
            </div>
          )}

          {/* VIEW: PROFILES & CONTAINERS */}
          {sidebarTab === "profiles" && (
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
              {/* Create Profile Button */}
              <button
                onClick={() => {
                  const name = prompt("Enter new profile name:");
                  if (name && name.trim()) {
                    const newP: BrowserProfile = {
                      id: crypto.randomUUID(),
                      name: name.trim(),
                      profile_type: "REGULAR",
                      storage_path: `profiles/${name.trim().toLowerCase()}`,
                      created_at: Date.now(),
                      last_used_at: Date.now(),
                      is_default: false,
                    };
                    setProfiles([...profiles, newP]);
                    setActiveProfileId(newP.id);
                  }
                }}
                style={{
                  background: "var(--accent-primary)",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "8px 12px",
                  fontSize: "11px",
                  fontWeight: 600,
                  cursor: "pointer",
                  marginBottom: "4px",
                }}
              >
                + Create New Profile
              </button>

              {(profiles.length > 0 ? profiles : [
                { id: "default", name: "Default Profile", profile_type: "REGULAR" as const, storage_path: "profiles/default", created_at: Date.now(), last_used_at: Date.now(), is_default: true },
                { id: "work", name: "Work Profile", profile_type: "REGULAR" as const, storage_path: "profiles/work", created_at: Date.now(), last_used_at: Date.now(), is_default: false },
              ]).map((p) => (
                <div
                  key={p.id}
                  onClick={() => setActiveProfileId(p.id)}
                  style={{
                    background: activeProfileId === p.id ? "rgba(59,130,246,0.08)" : "#ffffff",
                    border: activeProfileId === p.id ? "1.5px solid #3b82f6" : "1px solid var(--border-light)",
                    padding: "10px 12px",
                    borderRadius: "10px",
                    cursor: "pointer",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "12px", color: "var(--text-primary)" }}>{p.name}</div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>{p.profile_type}</div>
                  </div>
                  {activeProfileId === p.id && (
                    <span style={{ fontSize: "11px", color: "#3b82f6", fontWeight: 700 }}>Active</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* VIEW: EXTENSIONS */}
          {sidebarTab === "extensions" && (
            <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "12px" }}>
              {/* Chrome Web Store 1-Click Installer */}
              <div style={{ background: "#ffffff", padding: "14px", borderRadius: "10px", border: "1px solid var(--border-light)", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                  <div style={{ fontSize: "14px" }}>🛍️</div>
                  <div style={{ fontSize: "13px", fontWeight: 700 }}>Chrome Web Store Installer</div>
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "10px" }}>
                  Install any extension directly from Google Chrome Web Store.
                </div>

                {/* 1-Click Install Active Tab Extension */}
                {liveUrl && liveUrl.includes("chromewebstore.google.com/detail") && (
                  <button
                    disabled={isInstallingExtension}
                    onClick={async () => {
                      setIsInstallingExtension(true);
                      try {
                        const res = await browserApi.installWebstoreExtension(liveUrl);
                        if (res.status === "ok" && res.path) {
                          const ext = await nativeBrowserService.loadExtension(res.path);
                          setExtensions((prev) => [ext, ...prev.filter((e) => e.id !== ext.id)]);
                          alert(`✓ Successfully installed ${res.name || "extension"}!`);
                        } else {
                          alert(`Failed: ${res.message || "Could not download extension"}`);
                        }
                      } catch (err: any) {
                        alert(`Installation error: ${err.message || err}`);
                      } finally {
                        setIsInstallingExtension(false);
                      }
                    }}
                    style={{
                      width: "100%",
                      background: isInstallingExtension ? "#9ca3af" : "linear-gradient(135deg, #10b981, #059669)",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: "8px",
                      padding: "10px",
                      fontSize: "12px",
                      fontWeight: 700,
                      cursor: isInstallingExtension ? "not-allowed" : "pointer",
                      marginBottom: "10px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "6px",
                      boxShadow: "0 2px 4px rgba(16,185,129,0.2)",
                    }}
                  >
                    {isInstallingExtension ? "⏳ Downloading & Installing..." : "⚡ Add Current Extension to Matrioshai"}
                  </button>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  <input
                    type="text"
                    value={extensionPathInput}
                    onChange={(e) => setExtensionPathInput(e.target.value)}
                    placeholder="Paste Chrome Web Store URL or ID..."
                    style={{
                      width: "100%",
                      boxSizing: "border-box",
                      padding: "8px 10px",
                      fontSize: "11px",
                      border: "1px solid var(--border-light)",
                      borderRadius: "6px",
                      outline: "none",
                    }}
                  />
                  <button
                    disabled={isInstallingExtension}
                    onClick={async () => {
                      const target = extensionPathInput.trim() || liveUrl;
                      if (target) {
                        setIsInstallingExtension(true);
                        try {
                          const res = await browserApi.installWebstoreExtension(target);
                          if (res.status === "ok" && res.path) {
                            const ext = await nativeBrowserService.loadExtension(res.path);
                            setExtensions((prev) => [ext, ...prev.filter((e) => e.id !== ext.id)]);
                            setExtensionPathInput("");
                            alert(`✓ Successfully installed ${res.name || "extension"} from Chrome Web Store!`);
                          } else {
                            alert(`Failed: ${res.message || "Could not download extension"}`);
                          }
                        } catch (err: any) {
                          alert(`Installation error: ${err.message || err}`);
                        } finally {
                          setIsInstallingExtension(false);
                        }
                      }
                    }}
                    style={{
                      width: "100%",
                      background: isInstallingExtension ? "#9ca3af" : "var(--accent-primary)",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: "6px",
                      padding: "8px 12px",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: isInstallingExtension ? "not-allowed" : "pointer",
                      textAlign: "center",
                    }}
                  >
                    {isInstallingExtension ? "⏳ Downloading..." : "Install Extension"}
                  </button>
                </div>
              </div>

              {/* Unpacked Local Folder Loader */}
              <div style={{ background: "#ffffff", padding: "14px", borderRadius: "10px", border: "1px solid var(--border-light)" }}>
                <div style={{ fontSize: "12px", fontWeight: 700, marginBottom: "4px" }}>Load Unpacked Folder</div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "8px" }}>
                  Load developer extension folder with manifest.json
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  <input
                    type="text"
                    id="unpacked-ext-path"
                    placeholder="/path/to/unpacked_extension"
                    style={{
                      width: "100%",
                      boxSizing: "border-box",
                      padding: "8px 10px",
                      fontSize: "11px",
                      border: "1px solid var(--border-light)",
                      borderRadius: "6px",
                      outline: "none",
                    }}
                  />
                  <button
                    onClick={async () => {
                      const el = document.getElementById("unpacked-ext-path") as HTMLInputElement;
                      if (el && el.value.trim()) {
                        try {
                          const ext = await nativeBrowserService.loadExtension(el.value.trim());
                          setExtensions((prev) => [ext, ...prev.filter((e) => e.id !== ext.id)]);
                          el.value = "";
                          alert(`✓ Successfully loaded ${ext.name}!`);
                        } catch (err: any) {
                          alert(`Error loading extension: ${err.message || err}`);
                        }
                      }
                    }}
                    style={{
                      width: "100%",
                      background: "var(--bg-card-secondary)",
                      color: "var(--text-primary)",
                      border: "1px solid var(--border-light)",
                      borderRadius: "6px",
                      padding: "8px 12px",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: "pointer",
                      textAlign: "center",
                    }}
                  >
                    Load Unpacked
                  </button>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>Installed Extensions</span>
                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{extensions.length} active</span>
              </div>

              {extensions.length === 0 ? (
                <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-muted)", fontSize: "12px" }}>
                  <div style={{ fontSize: "20px", marginBottom: "6px" }}>🧩</div>
                  No extensions installed yet.
                </div>
              ) : (
                extensions.map((ext) => (
                  <div
                    key={ext.id}
                    style={{
                      background: "#ffffff",
                      padding: "12px",
                      borderRadius: "10px",
                      border: "1px solid var(--border-light)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <div style={{ fontSize: "18px" }}>🧩</div>
                        <div>
                          <div style={{ fontWeight: 700, fontSize: "12px", color: "var(--text-primary)" }}>{ext.name}</div>
                          <div style={{ fontSize: "10px", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "6px" }}>
                            <span>v{ext.version}</span>
                            <span>•</span>
                            <span style={{ color: ext.enabled ? "#10b981" : "#9ca3af", fontWeight: 600 }}>
                              {ext.enabled ? "● Active" : "○ Disabled"}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <label style={{ display: "flex", alignItems: "center", cursor: "pointer", fontSize: "11px", gap: "4px" }}>
                          <input
                            type="checkbox"
                            checked={ext.enabled}
                            onChange={async (e) => {
                              const checked = e.target.checked;
                              await nativeBrowserService.toggleExtension(ext.id, checked);
                              setExtensions((prev) =>
                                prev.map((item) => (item.id === ext.id ? { ...item, enabled: checked } : item))
                              );
                            }}
                            style={{ cursor: "pointer" }}
                          />
                        </label>

                        <button
                          type="button"
                          title="Uninstall extension"
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              setExtensions((prev) => prev.filter((item) => item.id !== ext.id));
                              await nativeBrowserService.removeExtension(ext.id);
                            } catch (err: any) {
                              console.error("Error removing extension:", err);
                            }
                          }}
                          style={{
                            background: "rgba(239, 68, 68, 0.1)",
                            border: "1px solid rgba(239, 68, 68, 0.2)",
                            cursor: "pointer",
                            padding: "4px 6px",
                            color: "#ef4444",
                            display: "flex",
                            alignItems: "center",
                            borderRadius: "6px",
                            fontSize: "10px",
                            fontWeight: 600,
                            gap: "3px",
                          }}
                        >
                          <X size={12} />
                          <span>Remove</span>
                        </button>
                      </div>
                    </div>

                    {ext.description && (
                      <div style={{ fontSize: "11px", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                        {ext.description}
                      </div>
                    )}

                    {/* Universal Dynamic Extension Capabilities */}
                    <div style={{ background: "var(--bg-card-secondary)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-light)", display: "flex", flexDirection: "column", gap: "8px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px" }}>
                        <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>Status:</span>
                        <span style={{ color: ext.enabled ? "#10b981" : "#9ca3af", fontWeight: 600, fontSize: "10.5px" }}>
                          {ext.enabled ? "● Active & Injected" : "○ Disabled"}
                        </span>
                      </div>

                      {/* Clean Supported Store / Domain Badges */}
                      {ext.content_scripts && ext.content_scripts.length > 0 && (() => {
                        const allMatches = ext.content_scripts.flatMap((cs) => cs.matches || []);
                        const hasAll = allMatches.some((m) => m === "<all_urls>" || m.includes("*/*"));
                        const domains = Array.from(
                          new Set(
                            allMatches
                              .map((m) => {
                                try {
                                  return m.replace(/^https?:\/\/(www\.)?/, "").split("/")[0].replace(/\*$/, "");
                                } catch {
                                  return "";
                                }
                              })
                              .filter((d) => d && d !== "*" && !d.includes("<all_urls>"))
                          )
                        );

                        return (
                          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                            <span style={{ fontSize: "10.5px", color: "var(--text-secondary)" }}>Active Stores & Origins:</span>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                              {hasAll && (
                                <span style={{ fontSize: "10px", background: "rgba(99, 102, 241, 0.1)", color: "var(--accent-primary)", padding: "2px 6px", borderRadius: "4px", fontWeight: 600 }}>
                                  🌐 All Websites
                                </span>
                              )}
                              {domains.slice(0, 5).map((dom, i) => (
                                <span key={i} style={{ fontSize: "10px", background: "#ffffff", padding: "2px 6px", borderRadius: "4px", border: "1px solid var(--border-light)", color: "var(--text-primary)", fontWeight: 500 }}>
                                  {dom}
                                </span>
                              ))}
                              {domains.length > 5 && (
                                <span style={{ fontSize: "9.5px", color: "var(--text-muted)", alignSelf: "center" }}>
                                  +{domains.length - 5} more
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })()}

                      {/* Permissions Summary */}
                      {ext.permissions && ext.permissions.length > 0 && (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                          {ext.permissions.slice(0, 4).map((p, i) => (
                            <span key={i} style={{ fontSize: "9px", background: "#ffffff", padding: "1px 5px", borderRadius: "3px", border: "1px solid var(--border-light)", color: "var(--text-muted)" }}>
                              {p}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div style={{ fontSize: "10px", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "4px" }}>
                      <span>✓</span> Scripts injected into active shopping tabs
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* VIEW: AI ASSISTANT */}
          {sidebarTab === "ai" && (
            <>
              {/* Quick Prompt Pills & Debug Toggle */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexShrink: 0 }}>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {["Summarize", "Research", "Extract", "Find"].map((act) => {
                    const isTaskBusy = loadingAi || (activeAgentTask && ["running", "paused"].includes(activeAgentTask.status));
                    return (
                      <button
                        key={act}
                        onClick={() => handleAiAction(act)}
                        disabled={!!isTaskBusy}
                        style={{
                          background: isTaskBusy ? "var(--bg-card-secondary)" : "#ffffff",
                          border: "1px solid var(--border-light)",
                          borderRadius: "var(--radius-pill)",
                          padding: "4px 10px",
                          fontSize: "11px",
                          fontWeight: 600,
                          cursor: isTaskBusy ? "not-allowed" : "pointer",
                          color: isTaskBusy ? "var(--text-muted)" : "var(--text-primary)",
                          opacity: isTaskBusy ? 0.6 : 1,
                          transition: "all 0.15s ease",
                        }}
                      >
                        {act}
                      </button>
                    );
                  })}
                </div>
                <button
                  onClick={() => setShowDebugPanel(!showDebugPanel)}
                  title="Toggle Native WKWebView Inspection Debug Panel"
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    background: showDebugPanel ? "#6b21a8" : "var(--bg-card-secondary)",
                    color: showDebugPanel ? "#ffffff" : "var(--text-muted)",
                    border: "1px solid var(--border-light)",
                    borderRadius: "4px",
                    padding: "3px 6px",
                    cursor: "pointer",
                  }}
                >
                  DEBUG
                </button>
              </div>

              {/* Native WKWebView Inspection Debug Panel */}
              {showDebugPanel && inspectionDebug && (
                <div
                  style={{
                    background: "#1e1e24",
                    color: "#f8f8f2",
                    borderRadius: "10px",
                    padding: "10px 12px",
                    fontSize: "10.5px",
                    fontFamily: "monospace",
                    marginBottom: "10px",
                    lineHeight: "1.5",
                    border: "1px solid #333",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                    <div style={{ fontWeight: 700, color: "#a78bfa" }}>Native WKWebView Inspection</div>
                    <button
                      onClick={handleRunDiagnosticCheck}
                      style={{
                        fontSize: "9.5px",
                        background: "#3b82f6",
                        color: "#fff",
                        border: "none",
                        borderRadius: "4px",
                        padding: "2px 6px",
                        cursor: "pointer",
                        fontWeight: 600,
                      }}
                    >
                      Run Diagnostic Check
                    </button>
                  </div>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <strong>URL:</strong> {inspectionDebug.url}
                  </div>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <strong>Title:</strong> {inspectionDebug.title}
                  </div>
                  <div>
                    <strong>DOM State:</strong> <span style={{ color: "#34d399" }}>READY</span>
                  </div>
                  <div>
                    <strong>Elements:</strong> {inspectionDebug.elementsCount} | <strong>Visible:</strong> {inspectionDebug.visibleCount}
                  </div>
                  <div>
                    <strong>Links:</strong> {inspectionDebug.linksCount} | <strong>Buttons:</strong> {inspectionDebug.buttonsCount} | <strong>Inputs:</strong> {inspectionDebug.inputsCount}
                  </div>
                  {diagnosticResult && (
                    <div style={{ marginTop: "6px", paddingTop: "6px", borderTop: "1px dashed #444", color: "#60a5fa" }}>
                      <div><strong>Diagnostic Title:</strong> {diagnosticResult.title}</div>
                      <div><strong>Body Text Length:</strong> {diagnosticResult.body_text_len} chars</div>
                      <div><strong>DOM Elements Count:</strong> {diagnosticResult.elements_count}</div>
                    </div>
                  )}
                  <div style={{ color: "#9ca3af", marginTop: "4px" }}>
                    Last Inspection: {inspectionDebug.timestamp} [SUCCESS]
                  </div>
                </div>
              )}

              {/* AGENT EXECUTION CARD — structured runtime panel fed by the
                  AgentEvent stream; never rendered as a chat message. */}
              {activeAgentTask && (
                <AgentExecutionCard task={activeAgentTask} currentAction={agentActionDesc} activeTabId={activeTabId} />
              )}

              {/* ChatGPT-Style Message Stream */}
              <div
                id="ai-chat-messages-container"
                className="no-scrollbar"
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                  overflowY: "auto",
                  paddingRight: "2px",
                  minHeight: "200px",
                  scrollbarWidth: "none",
                  msOverflowStyle: "none",
                }}
              >
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: msg.role === "user" ? "flex-end" : "flex-start",
                      width: "100%",
                      marginBottom: msg.role === "user" ? "8px" : "14px",
                    }}
                  >
                    {msg.role === "user" ? (
                      <div
                        style={{
                          maxWidth: "85%",
                          background: "#6b21a8",
                          color: "#ffffff",
                          padding: "10px 16px",
                          borderRadius: "18px",
                          fontSize: "12px",
                          lineHeight: 1.5,
                          fontWeight: 500,
                          wordBreak: "break-word",
                          boxShadow: "0 2px 8px rgba(107,33,168,0.2)",
                        }}
                      >
                        {msg.content}
                      </div>
                    ) : (
                      <div
                        style={{
                          width: "100%",
                          color: "var(--text-primary)",
                          fontSize: "12.5px",
                          lineHeight: 1.65,
                          padding: "0 2px",
                        }}
                      >
                        <ReactMarkdown
                          components={{
                            h1: ({ node, ...props }) => <h1 style={{ fontSize: "14px", fontWeight: 800, margin: "12px 0 6px 0", color: "var(--text-primary)" }} {...props} />,
                            h2: ({ node, ...props }) => <h2 style={{ fontSize: "13px", fontWeight: 700, margin: "10px 0 4px 0", color: "var(--text-primary)" }} {...props} />,
                            h3: ({ node, ...props }) => <h3 style={{ fontSize: "12px", fontWeight: 700, margin: "8px 0 3px 0", color: "var(--text-primary)" }} {...props} />,
                            p: ({ node, ...props }) => <p style={{ margin: "0 0 8px 0" }} {...props} />,
                            ul: ({ node, ...props }) => <ul style={{ paddingLeft: "16px", margin: "0 0 8px 0" }} {...props} />,
                            ol: ({ node, ...props }) => <ol style={{ paddingLeft: "16px", margin: "0 0 8px 0" }} {...props} />,
                            li: ({ node, ...props }) => <li style={{ marginBottom: "3px" }} {...props} />,
                            strong: ({ node, ...props }) => <strong style={{ fontWeight: 700, color: "var(--text-primary)" }} {...props} />,
                            code: ({ node, ...props }) => (
                              <code style={{ background: "rgba(0,0,0,0.06)", padding: "2px 6px", borderRadius: "4px", fontSize: "11px", fontFamily: "monospace" }} {...props} />
                            ),
                            pre: ({ node, ...props }) => (
                              <pre style={{ background: "#1e1e24", color: "#f8f8f2", padding: "10px", borderRadius: "8px", overflowX: "auto", fontSize: "11px", margin: "8px 0" }} {...props} />
                            ),
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                ))}

                {loadingAi && (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "10px 14px", background: "#ffffff", borderRadius: "14px 14px 14px 3px", border: "1px solid var(--border-light)", alignSelf: "flex-start", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                    <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#2563eb", animation: "pulse 1.5s infinite" }} />
                    <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 500 }}>
                      Thinking and reading page context...
                    </span>
                  </div>
                )}
              </div>

              {/* AI Input Box */}
              <div style={{ marginTop: "8px", flexShrink: 0 }}>
                {(() => {
                  const isTaskBusy = loadingAi || (activeAgentTask && ["running", "paused"].includes(activeAgentTask.status));
                  return (
                    <div
                      style={{
                        background: isTaskBusy ? "var(--bg-card-secondary)" : "#ffffff",
                        border: isTaskBusy ? "1.5px solid #d97706" : "1px solid var(--border-light)",
                        borderRadius: "12px",
                        padding: "8px 10px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                        transition: "all 0.2s ease",
                      }}
                    >
                      <textarea
                        value={assistantInput}
                        disabled={!!isTaskBusy}
                        onChange={(e) => setAssistantInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            if (assistantInput.trim() && !isTaskBusy) {
                              handleAiAction(`Custom Query: ${assistantInput}`);
                              setAssistantInput("");
                            }
                          }
                        }}
                        placeholder={
                          isTaskBusy
                            ? "⚠️ Task running in this tab... Please wait or click Stop."
                            : "Ask about this page... (Enter to send)"
                        }
                        rows={2}
                        style={{
                          width: "100%",
                          border: "none",
                          outline: "none",
                          resize: "none",
                          fontSize: "12px",
                          background: "transparent",
                          color: isTaskBusy ? "var(--text-muted)" : "var(--text-primary)",
                          cursor: isTaskBusy ? "not-allowed" : "text",
                        }}
                      />
                      {isTaskBusy ? (
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "#d97706", fontWeight: 600 }}>
                            <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", background: "#d97706" }} />
                            Task in progress...
                          </div>
                          <button
                            onClick={() => {
                              BrowserTaskManager.getInstance().stopAgent();
                              setLoadingAi(false);
                            }}
                            style={{
                              background: "#dc2626",
                              border: "none",
                              borderRadius: "6px",
                              padding: "5px 12px",
                              fontSize: "11px",
                              fontWeight: 600,
                              color: "#ffffff",
                              cursor: "pointer",
                            }}
                          >
                            Stop Task
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: "flex", justifyContent: "flex-end" }}>
                          <button
                            onClick={() => {
                              if (assistantInput.trim()) {
                                handleAiAction(`Custom Query: ${assistantInput}`);
                                setAssistantInput("");
                              }
                            }}
                            style={{
                              background: "#2563eb",
                              border: "none",
                              borderRadius: "6px",
                              padding: "5px 10px",
                              fontSize: "11px",
                              fontWeight: 600,
                              color: "#ffffff",
                              cursor: "pointer",
                            }}
                          >
                            Ask AI
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>

              {/* Pending Approval Dialog Card */}
              {pendingApproval && (
                <div
                  style={{
                    background: "rgba(245, 158, 11, 0.08)",
                    border: "1.5px solid #f59e0b",
                    borderRadius: "12px",
                    padding: "12px",
                    marginBottom: "12px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span style={{ fontSize: "14px" }}>⚠️</span>
                    <span style={{ fontSize: "12px", fontWeight: 700, color: "#b45309" }}>Action Approval Required</span>
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-primary)", lineHeight: 1.4 }}>
                    AI wants to execute <strong>{pendingApproval.action}</strong> on <em>{pendingApproval.description}</em>
                  </div>
                  <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                    <button
                      onClick={handleApproveAction}
                      style={{
                        flex: 1,
                        background: "#10b981",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "6px",
                        padding: "6px 10px",
                        fontSize: "11px",
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      ✓ Approve & Run
                    </button>
                    <button
                      onClick={handleDenyAction}
                      style={{
                        flex: 1,
                        background: "#ef4444",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "6px",
                        padding: "6px 10px",
                        fontSize: "11px",
                        fontWeight: 700,
                        cursor: "pointer",
                      }}
                    >
                      ✕ Deny
                    </button>
                  </div>
                </div>
              )}

              {/* Action Log History */}
              {actionLogs.length > 0 && (
                <div style={{ marginTop: "12px", background: "var(--bg-card-secondary)", borderRadius: "10px", padding: "10px", border: "1px solid var(--border-light)" }}>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-secondary)", marginBottom: "6px" }}>
                    Execution Action Log
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "120px", overflowY: "auto" }}>
                    {actionLogs.map((log) => (
                      <div key={log.id} style={{ fontSize: "10px", display: "flex", justifyContent: "space-between", color: log.status === "success" ? "#10b981" : "#ef4444" }}>
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "160px" }}>{log.desc}</span>
                        <span style={{ color: "var(--text-muted)", fontSize: "9px" }}>{log.time}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
