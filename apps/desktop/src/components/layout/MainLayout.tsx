import React, { useState, useEffect } from "react";
import { MessageSquare, Globe, Edit3, Link2, PanelLeftClose, PanelLeft } from "lucide-react";
import { ChatView } from "../../features/chat/ChatView";
import { NotesView } from "../../features/notes/NotesView";
import { BrowserView } from "../../features/browser/BrowserView";
import { SystemView } from "../../features/system/SystemView";
import { SecurityView } from "../../features/security/SecurityView";
import { SettingsView } from "../../features/settings/SettingsView";
import { Conversation } from "../../types";
import { conversationApi } from "../../services/api/conversations";
import { nativeBrowserService } from "../../services/browser/nativeService";
import { API_BASE_URL } from "../../services/api/client";

export type ViewTab = "chats" | "browser" | "notepad" | "account" | "system" | "security";

export const MainLayout: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ViewTab>("chats");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  // Real browsing history loaded from SQLite backend API & localStorage
  const [browserHistory, setBrowserHistory] = useState<Array<{ id: string; title: string; url: string; visitedAt: number }>>([]);

  const loadBrowserHistory = async () => {
    try {
      // 1. First check localStorage for immediate response
      const saved = localStorage.getItem("matrioshai_history");
      if (saved) {
        const parsed = JSON.parse(saved);
        setBrowserHistory(parsed.map((p: any) => ({
          id: p.id,
          title: p.title || p.url,
          url: p.url,
          visitedAt: p.visitedAt || (p.visited_at ? new Date(p.visited_at).getTime() : Date.now()),
        })));
      }

      // 2. Refresh from SQLite backend
      const resp = await fetch(`${API_BASE_URL}/browser/history?limit=50`);
      if (resp.ok) {
        const sqliteItems = await resp.json();
        if (Array.isArray(sqliteItems)) {
          const formatted = sqliteItems.map((item: any) => ({
            id: item.id,
            url: item.url,
            title: item.title,
            visitedAt: new Date(item.visited_at).getTime(),
          }));
          setBrowserHistory(formatted);
          localStorage.setItem("matrioshai_history", JSON.stringify(formatted));
        }
      }
    } catch {}
  };

  useEffect(() => {
    loadBrowserHistory();
    const interval = setInterval(loadBrowserHistory, 2000);

    const handleCleared = () => {
      setBrowserHistory([]);
      localStorage.removeItem("matrioshai_history");
    };

    const handleUpdated = () => {
      loadBrowserHistory();
    };

    window.addEventListener("matrioshai:history-cleared", handleCleared);
    window.addEventListener("matrioshai:history-updated", handleUpdated);

    return () => {
      clearInterval(interval);
      window.removeEventListener("matrioshai:history-cleared", handleCleared);
      window.removeEventListener("matrioshai:history-updated", handleUpdated);
    };
  }, []);

  const now = Date.now();
  const ONE_DAY = 24 * 60 * 60 * 1000;
  const SEVEN_DAYS = 7 * ONE_DAY;

  const todayWebHistory = browserHistory.filter((h) => now - h.visitedAt < ONE_DAY);
  const yesterdayWebHistory = browserHistory.filter((h) => now - h.visitedAt >= ONE_DAY && now - h.visitedAt < 2 * ONE_DAY);
  const olderWebHistory = browserHistory.filter((h) => now - h.visitedAt >= 2 * ONE_DAY && now - h.visitedAt < SEVEN_DAYS);

  useEffect(() => {
    if (activeTab !== "browser") {
      nativeBrowserService.hideAllWebviews().catch(() => {});
    }
  }, [activeTab]);

  const loadConversations = async () => {
    try {
      const list = await conversationApi.list();
      setConversations(list);
    } catch (e) {
      console.error("Failed to load conversations", e);
    }
  };

  const handleNewChat = () => {
    setActiveConversationId(null);
    setActiveTab("chats");
  };

  const handleConversationCreated = (convId: string) => {
    loadConversations();
    setActiveConversationId(convId);
  };

  return (
    <div className="matrioshai-app">
      {/* Floating Left Sidebar */}
      <aside className={`floating-sidebar ${sidebarOpen ? "" : "collapsed"}`}>
        {/* Header */}
        <div className="sidebar-header">
          <div className="logo-brand" onClick={() => handleNewChat()} style={{ cursor: "pointer" }}>
            {/* Matrioshai Abstract Brand Logo */}
            <svg width="22" height="22" viewBox="0 0 100 100" fill="none">
              <path d="M28 65C32.4183 65 36 61.4183 36 57C36 52.5817 32.4183 49 28 49C23.5817 49 20 52.5817 20 57C20 61.4183 23.5817 65 28 65Z" fill="black"/>
              <path d="M42 42C48.6274 42 54 36.6274 54 30C54 23.3726 48.6274 18 42 18C35.3726 18 30 23.3726 30 30C30 36.6274 35.3726 42 42 42Z" fill="black"/>
              <path d="M68 62C72.4183 62 76 58.4183 76 54C76 49.5817 72.4183 46 68 46C63.5817 46 60 49.5817 60 54C60 58.4183 63.5817 62 68 62Z" fill="black"/>
              <path d="M65 32C68.3137 32 71 29.3137 71 26C71 22.6863 68.3137 20 65 20C61.6863 20 59 22.6863 59 26C59 29.3137 61.6863 32 65 32Z" fill="black"/>
              <path d="M48 68C56 68 62 58 62 48C62 38 52 30 42 30C32 30 24 40 24 50C24 60 38 68 48 68Z" stroke="black" strokeWidth="12" strokeLinecap="round"/>
            </svg>
            <span>MATRIOSHAI</span>
          </div>

          <button
            className="sidebar-toggle-btn"
            onClick={() => setSidebarOpen(false)}
            title="Collapse Sidebar"
          >
            <PanelLeftClose size={16} />
          </button>
        </div>

        {/* Navigation Pills */}
        <div className="nav-pills">
          <div
            className={`nav-pill-item ${activeTab === "chats" && !activeConversationId ? "active" : ""}`}
            onClick={handleNewChat}
          >
            <MessageSquare size={15} />
            <span>New Chats</span>
          </div>

          <div
            className={`nav-pill-item ${activeTab === "browser" ? "active" : ""}`}
            onClick={() => setActiveTab("browser")}
          >
            <Globe size={15} />
            <span>Browser</span>
          </div>

          <div
            className={`nav-pill-item ${activeTab === "notepad" ? "active" : ""}`}
            onClick={() => setActiveTab("notepad")}
          >
            <Edit3 size={15} />
            <span>Notepad</span>
          </div>

          <div
            className={`nav-pill-item ${activeTab === "account" ? "active" : ""}`}
            onClick={() => setActiveTab("account")}
          >
            <Link2 size={15} />
            <span>Account Link</span>
          </div>
        </div>

        {/* Categorized History List */}
        <div className="history-section">
          {/* Today History */}
          <div>
            <div className="history-group-title">
              {activeTab === "browser" ? "Today Web-History" : activeTab === "notepad" ? "Today Note" : "Today Chats"}
            </div>
            <div className="history-items">
              {activeTab === "browser" ? (
                todayWebHistory.length > 0 ? (
                  todayWebHistory.slice(0, 6).map((h) => (
                    <div
                      key={h.id}
                      className="history-item"
                      title={h.url}
                      onClick={() => {
                        window.dispatchEvent(new CustomEvent("matrioshai:navigate", { detail: { url: h.url } }));
                      }}
                      style={{ cursor: "pointer" }}
                    >
                      {h.title || h.url}
                    </div>
                  ))
                ) : (
                  <div className="history-item" style={{ opacity: 0.5, cursor: "default" }}>No history today</div>
                )
              ) : (
                conversations.slice(0, 3).map((c) => (
                  <div
                    key={c.id}
                    className={`history-item ${activeConversationId === c.id ? "active" : ""}`}
                    onClick={() => {
                      setActiveConversationId(c.id);
                      setActiveTab("chats");
                    }}
                  >
                    {c.title || "New Conversation"}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Yesterday History */}
          <div>
            <div className="history-group-title">
              {activeTab === "browser" ? "Yesterday Web-History" : activeTab === "notepad" ? "Yesterday Note" : "Yesterday Chats"}
            </div>
            <div className="history-items">
              {activeTab === "browser" ? (
                yesterdayWebHistory.length > 0 ? (
                  yesterdayWebHistory.slice(0, 4).map((h) => (
                    <div
                      key={h.id}
                      className="history-item"
                      title={h.url}
                      onClick={() => {
                        window.dispatchEvent(new CustomEvent("matrioshai:navigate", { detail: { url: h.url } }));
                      }}
                      style={{ cursor: "pointer" }}
                    >
                      {h.title || h.url}
                    </div>
                  ))
                ) : (
                  <div className="history-item" style={{ opacity: 0.5, cursor: "default" }}>No history yesterday</div>
                )
              ) : (
                <div className="history-item" style={{ opacity: 0.5, cursor: "default" }}>No older chats</div>
              )}
            </div>
          </div>

          {/* 7days History */}
          <div>
            <div className="history-group-title">
              {activeTab === "browser" ? "7days Web-History" : activeTab === "notepad" ? "7days Note" : "7days Chats"}
            </div>
            <div className="history-items">
              {activeTab === "browser" ? (
                olderWebHistory.length > 0 ? (
                  olderWebHistory.slice(0, 4).map((h) => (
                    <div
                      key={h.id}
                      className="history-item"
                      title={h.url}
                      onClick={() => {
                        window.dispatchEvent(new CustomEvent("matrioshai:navigate", { detail: { url: h.url } }));
                      }}
                      style={{ cursor: "pointer" }}
                    >
                      {h.title || h.url}
                    </div>
                  ))
                ) : (
                  <div className="history-item" style={{ opacity: 0.5, cursor: "default" }}>No history this week</div>
                )
              ) : (
                <div className="history-item" style={{ opacity: 0.5, cursor: "default" }}>No weekly activity</div>
              )}
            </div>
          </div>
        </div>

        {/* User Profile Pill at Bottom */}
        <div className="sidebar-user-pill">
          <div className="user-avatar-rect" />
          <span className="user-name">Anurag</span>
        </div>
      </aside>

      {/* Main Stage Content Area */}
      <main className="main-stage-container">
        {/* Toggle icon button if collapsed */}
        {!sidebarOpen && (
          <button
            className="collapsed-sidebar-trigger"
            onClick={() => setSidebarOpen(true)}
            title="Expand Sidebar"
          >
            <PanelLeft size={16} />
          </button>
        )}

        {/* Active View Render */}
        {activeTab === "chats" && (
          <ChatView
            activeConversationId={activeConversationId}
            onConversationCreated={handleConversationCreated}
          />
        )}

        {activeTab === "browser" && <BrowserView />}

        {activeTab === "notepad" && <NotesView />}

        {activeTab === "account" && <SettingsView />}

        {activeTab === "system" && <SystemView />}

        {activeTab === "security" && <SecurityView />}

        {/* Bottom Right Floating Link Widget */}
        <div className="floating-link-widget" onClick={() => setActiveTab("account")}>
          <Link2 size={13} />
        </div>
      </main>
    </div>
  );
};
