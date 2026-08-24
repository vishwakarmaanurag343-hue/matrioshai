import React from "react";
import { Octagon, ShieldAlert, RotateCcw } from "lucide-react";

interface EmergencyStopButtonProps {
  isActive: boolean;
  onTrigger: () => void;
  onReset: () => void;
}

export const EmergencyStopButton: React.FC<EmergencyStopButtonProps> = ({
  isActive,
  onTrigger,
  onReset,
}) => {
  if (isActive) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "8px 14px",
          background: "rgba(239, 68, 68, 0.15)",
          border: "1px solid rgba(239, 68, 68, 0.4)",
          borderRadius: "8px",
        }}
      >
        <ShieldAlert size={18} color="#ef4444" />
        <span style={{ fontSize: "13px", fontWeight: 600, color: "#ef4444" }}>
          EMERGENCY STOP ACTIVE
        </span>
        <button
          onClick={onReset}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            background: "#22c55e",
            color: "#fff",
            border: "none",
            borderRadius: "6px",
            padding: "4px 10px",
            fontSize: "12px",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          <RotateCcw size={12} />
          Reset Stop
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={onTrigger}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        background: "#dc2626",
        color: "#ffffff",
        border: "none",
        borderRadius: "8px",
        padding: "8px 14px",
        fontSize: "13px",
        fontWeight: 700,
        cursor: "pointer",
        boxShadow: "0 2px 6px rgba(220, 38, 38, 0.3)",
      }}
      title="Immediately kill all autonomous browser actions"
    >
      <Octagon size={16} />
      EMERGENCY STOP
    </button>
  );
};
