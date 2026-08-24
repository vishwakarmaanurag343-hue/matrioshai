import React, { useState } from "react";
import { Shield, Plus, Trash2, X } from "lucide-react";

interface PermissionItem {
  domain: string;
  permissions: string[];
  scope: string;
  status: string;
  expires_at?: string | null;
}

interface PermissionManagerModalProps {
  isOpen: boolean;
  permissions: PermissionItem[];
  onClose: () => void;
  onGrant: (domain: string, perms: string[]) => void;
  onRevoke: (domain: string) => void;
}

export const PermissionManagerModal: React.FC<PermissionManagerModalProps> = ({
  isOpen,
  permissions,
  onClose,
  onGrant,
  onRevoke,
}) => {
  const [newDomain, setNewDomain] = useState("");
  const [selectedPerms] = useState<string[]>(["CLICK", "TYPE", "NAVIGATE"]);

  if (!isOpen) return null;

  const handleGrant = () => {
    if (!newDomain.trim()) return;
    onGrant(newDomain.trim(), selectedPerms);
    setNewDomain("");
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.6)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          width: "540px",
          background: "var(--bg-secondary, #1e1e2e)",
          border: "1px solid var(--border-color, #313244)",
          borderRadius: "12px",
          padding: "20px",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Shield size={20} color="var(--accent-primary, #cba6f7)" />
            <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>Domain Permissions Manager</h3>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer" }}>
            <X size={18} />
          </button>
        </div>

        {/* Grant New Permission */}
        <div style={{ display: "flex", gap: "8px", background: "var(--bg-primary, #181825)", padding: "10px", borderRadius: "8px" }}>
          <input
            type="text"
            placeholder="e.g. google.com or makemytrip.com"
            value={newDomain}
            onChange={(e) => setNewDomain(e.target.value)}
            style={{
              flex: 1,
              background: "transparent",
              border: "1px solid var(--border-color, #313244)",
              borderRadius: "6px",
              padding: "6px 10px",
              color: "#fff",
              fontSize: "12px",
            }}
          />
          <button
            onClick={handleGrant}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              background: "var(--accent-primary, #cba6f7)",
              color: "#111",
              border: "none",
              borderRadius: "6px",
              padding: "6px 12px",
              fontSize: "12px",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            <Plus size={14} />
            Grant
          </button>
        </div>

        {/* Active Permissions List */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "240px", overflowY: "auto" }}>
          {permissions.length === 0 ? (
            <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "12px", padding: "16px" }}>
              No custom domain permissions configured.
            </div>
          ) : (
            permissions.map((p) => (
              <div
                key={p.domain}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 12px",
                  background: "var(--bg-primary, #181825)",
                  borderRadius: "6px",
                }}
              >
                <div>
                  <div style={{ fontSize: "13px", fontWeight: 600 }}>{p.domain}</div>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                    {p.permissions.join(", ")} • {p.status}
                  </div>
                </div>
                <button
                  onClick={() => onRevoke(p.domain)}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "#ef4444",
                    cursor: "pointer",
                    padding: "4px",
                  }}
                  title="Revoke Permission"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
