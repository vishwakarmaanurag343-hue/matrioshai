import React, { useState, useEffect } from "react";
import { Terminal, AlertCircle, RefreshCw } from "lucide-react";

export const ObservabilityPanel: React.FC = () => {
  const [dlqItems, setDlqItems] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<"events" | "dlq">("events");

  const fetchLogs = async () => {
    try {
      const dlqRes = await fetch("http://127.0.0.1:8000/api/v1/browser/runtime/dead-letter-queue?limit=20");
      if (dlqRes.ok) {
        const data = await dlqRes.json();
        setDlqItems(data.dead_letter_items || []);
      }
    } catch (e) {}
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px", padding: "16px", background: "var(--bg-secondary, #1e1e2e)", borderRadius: "10px", border: "1px solid var(--border-color, #313244)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={() => setActiveTab("events")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              background: activeTab === "events" ? "var(--bg-primary, #181825)" : "transparent",
              border: "1px solid var(--border-color, #313244)",
              borderRadius: "6px",
              color: "#fff",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <Terminal size={14} />
            Runtime Event Bus
          </button>
          <button
            onClick={() => setActiveTab("dlq")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              background: activeTab === "dlq" ? "var(--bg-primary, #181825)" : "transparent",
              border: "1px solid var(--border-color, #313244)",
              borderRadius: "6px",
              color: dlqItems.length > 0 ? "#ef4444" : "#fff",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <AlertCircle size={14} />
            Dead Letter Queue ({dlqItems.length})
          </button>
        </div>

        <button onClick={fetchLogs} style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer" }}>
          <RefreshCw size={13} />
        </button>
      </div>

      {activeTab === "dlq" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "200px", overflowY: "auto" }}>
          {dlqItems.length === 0 ? (
            <div style={{ fontSize: "12px", color: "var(--text-muted)", textAlign: "center", padding: "16px" }}>
              No failed operations in Dead Letter Queue.
            </div>
          ) : (
            dlqItems.map((item) => (
              <div
                key={item.item_id}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                  padding: "8px 10px",
                  background: "var(--bg-primary, #181825)",
                  borderRadius: "6px",
                  borderLeft: "3px solid #ef4444",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px" }}>
                  <span style={{ fontWeight: 700, color: "#ef4444" }}>[{item.source}]</span>
                  <span style={{ color: "var(--text-muted)" }}>Attempts: {item.attempts}</span>
                </div>
                <div style={{ fontSize: "12px", color: "#fff" }}>{item.error_message}</div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div style={{ fontSize: "12px", color: "var(--text-muted)", textAlign: "center", padding: "16px" }}>
          Streaming runtime event bus active.
        </div>
      )}
    </div>
  );
};
