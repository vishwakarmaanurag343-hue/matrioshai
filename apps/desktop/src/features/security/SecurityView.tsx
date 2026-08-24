import React, { useState, useEffect } from "react";
import { ShieldCheck, Lock, Eye, AlertTriangle, CheckCircle, XCircle, RefreshCw, Key, FileCheck, Layers } from "lucide-react";
import { securityApi } from "../../services/api/security";
import { SecurityAuditEvent, ToolDefinition, ConfirmationRequest } from "../../types";

export const SecurityView: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<"overview" | "audit" | "permissions" | "confirmations">("overview");
  const [auditLogs, setAuditLogs] = useState<SecurityAuditEvent[]>([]);
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [confirmations, setConfirmations] = useState<ConfirmationRequest[]>([]);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [logs, toolList, pendingList] = await Promise.all([
        securityApi.getAuditLogs(50),
        securityApi.getTools(),
        securityApi.getPendingConfirmations(),
      ]);
      setAuditLogs(logs);
      setTools(toolList);
      setConfirmations(pendingList);
    } catch (err: any) {
      setStatusMsg(`Error refreshing security data: ${err.message}`);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleResolveConfirmation = async (id: string, approved: boolean) => {
    try {
      await securityApi.resolveConfirmation(id, approved);
      setStatusMsg(`Confirmation ${approved ? "approved" : "rejected"}.`);
      loadData();
    } catch (err: any) {
      setStatusMsg(`Failed to resolve confirmation: ${err.message}`);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "24px", overflowY: "auto", gap: "20px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <ShieldCheck size={26} style={{ color: "var(--accent-primary)" }} />
          <div>
            <h2 style={{ fontSize: "18px", fontWeight: 700 }}>SECURITY, PRIVACY & CONTROL</h2>
            <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              Central Privacy Gatekeeper, PII Redaction, Secret Isolation, and 3-Tier Autonomy Permission Engine
            </p>
          </div>
        </div>

        <button className="action-btn" onClick={loadData} title="Refresh Security State">
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {statusMsg && (
        <div style={{ padding: "8px 14px", background: "var(--accent-light)", borderRadius: "6px", color: "var(--accent-primary)", fontSize: "13px" }}>
          {statusMsg}
        </div>
      )}

      {/* Sub Tabs */}
      <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid var(--border-color)", paddingBottom: "8px" }}>
        <button
          className={`nav-item ${activeSubTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveSubTab("overview")}
        >
          <Layers size={14} />
          Security Overview
        </button>
        <button
          className={`nav-item ${activeSubTab === "audit" ? "active" : ""}`}
          onClick={() => setActiveSubTab("audit")}
        >
          <Eye size={14} />
          Audit Trail ({auditLogs.length})
        </button>
        <button
          className={`nav-item ${activeSubTab === "permissions" ? "active" : ""}`}
          onClick={() => setActiveSubTab("permissions")}
        >
          <Lock size={14} />
          Permissions & Tools ({tools.length})
        </button>
        <button
          className={`nav-item ${activeSubTab === "confirmations" ? "active" : ""}`}
          onClick={() => setActiveSubTab("confirmations")}
        >
          <AlertTriangle size={14} />
          Pending Approvals ({confirmations.length})
        </button>
      </div>

      {/* OVERVIEW PANEL */}
      {activeSubTab === "overview" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "12px" }}>
            <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, marginBottom: "6px" }}>
                <ShieldCheck size={16} color="var(--status-green)" />
                Privacy Gatekeeper
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                Active. Contexts sent to models are evaluated and sanitized. PII and credentials are automatically redacted.
              </div>
            </div>

            <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, marginBottom: "6px" }}>
                <Key size={16} color="var(--accent-primary)" />
                Secret Isolation
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                Active. Secrets are stored in isolated macOS Keychain storage and NEVER enter SQLite, memory, logs, or model context.
              </div>
            </div>

            <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, marginBottom: "6px" }}>
                <FileCheck size={16} color="var(--status-green)" />
                Filesystem Security
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                Restricted to <code>matrioshai/data/</code>. System directories (<code>/etc</code>, <code>~/.ssh</code>) are strictly blocked.
              </div>
            </div>
          </div>

          {/* Model Dispatch Policy */}
          <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px" }}>
            <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "10px" }}>MODEL CONTEXT PRIVACY POLICY</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "13px" }}>
              <div style={{ padding: "10px", background: "var(--bg-tertiary)", borderRadius: "6px" }}>
                <strong>LOCAL AI (Ollama) Policy:</strong> Private notes & memory context allowed locally. Secret credentials and keys are blocked.
              </div>
              <div style={{ padding: "10px", background: "var(--bg-tertiary)", borderRadius: "6px" }}>
                <strong>CLOUD AI Policy:</strong> Entire local database is blocked from automatic exfiltration. Sensitive PII (emails, phone numbers, credentials) is redacted.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* AUDIT LOG PANEL */}
      {activeSubTab === "audit" && (
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "12px" }}>SECURITY AUDIT TRAIL</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {auditLogs.map((log) => (
              <div
                key={log.id}
                style={{
                  background: "var(--bg-tertiary)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "6px",
                  padding: "10px 14px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: 800,
                        padding: "2px 6px",
                        borderRadius: "4px",
                        background: log.decision === "ALLOWED" ? "rgba(16, 185, 129, 0.15)" : log.decision === "REDACTED" ? "var(--accent-light)" : "rgba(239, 68, 68, 0.15)",
                        color: log.decision === "ALLOWED" ? "var(--status-green)" : log.decision === "REDACTED" ? "var(--accent-primary)" : "var(--status-red)",
                      }}
                    >
                      {log.decision}
                    </span>
                    <strong style={{ fontSize: "13px" }}>{log.action}</strong>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>({log.event_type})</span>
                  </div>
                  {log.reason && <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "4px" }}>{log.reason}</div>}
                </div>
                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* PERMISSIONS PANEL */}
      {activeSubTab === "permissions" && (
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "12px" }}>REGISTERED TOOL PERMISSIONS & AUTONOMY TIERS</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {tools.map((t) => (
              <div
                key={t.name}
                style={{
                  background: "var(--bg-tertiary)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "6px",
                  padding: "12px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: "13px" }}>{t.name}</div>
                  <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{t.description}</div>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                    Permission: {t.permission_level} | Side Effects: {t.causes_side_effects ? "Yes" : "No"}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 800,
                      padding: "3px 8px",
                      borderRadius: "4px",
                      background: t.autonomy_tier === "TIER_1" ? "rgba(16, 185, 129, 0.15)" : t.autonomy_tier === "TIER_2" ? "rgba(245, 158, 11, 0.2)" : "rgba(239, 68, 68, 0.2)",
                      color: t.autonomy_tier === "TIER_1" ? "var(--status-green)" : t.autonomy_tier === "TIER_2" ? "var(--status-amber)" : "var(--status-red)",
                    }}
                  >
                    {t.autonomy_tier === "TIER_1" ? "Tier 1 (Autonomous)" : t.autonomy_tier === "TIER_2" ? "Tier 2 (Approval Required)" : "Tier 3 (Blocked / Prohibited)"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* CONFIRMATIONS PANEL */}
      {activeSubTab === "confirmations" && (
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "12px" }}>PENDING ACTION APPROVALS</h3>
          {confirmations.length === 0 ? (
            <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "20px" }}>
              No pending approvals. Tier 2 actions requiring approval will appear here.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {confirmations.map((req) => (
                <div
                  key={req.id}
                  style={{
                    background: "var(--bg-tertiary)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "6px",
                    padding: "16px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong style={{ fontSize: "14px" }}>Action Approval Required: {req.tool_name}</strong>
                    <span style={{ color: "var(--status-amber)", fontWeight: 700, fontSize: "12px" }}>Risk: {req.risk_level}</span>
                  </div>
                  <div style={{ fontSize: "13px" }}>{req.action_summary}</div>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Target Resource: <code>{req.affected_resource}</code></div>
                  <div style={{ display: "flex", gap: "10px", marginTop: "6px" }}>
                    <button
                      className="new-chat-btn"
                      onClick={() => handleResolveConfirmation(req.id, true)}
                    >
                      <CheckCircle size={14} />
                      Approve Action
                    </button>
                    <button
                      className="action-btn"
                      onClick={() => handleResolveConfirmation(req.id, false)}
                      style={{ color: "var(--status-red)", padding: "6px 12px" }}
                    >
                      <XCircle size={14} />
                      Cancel
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
