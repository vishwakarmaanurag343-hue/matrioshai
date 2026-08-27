import React from "react";
import type { Intent } from "../types";

interface CommandDetectionIndicatorProps {
  intent: Intent;
}

/**
 * Small dot rendered next to a note line that produced an Intent.
 * Color encodes status. No interaction; visual only.
 */
export const CommandDetectionIndicator: React.FC<CommandDetectionIndicatorProps> = ({ intent }) => {
  const color =
    intent.status === "DEFERRED"
      ? "var(--text-muted)"
      : intent.status === "FAILED"
      ? "#c0392b"
      : intent.status === "COMPLETED"
      ? "#2c7a4b"
      : intent.status === "RUNNING" || intent.status === "ROUTED"
      ? "#2a6f97"
      : "var(--text-muted)";

  const title = `@${intent.capability_id ?? "?"} • ${intent.status}`;
  return (
    <span
      data-testid="command-detection-indicator"
      title={title}
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: color,
        marginRight: 6,
        verticalAlign: "middle",
      }}
    />
  );
};
