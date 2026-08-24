import React from "react";
import { Download, X } from "lucide-react";

export interface DownloadItem {
  id: string;
  filename: string;
  url: string;
  totalBytes: number;
  receivedBytes: number;
  status: "DOWNLOADING" | "PAUSED" | "COMPLETED" | "FAILED" | "CANCELLED";
  startedAt: number;
}

interface DownloadManagerDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  downloads: DownloadItem[];
  onCancelDownload: (id: string) => void;
  onClearCompleted: () => void;
}

export const DownloadManagerDrawer: React.FC<DownloadManagerDrawerProps> = ({
  isOpen,
  onClose,
  downloads,
  onCancelDownload,
  onClearCompleted,
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "absolute",
        top: "78px",
        left: "300px",
        width: "420px",
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
          <Download size={15} color="#3b82f6" /> Downloads Manager
        </div>
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          {downloads.some((d) => d.status === "COMPLETED") && (
            <button
              onClick={onClearCompleted}
              style={{
                background: "var(--bg-card-secondary)",
                border: "none",
                borderRadius: "6px",
                padding: "4px 8px",
                fontSize: "11px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Clear Completed
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

      {/* Downloads List */}
      <div style={{ maxHeight: "280px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px" }}>
        {downloads.length === 0 ? (
          <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-muted)", fontSize: "12px" }}>
            No active or recent downloads.
          </div>
        ) : (
          downloads.map((d) => {
            const percent = d.totalBytes > 0 ? Math.round((d.receivedBytes / d.totalBytes) * 100) : 0;
            return (
              <div
                key={d.id}
                style={{
                  padding: "10px",
                  borderRadius: "10px",
                  background: "var(--bg-card-secondary)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontWeight: 600, fontSize: "12px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {d.filename}
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>
                    {d.status}
                  </div>
                </div>

                {/* Progress bar */}
                {d.status === "DOWNLOADING" && (
                  <div style={{ width: "100%", height: "4px", background: "rgba(0,0,0,0.06)", borderRadius: "2px", overflow: "hidden" }}>
                    <div style={{ width: `${percent}%`, height: "100%", background: "#3b82f6" }} />
                  </div>
                )}

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "10px", color: "var(--text-muted)", marginTop: "2px" }}>
                  <span>{d.url.replace(/^https?:\/\//, "").split("/")[0]}</span>
                  <div style={{ display: "flex", gap: "6px" }}>
                    {d.status === "DOWNLOADING" && (
                      <button
                        onClick={() => onCancelDownload(d.id)}
                        style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 0 }}
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
