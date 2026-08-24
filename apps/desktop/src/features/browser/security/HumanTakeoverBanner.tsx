import React from "react";
import { UserCheck, Bot, Play, Pause } from "lucide-react";

interface HumanTakeoverBannerProps {
  takeoverState: "AGENT_CONTROL" | "USER_CONTROL" | "SHARED_CONTROL" | "PAUSED";
  onSetState: (state: "AGENT_CONTROL" | "USER_CONTROL" | "SHARED_CONTROL" | "PAUSED") => void;
}

export const HumanTakeoverBanner: React.FC<HumanTakeoverBannerProps> = ({
  takeoverState,
  onSetState,
}) => {
  const isUserInControl = takeoverState === "USER_CONTROL";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 16px",
        background: isUserInControl
          ? "rgba(59, 130, 246, 0.12)"
          : "rgba(16, 185, 129, 0.12)",
        border: `1px solid ${
          isUserInControl ? "rgba(59, 130, 246, 0.3)" : "rgba(16, 185, 129, 0.3)"
        }`,
        borderRadius: "8px",
        marginBottom: "12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        {isUserInControl ? (
          <UserCheck size={18} color="#3b82f6" />
        ) : (
          <Bot size={18} color="#10b981" />
        )}
        <div>
          <div style={{ fontSize: "13px", fontWeight: 700 }}>
            {isUserInControl ? "Human In Control (Takeover Active)" : "Agent Autonomous Control Active"}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            {isUserInControl
              ? "Agent browser action dispatching is paused. You have full manual browser control."
              : "Agent is operating in supervised mode under policy and confirmation guardrails."}
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: "8px" }}>
        {isUserInControl ? (
          <button
            onClick={() => onSetState("AGENT_CONTROL")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              background: "#10b981",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <Play size={13} />
            Return Control to Agent
          </button>
        ) : (
          <button
            onClick={() => onSetState("USER_CONTROL")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              background: "#3b82f6",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <Pause size={13} />
            Take Manual Control
          </button>
        )}
      </div>
    </div>
  );
};
