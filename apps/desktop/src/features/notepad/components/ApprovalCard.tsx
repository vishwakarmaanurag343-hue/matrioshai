import React from "react";
import type { Intent } from "../types";

interface ApprovalCardProps {
  intent: Intent;
  onApprove: (intentId: string) => void;
  onReject: (intentId: string) => void;
}

/**
 * Renders a pending-approval card. In slice 1, the simple @ai summarize
 * path does not require approval (LOW risk). @ai research is MEDIUM and
 * will eventually require approval via the existing confirmation_system;
 * for slice 1 this is a placeholder that is only rendered if an intent
 * arrives in PENDING_APPROVAL state from the backend.
 */
export const ApprovalCard: React.FC<ApprovalCardProps> = ({ intent, onApprove, onReject }) => {
  if (intent.status !== "PENDING_APPROVAL") return null;
  return (
    <div
      data-testid="approval-card"
      style={{
        marginTop: 8,
        padding: 10,
        background: "var(--bg-card)",
        borderLeft: "3px solid #d97706",
        borderRadius: 6,
        fontSize: 12,
        color: "var(--text-secondary)",
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Approval required</div>
      <div style={{ marginBottom: 6 }}>
        This intent is {intent.risk} risk. Approve to continue.
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          type="button"
          onClick={() => onApprove(intent.id)}
          data-testid="approval-approve"
          style={{
            padding: "4px 10px",
            background: "#2c7a4b",
            color: "white",
            border: "none",
            borderRadius: 4,
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          Approve
        </button>
        <button
          type="button"
          onClick={() => onReject(intent.id)}
          data-testid="approval-reject"
          style={{
            padding: "4px 10px",
            background: "transparent",
            color: "var(--text-primary)",
            border: "1px solid var(--text-muted)",
            borderRadius: 4,
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          Reject
        </button>
      </div>
    </div>
  );
};
