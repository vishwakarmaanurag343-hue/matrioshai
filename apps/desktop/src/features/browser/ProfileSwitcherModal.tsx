import React, { useState } from "react";
import { User, Plus, Check, Lock, X } from "lucide-react";
import { BrowserProfile } from "../../services/browser/nativeService";

interface ProfileSwitcherModalProps {
  isOpen: boolean;
  onClose: () => void;
  profiles: BrowserProfile[];
  activeProfileId: string;
  onSelectProfile: (profileId: string) => void;
  onCreateProfile: (name: string, isPrivate: boolean) => void;
}

export const ProfileSwitcherModal: React.FC<ProfileSwitcherModalProps> = ({
  isOpen,
  onClose,
  profiles,
  activeProfileId,
  onSelectProfile,
  onCreateProfile,
}) => {
  const [newProfileName, setNewProfileName] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  if (!isOpen) return null;

  const handleCreate = () => {
    if (!newProfileName.trim()) return;
    onCreateProfile(newProfileName.trim(), isPrivate);
    setNewProfileName("");
    setIsCreating(false);
  };

  return (
    <div
      style={{
        position: "absolute",
        top: "78px",
        left: "320px",
        width: "300px",
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
        <div style={{ fontWeight: 700, fontSize: "14px" }}>Browser Profiles</div>
        <button
          onClick={onClose}
          style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }}
        >
          <X size={16} />
        </button>
      </div>

      {/* Profiles List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginBottom: "14px" }}>
        {profiles.map((p) => (
          <div
            key={p.id}
            onClick={() => onSelectProfile(p.id)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "8px 10px",
              borderRadius: "10px",
              background: p.id === activeProfileId ? "var(--bg-card-hover)" : "var(--bg-card-secondary)",
              cursor: "pointer",
              border: p.id === activeProfileId ? "1px solid rgba(0,0,0,0.15)" : "1px solid transparent",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "24px",
                  height: "24px",
                  borderRadius: "50%",
                  background: p.profile_type === "PRIVATE" ? "#4b5563" : "#3b82f6",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                }}
              >
                {p.profile_type === "PRIVATE" ? <Lock size={12} /> : <User size={12} />}
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: "12px" }}>{p.name}</div>
                <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                  {p.profile_type === "PRIVATE" ? "Isolated Ephemeral Session" : "Isolated Cookies & Storage"}
                </div>
              </div>
            </div>
            {p.id === activeProfileId && <Check size={14} color="#10b981" />}
          </div>
        ))}
      </div>

      {/* Add Profile Section */}
      {isCreating ? (
        <div style={{ background: "var(--bg-card-secondary)", padding: "10px", borderRadius: "10px" }}>
          <input
            type="text"
            placeholder="Profile name (e.g. Work, Research)"
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
            style={{
              width: "100%",
              padding: "6px 8px",
              borderRadius: "6px",
              border: "1px solid rgba(0,0,0,0.1)",
              marginBottom: "8px",
              fontSize: "12px",
            }}
            autoFocus
          />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <label style={{ fontSize: "11px", display: "flex", alignItems: "center", gap: "4px" }}>
              <input
                type="checkbox"
                checked={isPrivate}
                onChange={(e) => setIsPrivate(e.target.checked)}
              />
              Private Session
            </label>
          </div>
          <div style={{ display: "flex", gap: "6px" }}>
            <button
              onClick={handleCreate}
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
              Save Profile
            </button>
            <button
              onClick={() => setIsCreating(false)}
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
      ) : (
        <button
          onClick={() => setIsCreating(true)}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "6px",
            background: "var(--bg-card-secondary)",
            border: "1px dashed rgba(0,0,0,0.15)",
            padding: "8px",
            borderRadius: "10px",
            fontSize: "12px",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          <Plus size={14} /> Add Profile
        </button>
      )}
    </div>
  );
};
