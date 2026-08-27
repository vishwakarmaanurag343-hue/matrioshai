import React from "react";
import type { Intent } from "../types";
import { TaskCard } from "./TaskCard";
import { ApprovalCard } from "./ApprovalCard";

interface IntentSurfaceProps {
  intents: Intent[];
  onRoute: (intentId: string) => void;
  onApprove: (intentId: string) => void;
  onReject: (intentId: string) => void;
}

/**
 * Container that renders all detected Intents as cards below the editor.
 * The component is purely presentational; intent state lives in IntentRouter.
 */
export const IntentSurface: React.FC<IntentSurfaceProps> = ({
  intents,
  onRoute,
  onApprove,
  onReject,
}) => {
  if (intents.length === 0) return null;

  const running = intents.filter((i) => i.status === "RUNNING" || i.status === "ROUTED").length;
  const pending = intents.filter((i) => i.status === "PENDING_APPROVAL").length;

  return (
    <div
      data-testid="intent-surface"
      style={{
        marginTop: 12,
        maxHeight: "30vh",
        overflowY: "auto",
        paddingTop: 4,
        borderTop: "1px solid rgba(0,0,0,0.05)",
      }}
    >
      <div
        data-testid="intent-status-row"
        style={{
          fontSize: 11,
          color: "var(--text-muted)",
          marginBottom: 6,
        }}
      >
        {running} running · {pending} awaiting approval
      </div>
      {intents.map((intent) => (
        <React.Fragment key={intent.id}>
          <TaskCard intent={intent} onRoute={onRoute} />
          <ApprovalCard
            intent={intent}
            onApprove={onApprove}
            onReject={onReject}
          />
        </React.Fragment>
      ))}
    </div>
  );
};
