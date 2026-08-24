import React, { useState } from "react";
import { Key, Plus, Eye, EyeOff, Trash2, Copy, Search, X } from "lucide-react";

export interface PasswordEntry {
  id: string;
  domain: string;
  username: string;
  password: string;
  createdAt: number;
  lastUsedAt: number;
}

interface PasswordManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  entries: PasswordEntry[];
  onSaveEntry: (domain: string, username: string, pass: string) => void;
  onDeleteEntry: (id: string) => void;
}

export const PasswordManagerModal: React.FC<PasswordManagerModalProps> = ({
  isOpen,
  onClose,
  entries,
  onSaveEntry,
  onDeleteEntry,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [domain, setDomain] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  if (!isOpen) return null;

  const generateStrongPassword = () => {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+~";
    let pass = "";
    for (let i = 0; i < 16; i++) {
      pass += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setPassword(pass);
  };

  const handleSave = () => {
    if (!domain.trim() || !username.trim() || !password.trim()) return;
    onSaveEntry(domain.trim(), username.trim(), password.trim());
    setDomain("");
    setUsername("");
    setPassword("");
    setIsAdding(false);
  };

  const copyToClipboard = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filtered = entries.filter(
    (e) =>
      e.domain.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.username.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div
      style={{
        position: "absolute",
        top: "78px",
        left: "260px",
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
          <Key size={15} color="#10b981" /> Passwords & Secure Vault
        </div>
        <button
          onClick={onClose}
          style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }}
        >
          <X size={16} />
        </button>
      </div>

      {/* Search & Add Trigger */}
      <div style={{ display: "flex", gap: "6px", marginBottom: "10px" }}>
        <div style={{ position: "relative", flex: 1 }}>
          <Search size={13} style={{ position: "absolute", left: "8px", top: "8px", color: "var(--text-muted)" }} />
          <input
            type="text"
            placeholder="Search saved credentials..."
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
        <button
          onClick={() => setIsAdding(!isAdding)}
          style={{
            background: "var(--accent-primary)",
            color: "#fff",
            border: "none",
            borderRadius: "8px",
            padding: "6px 10px",
            fontSize: "11px",
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "4px",
          }}
        >
          <Plus size={13} /> Add
        </button>
      </div>

      {/* Add New Credential Form */}
      {isAdding && (
        <div
          style={{
            background: "var(--bg-card-secondary)",
            padding: "10px",
            borderRadius: "10px",
            marginBottom: "12px",
            display: "flex",
            flexDirection: "column",
            gap: "6px",
          }}
        >
          <input
            type="text"
            placeholder="Website domain (e.g. github.com)"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            style={{ padding: "6px 8px", borderRadius: "6px", border: "1px solid rgba(0,0,0,0.1)", fontSize: "12px" }}
          />
          <input
            type="text"
            placeholder="Username or email"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={{ padding: "6px 8px", borderRadius: "6px", border: "1px solid rgba(0,0,0,0.1)", fontSize: "12px" }}
          />
          <div style={{ display: "flex", gap: "6px" }}>
            <input
              type="text"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ flex: 1, padding: "6px 8px", borderRadius: "6px", border: "1px solid rgba(0,0,0,0.1)", fontSize: "12px" }}
            />
            <button
              onClick={generateStrongPassword}
              style={{
                background: "rgba(16, 185, 129, 0.12)",
                color: "#10b981",
                border: "none",
                borderRadius: "6px",
                padding: "6px 8px",
                fontSize: "11px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Generate
            </button>
          </div>
          <div style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
            <button
              onClick={handleSave}
              style={{
                flex: 1,
                background: "var(--text-primary)",
                color: "#fff",
                border: "none",
                borderRadius: "6px",
                padding: "6px",
                fontSize: "11px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Save to Vault
            </button>
            <button
              onClick={() => setIsAdding(false)}
              style={{
                background: "transparent",
                border: "1px solid rgba(0,0,0,0.1)",
                borderRadius: "6px",
                padding: "6px 10px",
                fontSize: "11px",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Credentials List */}
      <div style={{ maxHeight: "240px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px" }}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: "center", padding: "20px", color: "var(--text-muted)", fontSize: "12px" }}>
            No credentials saved.
          </div>
        ) : (
          filtered.map((entry) => (
            <div
              key={entry.id}
              style={{
                padding: "8px 10px",
                borderRadius: "8px",
                background: "var(--bg-card-secondary)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: "12px" }}>{entry.domain}</div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>{entry.username}</div>
                <div style={{ fontSize: "11px", fontFamily: "monospace", marginTop: "2px" }}>
                  {showPassword[entry.id] ? entry.password : "••••••••••••"}
                </div>
              </div>
              <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                <button
                  onClick={() => setShowPassword({ ...showPassword, [entry.id]: !showPassword[entry.id] })}
                  title={showPassword[entry.id] ? "Hide password" : "Show password"}
                  style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: "4px" }}
                >
                  {showPassword[entry.id] ? <EyeOff size={13} /> : <Eye size={13} />}
                </button>
                <button
                  onClick={() => copyToClipboard(entry.id, entry.password)}
                  title="Copy password"
                  style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: "4px" }}
                >
                  <Copy size={13} color={copiedId === entry.id ? "#10b981" : undefined} />
                </button>
                <button
                  onClick={() => onDeleteEntry(entry.id)}
                  title="Delete credential"
                  style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: "4px" }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
