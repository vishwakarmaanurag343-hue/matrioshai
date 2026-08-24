import React, { useState } from "react";
import { ShieldCheck, ShieldAlert, Lock, Eye, Zap, X } from "lucide-react";
import { ShieldStats } from "../../services/browser/nativeService";

interface ShieldsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentOrigin: string;
  stats: ShieldStats | null;
}

export const ShieldsModal: React.FC<ShieldsModalProps> = ({
  isOpen,
  onClose,
  currentOrigin,
  stats,
}) => {
  const [shieldsEnabled, setShieldsEnabled] = useState(true);
  const [httpsUpgrades, setHttpsUpgrades] = useState(true);
  const [fingerprintProtection, setFingerprintProtection] = useState(true);

  if (!isOpen) return null;

  const displayOrigin = currentOrigin ? currentOrigin.replace(/^https?:\/\//, "").split("/")[0] : "matrioshai.local";

  return (
    <div
      style={{
        position: "absolute",
        top: "78px",
        left: "240px",
        width: "320px",
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
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "8px",
              background: shieldsEnabled ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: shieldsEnabled ? "#10b981" : "#ef4444",
            }}
          >
            {shieldsEnabled ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: "14px", lineHeight: "1.1" }}>MATRIOSHAI SHIELDS</div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              {displayOrigin}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)" }}
        >
          <X size={16} />
        </button>
      </div>

      {/* Main Switch */}
      <div
        style={{
          background: "var(--bg-card-secondary)",
          padding: "10px 12px",
          borderRadius: "12px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "14px",
        }}
      >
        <span style={{ fontWeight: 600 }}>Shields for this site</span>
        <button
          onClick={() => setShieldsEnabled(!shieldsEnabled)}
          style={{
            background: shieldsEnabled ? "#10b981" : "#9ca3af",
            color: "#fff",
            border: "none",
            borderRadius: "14px",
            padding: "4px 10px",
            fontSize: "11px",
            fontWeight: 700,
            cursor: "pointer",
            transition: "background 0.2s ease",
          }}
        >
          {shieldsEnabled ? "UP" : "DOWN"}
        </button>
      </div>

      {/* Blocked Metrics Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "8px",
          marginBottom: "14px",
        }}
      >
        <div style={{ background: "var(--bg-card-secondary)", padding: "10px", borderRadius: "10px" }}>
          <div style={{ fontSize: "18px", fontWeight: 800, color: "#10b981" }}>
            {stats?.trackers_blocked || 0}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Trackers & Ads Blocked</div>
        </div>
        <div style={{ background: "var(--bg-card-secondary)", padding: "10px", borderRadius: "10px" }}>
          <div style={{ fontSize: "18px", fontWeight: 800, color: "#3b82f6" }}>
            {stats?.malicious_blocked || 0}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Malicious Threats</div>
        </div>
      </div>

      {/* Granular Toggles */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px" }}>
            <Eye size={13} color="#6b7280" /> Block Cross-Site Trackers
          </span>
          <input
            type="checkbox"
            checked={shieldsEnabled}
            disabled={!shieldsEnabled}
            onChange={() => {}}
            style={{ cursor: "pointer" }}
          />
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px" }}>
            <Lock size={13} color="#6b7280" /> Upgrade Connections to HTTPS
          </span>
          <input
            type="checkbox"
            checked={httpsUpgrades}
            onChange={(e) => setHttpsUpgrades(e.target.checked)}
            style={{ cursor: "pointer" }}
          />
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px" }}>
            <Zap size={13} color="#6b7280" /> Block Fingerprinting vectors
          </span>
          <input
            type="checkbox"
            checked={fingerprintProtection}
            onChange={(e) => setFingerprintProtection(e.target.checked)}
            style={{ cursor: "pointer" }}
          />
        </div>
      </div>
    </div>
  );
};
