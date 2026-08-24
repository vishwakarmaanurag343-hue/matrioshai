import React, { useState, useEffect } from "react";
import { ShieldCheck, Lock, Eye, RefreshCw } from "lucide-react";
import { EmergencyStopButton } from "./EmergencyStopButton";
import { HumanTakeoverBanner } from "./HumanTakeoverBanner";
import { PermissionManagerModal } from "./PermissionManagerModal";

export const SecurityCenter: React.FC = () => {
  const [securityState, setSecurityState] = useState<any>({
    autonomy_level: "SUPERVISED",
    takeover_state: "AGENT_CONTROL",
    emergency_stop_active: false,
    active_permissions_count: 0,
    domain_permissions: {},
    blocked_domains: [],
    spending_limits: [],
  });
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [isPermModalOpen, setIsPermModalOpen] = useState(false);

  const fetchSecurityState = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/browser/security/state");
      if (res.ok) {
        const data = await res.json();
        setSecurityState(data.security_state);
      }
      const logRes = await fetch("http://127.0.0.1:8000/api/v1/browser/security/audit-logs?limit=20");
      if (logRes.ok) {
        const data = await logRes.json();
        setAuditLogs(data.audit_logs);
      }
    } catch (e) {
      // Backend may be in mock/standalone mode
    }
  };

  useEffect(() => {
    fetchSecurityState();
    const interval = setInterval(fetchSecurityState, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleTakeover = async (state: string) => {
    try {
      await fetch("http://127.0.0.1:8000/api/v1/browser/security/takeover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state }),
      });
      fetchSecurityState();
    } catch (e) {}
  };

  const handleEmergencyStop = async () => {
    try {
      await fetch("http://127.0.0.1:8000/api/v1/browser/security/emergency-stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "User activated emergency kill switch" }),
      });
      fetchSecurityState();
    } catch (e) {}
  };

  const handleResetStop = async () => {
    try {
      await fetch("http://127.0.0.1:8000/api/v1/browser/security/emergency-stop/reset", {
        method: "POST",
      });
      fetchSecurityState();
    } catch (e) {}
  };

  const handleGrant = async (domain: string, perms: string[]) => {
    try {
      await fetch("http://127.0.0.1:8000/api/v1/browser/security/permissions/grant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain, permissions: perms }),
      });
      fetchSecurityState();
    } catch (e) {}
  };

  const handleRevoke = async (domain: string) => {
    try {
      await fetch("http://127.0.0.1:8000/api/v1/browser/security/permissions/revoke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain }),
      });
      fetchSecurityState();
    } catch (e) {}
  };

  const permsList = Object.values(securityState.domain_permissions || {}).map((p: any) => ({
    domain: p.domain,
    permissions: p.permissions || [],
    scope: p.scope || "DOMAIN",
    status: p.status || "ACTIVE",
    expires_at: p.expires_at,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px" }}>
      {/* Top Controls: Emergency Stop & Takeover */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <ShieldCheck size={24} color="var(--accent-primary, #cba6f7)" />
          <div>
            <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>Browser Agent Security Center</h2>
            <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
              Autonomy Guardrails, Secret Isolation, Domain Permissions & Real-time Kill Switch
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button
            onClick={() => setIsPermModalOpen(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: "var(--bg-secondary, #1e1e2e)",
              border: "1px solid var(--border-color, #313244)",
              color: "#fff",
              borderRadius: "8px",
              padding: "8px 12px",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <Lock size={14} />
            Manage Permissions ({permsList.length})
          </button>

          <EmergencyStopButton
            isActive={securityState.emergency_stop_active}
            onTrigger={handleEmergencyStop}
            onReset={handleResetStop}
          />
        </div>
      </div>

      {/* Human Takeover Banner */}
      <HumanTakeoverBanner
        takeoverState={securityState.takeover_state}
        onSetState={handleTakeover}
      />

      {/* Stats Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
        <div style={{ background: "var(--bg-secondary, #1e1e2e)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-color, #313244)" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Autonomy Level</div>
          <div style={{ fontSize: "14px", fontWeight: 700, marginTop: "4px", color: "var(--accent-primary, #cba6f7)" }}>
            {securityState.autonomy_level}
          </div>
        </div>

        <div style={{ background: "var(--bg-secondary, #1e1e2e)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-color, #313244)" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Active Domain Grants</div>
          <div style={{ fontSize: "14px", fontWeight: 700, marginTop: "4px" }}>
            {permsList.length} domains
          </div>
        </div>

        <div style={{ background: "var(--bg-secondary, #1e1e2e)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-color, #313244)" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Spending Limit (Single Tx)</div>
          <div style={{ fontSize: "14px", fontWeight: 700, marginTop: "4px", color: "#10b981" }}>
            ₹15,000 INR
          </div>
        </div>
      </div>

      {/* Security Audit Trail */}
      <div style={{ background: "var(--bg-secondary, #1e1e2e)", padding: "16px", borderRadius: "10px", border: "1px solid var(--border-color, #313244)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", fontWeight: 700 }}>
            <Eye size={16} />
            Security Audit Trail (Redacted)
          </div>
          <button onClick={fetchSecurityState} style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer" }}>
            <RefreshCw size={13} />
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "180px", overflowY: "auto" }}>
          {auditLogs.length === 0 ? (
            <div style={{ fontSize: "12px", color: "var(--text-muted)", textAlign: "center", padding: "12px" }}>
              No security audit events recorded yet.
            </div>
          ) : (
            auditLogs.slice().reverse().map((log: any) => (
              <div
                key={log.event_id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "11px",
                  padding: "6px 8px",
                  background: "var(--bg-primary, #181825)",
                  borderRadius: "4px",
                }}
              >
                <div>
                  <span style={{ fontWeight: 600, color: "var(--accent-primary, #cba6f7)" }}>[{log.policy_decision}]</span>{" "}
                  <span>{log.action}</span>{" "}
                  {log.target && <span style={{ color: "var(--text-muted)" }}>({log.target})</span>}
                </div>
                <div style={{ color: "var(--text-muted)" }}>
                  {new Date(log.timestamp).toLocaleTimeString()}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <PermissionManagerModal
        isOpen={isPermModalOpen}
        permissions={permsList}
        onClose={() => setIsPermModalOpen(false)}
        onGrant={handleGrant}
        onRevoke={handleRevoke}
      />
    </div>
  );
};
