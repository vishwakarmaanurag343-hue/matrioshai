import React, { useState, useEffect } from "react";
import { CheckCircle, Search, Zap, Layers } from "lucide-react";
import { orchestratorApi, DailyBriefing, GlobalSearchResult } from "../../services/api/orchestrator";

interface IntelligenceHomeViewProps {
  onNavigate: (tab: string) => void;
}

export const IntelligenceHomeView: React.FC<IntelligenceHomeViewProps> = ({ onNavigate }) => {
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<GlobalSearchResult[]>([]);

  useEffect(() => {
    loadBriefing();
  }, []);

  const loadBriefing = async () => {
    try {
      const data = await orchestratorApi.getDailyBriefing();
      setBriefing(data);
    } catch (e) {
      // transient load error
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    try {
      const res = await orchestratorApi.globalSearch(searchQuery.trim());
      setSearchResults(res.results);
    } catch (e) {
      // transient search error
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflowY: "auto", padding: "24px", gap: "20px" }}>
      {/* Top Banner: Greeting & System Status */}
      <div style={{ background: "linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(16, 185, 129, 0.1) 100%)", border: "1px solid var(--border-color)", borderRadius: "12px", padding: "20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <span style={{ fontSize: "11px", fontWeight: 700, padding: "2px 8px", borderRadius: "10px", background: "rgba(16, 185, 129, 0.2)", color: "var(--status-green)" }}>
            ● MATRIOSHAI OPERATING SYSTEM READY
          </span>
          <h1 style={{ fontSize: "22px", fontWeight: 800, marginTop: "8px" }}>
            {briefing?.greeting || "Good morning. MATRIOSHAI is online."}
          </h1>
          <div style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "4px" }}>
            Autonomous Multi-domain Personal AI Operating Layer
          </div>
        </div>

        {/* Global Search Bar */}
        <form onSubmit={handleSearch} style={{ display: "flex", alignItems: "center", gap: "8px", background: "var(--bg-secondary)", padding: "8px 14px", borderRadius: "8px", border: "1px solid var(--border-color)", width: "320px" }}>
          <Search size={16} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Global search across system..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ background: "transparent", border: "none", color: "var(--text-primary)", fontSize: "12px", outline: "none", width: "100%" }}
          />
        </form>
      </div>

      {/* Global Search Results if any */}
      {searchResults.length > 0 && (
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "10px" }}>Search Matches ({searchResults.length})</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {searchResults.map((r) => (
              <div key={r.id} style={{ background: "var(--bg-tertiary)", padding: "10px", borderRadius: "6px", fontSize: "12px" }}>
                <strong>{r.title}</strong> <span style={{ color: "var(--accent-primary)", fontSize: "10px" }}>[{r.source}]</span>
                <div style={{ color: "var(--text-muted)", marginTop: "2px" }}>{r.snippet}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Grid: 4 Metric Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "14px" }}>
        <div onClick={() => onNavigate("communication")} style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px", cursor: "pointer" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>IMPORTANT MESSAGES</div>
          <div style={{ fontSize: "24px", fontWeight: 800, marginTop: "6px", color: "var(--accent-primary)" }}>{briefing?.important_messages || 0}</div>
        </div>

        <div onClick={() => onNavigate("executive")} style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px", cursor: "pointer" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>OPEN 5C DECISIONS</div>
          <div style={{ fontSize: "24px", fontWeight: 800, marginTop: "6px", color: "var(--status-amber)" }}>{briefing?.open_decisions || 0}</div>
        </div>

        <div onClick={() => onNavigate("intelligence")} style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px", cursor: "pointer" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>UPCOMING DEADLINES</div>
          <div style={{ fontSize: "24px", fontWeight: 800, marginTop: "6px", color: "var(--status-green)" }}>{briefing?.upcoming_deadlines || 0}</div>
        </div>

        <div onClick={() => onNavigate("approvals")} style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px", cursor: "pointer" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>PENDING APPROVALS</div>
          <div style={{ fontSize: "24px", fontWeight: 800, marginTop: "6px", color: "var(--status-red)" }}>{briefing?.pending_approvals || 0}</div>
        </div>
      </div>

      {/* 2-Pane: Executive Insight & Today's Top Priorities */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "16px" }}>
        {/* Executive Insight Card */}
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
            <Zap size={16} color="var(--accent-primary)" /> 5C Executive Council Recommendation
          </h3>
          <div style={{ fontSize: "13px", lineHeight: "1.5", color: "var(--text-primary)" }}>
            {briefing?.executive_insight}
          </div>
          <div style={{ marginTop: "14px", padding: "10px", background: "var(--bg-tertiary)", borderRadius: "6px", fontSize: "12px", borderLeft: "3px solid var(--accent-primary)" }}>
            <strong>Top Action:</strong> {briefing?.top_recommendation}
          </div>
        </div>

        {/* Priorities List */}
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
            <Layers size={16} color="var(--status-green)" /> Key Focus & Priorities
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {briefing?.priorities.map((p, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", background: "var(--bg-tertiary)", padding: "8px 10px", borderRadius: "6px" }}>
                <CheckCircle size={14} color="var(--status-green)" />
                <span>{p}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
