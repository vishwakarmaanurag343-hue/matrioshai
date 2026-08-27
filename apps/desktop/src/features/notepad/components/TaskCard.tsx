import React from "react";
import type { Intent } from "../types";
import { ResultCard } from "./ResultCard";

interface TaskCardProps {
  intent: Intent;
  onRoute?: (intentId: string) => void;
}

/**
 * Renders a single Intent as a small card below the editor. The card is
 * visually distinct from note content (border + colored status badge).
 *
 * The simple @ai summarize flow is a single-step Intent and never creates
 * an AgentTask; the card just shows the status + (on COMPLETED) the result.
 */
export const TaskCard: React.FC<TaskCardProps> = ({ intent, onRoute }) => {
  const isDeferred = intent.status === "DEFERRED";
  const isFailed = intent.status === "FAILED";
  const isRunning = intent.status === "RUNNING" || intent.status === "ROUTED";
  const isCompleted = intent.status === "COMPLETED";

  const borderColor = isFailed
    ? "#c0392b"
    : isDeferred
    ? "var(--text-muted)"
    : isCompleted
    ? "#2c7a4b"
    : isRunning
    ? "#2a6f97"
    : "var(--text-muted)";

  return (
    <div
      data-testid={`task-card-${intent.capability_id ?? "unknown"}`}
      data-status={intent.status}
      style={{
        marginTop: 8,
        padding: 10,
        background: "var(--bg-card)",
        border: `1px solid var(--bg-card-secondary)`,
        borderLeft: `3px solid ${borderColor}`,
        borderRadius: 6,
        fontSize: 12,
        color: "var(--text-secondary)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 4,
        }}
      >
        <div>
          <span style={{ fontWeight: 600 }}>
            @{intent.capability_id ?? "unknown"}
          </span>{" "}
          <span style={{ color: "var(--text-muted)" }}>
            {intent.requested_action || ""}
          </span>
        </div>
        <div
          style={{
            fontSize: 10,
            textTransform: "uppercase",
            letterSpacing: 1,
            color: borderColor,
          }}
        >
          {intent.status}
        </div>
      </div>

      {isDeferred && (
        <div data-testid="deferred-message" style={{ color: "var(--text-muted)" }}>
          Browser capability is not enabled in this phase.
        </div>
      )}

      {isRunning && (
        <div style={{ color: "var(--text-muted)" }}>Running…</div>
      )}

      {isFailed && intent.failure && (
        <div data-testid="failure-message" style={{ color: "#c0392b" }}>
          {intent.failure.category}: {intent.failure.message}
        </div>
      )}

      {isCompleted && intent.result && <ResultCard result={intent.result} />}

      {intent.status === "DETECTED" && onRoute && intent.capability_id === "ai" && (
        <button
          type="button"
          onClick={() => onRoute(intent.id)}
          data-testid="route-button"
          style={{
            marginTop: 6,
            padding: "4px 10px",
            background: "var(--accent, #2a6f97)",
            color: "white",
            border: "none",
            borderRadius: 4,
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          Run
        </button>
      )}
    </div>
  );
};
