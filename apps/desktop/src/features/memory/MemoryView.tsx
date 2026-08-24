import React, { useState, useEffect } from "react";
import { Cpu, Search, Plus, Save, Trash2 } from "lucide-react";
import { memoryApi, MemorySearchResult } from "../../services/api/memory";

export const MemoryView: React.FC = () => {
  const [userPreferences, setUserPreferences] = useState<string>("");
  const [activeGoals, setActiveGoals] = useState<string>("");
  const [importantFacts, setImportantFacts] = useState<string>("");

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchResults, setSearchResults] = useState<MemorySearchResult[]>([]);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  // New Memory Modal State
  const [newContent, setNewContent] = useState<string>("");
  const [newTier, setNewTier] = useState<"RECALL" | "ARCHIVAL">("RECALL");

  const loadCoreMemory = async () => {
    try {
      const items = await memoryApi.getCore();
      items.forEach((m) => {
        if (m.source_type === "user_preferences") setUserPreferences(m.content);
        if (m.source_type === "active_goals") setActiveGoals(m.content);
        if (m.source_type === "important_facts") setImportantFacts(m.content);
      });
    } catch (err: any) {
      setStatusMsg(`Failed to load core memory: ${err.message}`);
    }
  };

  useEffect(() => {
    loadCoreMemory();
  }, []);

  const handleSaveCore = async () => {
    try {
      await memoryApi.setCore({
        user_preferences: userPreferences,
        active_goals: activeGoals,
        important_facts: importantFacts,
      });
      setStatusMsg("Core Memory facts updated successfully.");
      loadCoreMemory();
    } catch (err: any) {
      setStatusMsg(`Failed to save Core Memory: ${err.message}`);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const results = await memoryApi.search(searchQuery);
      setSearchResults(results);
    } catch (err: any) {
      setStatusMsg(`Search failed: ${err.message}`);
    }
  };

  const handleAddMemory = async () => {
    if (!newContent.trim()) return;
    try {
      await memoryApi.create({
        content: newContent,
        memory_tier: newTier,
      });
      setNewContent("");
      setStatusMsg(`Added memory item to ${newTier} tier.`);
      if (searchQuery) handleSearch();
    } catch (err: any) {
      setStatusMsg(`Add failed: ${err.message}`);
    }
  };

  const handleDeleteMemory = async (id: string) => {
    try {
      await memoryApi.delete(id);
      setSearchResults((prev) => prev.filter((item) => item.id !== id));
      setStatusMsg("Memory item deleted.");
    } catch (err: any) {
      setStatusMsg(`Delete failed: ${err.message}`);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "24px", overflowY: "auto", gap: "24px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <Cpu size={24} style={{ color: "var(--accent-primary)" }} />
        <div>
          <h2 style={{ fontSize: "18px", fontWeight: 700 }}>TIERED MEMORY FOUNDATION</h2>
          <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
            CORE Memory (Structured & always available), RECALL (Recent decisions/context), ARCHIVAL (Historical knowledge)
          </p>
        </div>
      </div>

      {statusMsg && (
        <div style={{ padding: "8px 14px", background: "var(--accent-light)", borderRadius: "6px", color: "var(--accent-primary)", fontSize: "13px" }}>
          {statusMsg}
        </div>
      )}

      {/* CORE MEMORY PANEL */}
      <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, letterSpacing: "0.5px" }}>CORE MEMORY</h3>
          <button className="new-chat-btn" onClick={handleSaveCore}>
            <Save size={14} />
            Save Core Memory
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div>
            <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
              User Preferences
            </label>
            <input
              type="text"
              placeholder="e.g. Concise responses, dark mode preferred, senior software engineer persona"
              value={userPreferences}
              onChange={(e) => setUserPreferences(e.target.value)}
              style={{
                width: "100%",
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-color)",
                color: "var(--text-primary)",
                padding: "8px 12px",
                borderRadius: "6px",
                fontSize: "13px",
                outline: "none",
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
              Active Goals
            </label>
            <input
              type="text"
              placeholder="e.g. Building MATRIOSHAI Core Phase 1 with Tauri and FastAPI"
              value={activeGoals}
              onChange={(e) => setActiveGoals(e.target.value)}
              style={{
                width: "100%",
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-color)",
                color: "var(--text-primary)",
                padding: "8px 12px",
                borderRadius: "6px",
                fontSize: "13px",
                outline: "none",
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
              Important Stable Facts
            </label>
            <input
              type="text"
              placeholder="e.g. Primary environment: macOS & Windows local-first"
              value={importantFacts}
              onChange={(e) => setImportantFacts(e.target.value)}
              style={{
                width: "100%",
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-color)",
                color: "var(--text-primary)",
                padding: "8px 12px",
                borderRadius: "6px",
                fontSize: "13px",
                outline: "none",
              }}
            />
          </div>
        </div>
      </div>

      {/* MEMORY SEARCH & ADD PANEL */}
      <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "12px" }}>RECALL & ARCHIVAL SEARCH</h3>
        
        <div style={{ display: "flex", gap: "10px", marginBottom: "16px" }}>
          <div className="global-search" style={{ margin: 0, flex: 1, maxWidth: "none" }}>
            <Search size={14} className="search-icon" />
            <input
              type="text"
              placeholder="Search recall and archival memory items..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>
          <button className="new-chat-btn" onClick={handleSearch}>
            Search
          </button>
        </div>

        {/* Add Memory Form */}
        <div style={{ display: "flex", gap: "10px", background: "var(--bg-tertiary)", padding: "10px", borderRadius: "6px", marginBottom: "16px" }}>
          <input
            type="text"
            placeholder="Add new recall or archival memory item..."
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            style={{ flex: 1, background: "transparent", border: "none", color: "var(--text-primary)", outline: "none" }}
          />
          <select
            value={newTier}
            onChange={(e) => setNewTier(e.target.value as any)}
            style={{ background: "var(--bg-secondary)", color: "var(--text-primary)", border: "1px solid var(--border-color)", borderRadius: "4px", padding: "0 8px" }}
          >
            <option value="RECALL">RECALL</option>
            <option value="ARCHIVAL">ARCHIVAL</option>
          </select>
          <button className="action-btn" onClick={handleAddMemory} title="Add Memory">
            <Plus size={16} />
          </button>
        </div>

        {/* Results */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {searchResults.map((item) => (
            <div
              key={item.id}
              style={{
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-color)",
                padding: "12px",
                borderRadius: "6px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <span
                  style={{
                    fontSize: "10px",
                    fontWeight: 800,
                    padding: "2px 6px",
                    borderRadius: "4px",
                    background: item.memory_tier === "RECALL" ? "var(--accent-light)" : "rgba(245, 158, 11, 0.2)",
                    color: item.memory_tier === "RECALL" ? "var(--accent-primary)" : "var(--status-amber)",
                    marginRight: "8px",
                  }}
                >
                  {item.memory_tier}
                </span>
                <span style={{ fontSize: "13px" }}>{item.content}</span>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                  Score: {item.relevance_score} | Source: {item.source_type}
                </div>
              </div>
              <button className="action-btn" onClick={() => handleDeleteMemory(item.id)} style={{ color: "var(--status-red)" }}>
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
