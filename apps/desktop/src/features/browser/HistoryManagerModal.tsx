import React, { useState } from "react";
import { History, Search, Trash2, X } from "lucide-react";

export interface HistoryEntry {
  id: string;
  url: string;
  title: string;
  visitedAt: number;
}

interface HistoryManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  history: HistoryEntry[];
  onNavigate: (url: string) => void;
  onClearHistory: () => void;
  onDeleteEntry: (id: string) => void;
}

export const HistoryManagerModal: React.FC<HistoryManagerModalProps> = ({
  isOpen,
  onClose,
  history,
  onNavigate,
  onClearHistory,
  onDeleteEntry,
}) => {
  const [searchTerm, setSearchTerm] = useState("");

  if (!isOpen) return null;

  const filtered = history.filter(
    (h) =>
      h.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      h.url.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div
      style={{
        position: "absolute",
        top: "78px",
        left: "200px",
        width: "440px",
        background: "rgba(255, 255, 255, 0.95)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        borderRadius: "16px",
        boxShadow: "0 12px 36px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.08)",
        zIndex: 9999,
        padding: "16px",
        color: "var(--text-primary)",
        fontSize: "13px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: 700, fontSize: "14px" }}>
          <History size={15} color="#3b82f6" /> Browsing History
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          {history.length > 0 && (
            <button
              onClick={onClearHistory}
              style={{
                background: "rgba(239, 68, 68, 0.1)",
                color: "#ef4444",
                border: "none",
                borderRadius: "6px",
                padding: "4px 8px",
                fontSize: "11px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Clear All
            </button>
          )}
          <button
            onClick={onClose}
            style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }}
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Search Filter */}
      <div style={{ position: "relative", marginBottom: "10px" }}>
        <Search size={13} style={{ position: "absolute", left: "8px", top: "8px", color: "var(--text-muted)" }} />
        <input
          type="text"
          placeholder="Search browsing history..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            width: "100%",
            padding: "6px 8px 6px 26px",
            borderRadius: "8px",
            border: "1px solid rgba(0,0,0,0.1)",
            fontSize: "12px",
          }}
        />
      </div>

      {/* History Items */}
      <div style={{ maxHeight: "260px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "4px" }}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: "center", padding: "20px", color: "var(--text-muted)", fontSize: "12px" }}>
            No history recorded.
          </div>
        ) : (
          filtered.map((item) => (
            <div
              key={item.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px",
                borderRadius: "8px",
                background: "var(--bg-card-secondary)",
              }}
            >
              <div
                onClick={() => {
                  onNavigate(item.url);
                  onClose();
                }}
                style={{ cursor: "pointer", flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}
              >
                <div style={{ fontWeight: 600, fontSize: "12px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {item.title || item.url}
                </div>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {item.url} • {new Date(item.visitedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
              <button
                onClick={() => onDeleteEntry(item.id)}
                title="Remove from history"
                style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: "4px" }}
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
