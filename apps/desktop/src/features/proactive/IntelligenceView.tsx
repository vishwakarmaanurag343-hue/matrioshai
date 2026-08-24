import React, { useState, useEffect } from "react";
import { Sparkles, Clock, XCircle } from "lucide-react";
import { proactiveApi, ProactiveSuggestion } from "../../services/api/knowledge_proactive";

export const IntelligenceView: React.FC = () => {
  const [suggestions, setSuggestions] = useState<ProactiveSuggestion[]>([]);

  useEffect(() => {
    loadSuggestions();
  }, []);

  const loadSuggestions = async () => {
    try {
      const data = await proactiveApi.getSuggestions();
      setSuggestions(data);
    } catch (e) {
      // transient load error
    }
  };

  const handleDismiss = async (id: string) => {
    try {
      await proactiveApi.dismissSuggestion(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    } catch (e) {
      // transient error
    }
  };

  const handleSnooze = async (id: string) => {
    try {
      await proactiveApi.snoozeSuggestion(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    } catch (e) {
      // transient error
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflowY: "auto", padding: "20px" }}>
      {/* Header */}
      <div style={{ marginBottom: "20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ fontSize: "18px", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px" }}>
            <Sparkles size={20} color="var(--accent-primary)" /> Proactive Intelligence & Attention Signals
          </h2>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
            Explainable signals surfaced from communications, 5C decisions, and workspace deadlines.
          </div>
        </div>
      </div>

      {/* Suggestions List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "14px", maxWidth: "860px" }}>
        {suggestions.length > 0 ? (
          suggestions.map((sug) => (
            <div
              key={sug.id}
              style={{
                background: "var(--bg-secondary)",
                border: "1px solid var(--border-color)",
                borderRadius: "8px",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "10px"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "10px", fontWeight: 700, padding: "2px 6px", borderRadius: "4px", background: "rgba(245, 158, 11, 0.15)", color: "var(--status-amber)" }}>
                      {sug.priority}
                    </span>
                    <h3 style={{ fontSize: "14px", fontWeight: 700 }}>{sug.title}</h3>
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-primary)", marginTop: "6px" }}>
                    <strong>Why MATRIOSHAI is showing this:</strong> {sug.reason}
                  </div>
                </div>

                <div style={{ display: "flex", gap: "6px" }}>
                  <button
                    onClick={() => handleSnooze(sug.id)}
                    style={{ background: "transparent", border: "1px solid var(--border-color)", color: "var(--text-muted)", padding: "4px 8px", borderRadius: "4px", fontSize: "11px", cursor: "pointer", display: "flex", alignItems: "center", gap: "4px" }}
                  >
                    <Clock size={12} /> Snooze
                  </button>
                  <button
                    onClick={() => handleDismiss(sug.id)}
                    style={{ background: "transparent", border: "1px solid var(--border-color)", color: "var(--text-muted)", padding: "4px 8px", borderRadius: "4px", fontSize: "11px", cursor: "pointer", display: "flex", alignItems: "center", gap: "4px" }}
                  >
                    <XCircle size={12} /> Dismiss
                  </button>
                </div>
              </div>

              {/* Evidence and Recommended Action */}
              <div style={{ background: "var(--bg-tertiary)", padding: "10px 12px", borderRadius: "6px", fontSize: "11px", display: "flex", flexDirection: "column", gap: "4px" }}>
                <div><strong>Evidence:</strong> {sug.evidence}</div>
                <div style={{ color: "var(--accent-primary)" }}><strong>Suggested Action:</strong> {sug.suggested_action}</div>
              </div>
            </div>
          ))
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: "13px", padding: "40px 0", textAlign: "center" }}>
            No pending proactive suggestions. All clear!
          </div>
        )}
      </div>
    </div>
  );
};
