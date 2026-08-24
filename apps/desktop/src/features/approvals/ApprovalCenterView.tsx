import React, { useState, useEffect } from "react";
import { ShieldAlert, CheckCircle, XCircle } from "lucide-react";
import { securityApi } from "../../services/api/security";
import { ConfirmationRequest } from "../../types";

export const ApprovalCenterView: React.FC = () => {
  const [requests, setRequests] = useState<ConfirmationRequest[]>([]);

  useEffect(() => {
    loadRequests();
  }, []);

  const loadRequests = async () => {
    try {
      const data = await securityApi.getPendingConfirmations();
      setRequests(data);
    } catch (e) {
      // transient load error
    }
  };

  const handleResolve = async (id: string, approved: boolean) => {
    try {
      await securityApi.resolveConfirmation(id, approved);
      setRequests((prev) => prev.filter((r) => r.id !== id));
    } catch (e) {
      // transient resolve error
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflowY: "auto", padding: "20px" }}>
      {/* Header */}
      <div style={{ marginBottom: "20px" }}>
        <h2 style={{ fontSize: "18px", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px" }}>
          <ShieldAlert size={20} color="var(--status-red)" /> Unified Approval Center
        </h2>
        <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
          Central authorization authority for Tier 2 consequential actions (Developer, Communication, Computer Use, and Agent Runtime).
        </div>
      </div>

      {/* Requests List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "14px", maxWidth: "860px" }}>
        {requests.length > 0 ? (
          requests.map((req) => (
            <div
              key={req.id}
              style={{
                background: "var(--bg-secondary)",
                border: "1px solid var(--border-color)",
                borderRadius: "8px",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "10px"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "10px", fontWeight: 700, padding: "2px 6px", borderRadius: "4px", background: "rgba(239, 68, 68, 0.15)", color: "var(--status-red)" }}>
                      TIER 2 • {req.risk_level}
                    </span>
                    <h3 style={{ fontSize: "14px", fontWeight: 700 }}>{req.action_summary}</h3>
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
                    Tool: <strong>{req.tool_name}</strong> | Target: <code>{req.affected_resource}</code>
                  </div>
                </div>

                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    onClick={() => handleResolve(req.id, true)}
                    style={{ background: "var(--status-green)", color: "#fff", border: "none", padding: "6px 14px", borderRadius: "6px", fontSize: "12px", fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
                  >
                    <CheckCircle size={14} /> APPROVE
                  </button>
                  <button
                    onClick={() => handleResolve(req.id, false)}
                    style={{ background: "transparent", border: "1px solid var(--border-color)", color: "var(--status-red)", padding: "6px 14px", borderRadius: "6px", fontSize: "12px", fontWeight: 700, cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
                  >
                    <XCircle size={14} /> REJECT
                  </button>
                </div>
              </div>

              {/* Exact Parameters & Hash Binding */}
              <div style={{ background: "var(--bg-tertiary)", padding: "10px 12px", borderRadius: "6px", fontSize: "11px", overflowX: "auto" }}>
                <div style={{ fontWeight: 700, color: "var(--text-muted)", marginBottom: "4px" }}>EXACT BOUND PARAMETERS:</div>
                <pre style={{ margin: 0, color: "var(--text-primary)" }}>
                  {JSON.stringify(req.parameters, null, 2)}
                </pre>
              </div>
            </div>
          ))
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: "13px", padding: "40px 0", textAlign: "center" }}>
            No pending action confirmations. System is running cleanly.
          </div>
        )}
      </div>
    </div>
  );
};
