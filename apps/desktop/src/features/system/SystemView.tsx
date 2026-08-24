import React, { useState, useEffect } from "react";
import { Activity, ShieldCheck, Database, Server, CheckCircle, Clock, Download } from "lucide-react";
import { systemApi, HealthStatus, SystemMetrics, StructuredEvent, DatabaseBackup, DiagnosticsReport } from "../../services/api/system";

export const SystemView: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [events, setEvents] = useState<StructuredEvent[]>([]);
  const [backups, setBackups] = useState<DatabaseBackup[]>([]);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsReport | null>(null);
  const [loadingDiag, setLoadingDiag] = useState(false);
  const [backupMsg, setBackupMsg] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [h, m, ev, bk] = await Promise.all([
        systemApi.getHealth(),
        systemApi.getMetrics(),
        systemApi.getEvents(30),
        systemApi.listBackups(),
      ]);
      setHealth(h);
      setMetrics(m);
      setEvents(ev);
      setBackups(bk);
    } catch (e) {
      // transient load error
    }
  };

  const handleRunDiagnostics = async () => {
    setLoadingDiag(true);
    try {
      const rep = await systemApi.runDiagnostics();
      setDiagnostics(rep);
    } catch (e) {
      // transient diag error
    } finally {
      setLoadingDiag(false);
    }
  };

  const handleCreateBackup = async () => {
    try {
      const b = await systemApi.createBackup();
      setBackupMsg(`Backup snapshot created: ${b.filename}`);
      const bkList = await systemApi.listBackups();
      setBackups(bkList);
    } catch (e: any) {
      setBackupMsg(`Backup failed: ${e.message}`);
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflowY: "auto", padding: "20px", gap: "20px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ fontSize: "18px", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px" }}>
            <Activity size={20} color="var(--accent-primary)" /> System Diagnostics & Observability
          </h2>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
            Production health, subsystem status, performance metrics, and database integrity.
          </div>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            onClick={handleRunDiagnostics}
            disabled={loadingDiag}
            className="new-chat-btn"
            style={{ fontSize: "12px", padding: "6px 14px", gap: "6px" }}
          >
            <ShieldCheck size={14} /> {loadingDiag ? "Running..." : "Run Safe Diagnostics"}
          </button>
          <button
            onClick={handleCreateBackup}
            className="action-btn"
            style={{ fontSize: "12px", padding: "6px 14px", display: "flex", alignItems: "center", gap: "6px" }}
          >
            <Download size={14} /> Create Snapshot Backup
          </button>
        </div>
      </div>

      {backupMsg && (
        <div style={{ padding: "8px 14px", background: "rgba(16, 185, 129, 0.15)", color: "var(--status-green)", fontSize: "12px", borderRadius: "6px" }}>
          {backupMsg}
        </div>
      )}

      {/* Diagnostics Report Banner if ran */}
      {diagnostics && (
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
            <CheckCircle size={16} color="var(--status-green)" /> Diagnostics Summary ({diagnostics.checks_passed} Passed / {diagnostics.checks_failed} Failed)
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "8px" }}>
            {diagnostics.diagnostics.map((d, i) => (
              <div key={i} style={{ background: "var(--bg-tertiary)", padding: "8px 12px", borderRadius: "6px", fontSize: "11px" }}>
                <strong>{d.name}:</strong> <span style={{ color: d.status === "PASSED" ? "var(--status-green)" : "var(--status-red)" }}>{d.status}</span>
                <div style={{ color: "var(--text-muted)", marginTop: "2px" }}>{d.details}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Subsystem Health Matrix */}
      <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
          <Server size={16} color="var(--accent-primary)" /> Subsystem Health Matrix
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px" }}>
          {health?.subsystems.map((sub, i) => (
            <div key={i} style={{ background: "var(--bg-tertiary)", padding: "12px", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "12px" }}>{sub.name}</strong>
                <span style={{ fontSize: "10px", fontWeight: 700, color: sub.status === "HEALTHY" ? "var(--status-green)" : "var(--status-amber)" }}>
                  ● {sub.status}
                </span>
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                Latency: {sub.latency_ms} ms | {sub.details}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Metrics Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px" }}>
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "14px" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>REQUEST COUNT</div>
          <div style={{ fontSize: "20px", fontWeight: 800, marginTop: "4px", color: "var(--accent-primary)" }}>{metrics?.request_count || 0}</div>
          <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>Avg Latency: {metrics?.request_latency_ms || 0} ms</div>
        </div>

        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "14px" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>LLM INVOCATIONS</div>
          <div style={{ fontSize: "20px", fontWeight: 800, marginTop: "4px", color: "var(--status-amber)" }}>{metrics?.llm_request_count || 0}</div>
          <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>Avg Latency: {metrics?.llm_latency_ms || 0} ms</div>
        </div>

        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "14px" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>TOOL EXECUTIONS</div>
          <div style={{ fontSize: "20px", fontWeight: 800, marginTop: "4px", color: "var(--status-green)" }}>{metrics?.tool_execution_count || 0}</div>
          <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>All Tier 1/2 safe executions</div>
        </div>

        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "14px" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700 }}>CONFIRMATIONS</div>
          <div style={{ fontSize: "20px", fontWeight: 800, marginTop: "4px", color: "var(--status-red)" }}>{metrics?.confirmation_count || 0}</div>
          <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>Tier 2 authorizations handled</div>
        </div>
      </div>

      {/* 2-Pane: Event Timeline & Database Backups */}
      <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: "16px" }}>
        {/* Event Timeline */}
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px", maxHeight: "300px", overflowY: "auto" }}>
          <h3 style={{ fontSize: "13px", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "6px" }}>
            <Clock size={15} color="var(--accent-primary)" /> System Event Timeline
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {events.map((ev, i) => (
              <div key={i} style={{ background: "var(--bg-tertiary)", padding: "8px 10px", borderRadius: "6px", fontSize: "11px", display: "flex", justifyContent: "space-between" }}>
                <div>
                  <strong>{ev.operation}</strong> <span style={{ color: "var(--text-muted)" }}>({ev.component})</span>
                  <div style={{ color: "var(--text-muted)", fontSize: "10px" }}>{ev.details || "Executed"}</div>
                </div>
                <span style={{ fontSize: "10px", color: ev.status === "SUCCESS" ? "var(--status-green)" : "var(--status-amber)", fontWeight: 700 }}>
                  {ev.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Database Snapshots */}
        <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px", maxHeight: "300px", overflowY: "auto" }}>
          <h3 style={{ fontSize: "13px", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "6px" }}>
            <Database size={15} color="var(--accent-primary)" /> Database Snapshots ({backups.length})
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {backups.map((bk, i) => (
              <div key={i} style={{ background: "var(--bg-tertiary)", padding: "8px 10px", borderRadius: "6px", fontSize: "11px" }}>
                <strong>{bk.filename}</strong>
                <div style={{ color: "var(--text-muted)", fontSize: "10px" }}>Size: {(bk.size_bytes / 1024).toFixed(1)} KB | Integrity: {bk.integrity_status}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
