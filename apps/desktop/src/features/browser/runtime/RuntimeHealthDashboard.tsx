import React, { useState, useEffect } from "react";
import { Activity, CheckCircle, AlertTriangle, XCircle, RefreshCw, Zap } from "lucide-react";

interface ComponentHealthItem {
  component_name: string;
  status: "HEALTHY" | "DEGRADED" | "UNAVAILABLE" | "FAILED" | "UNKNOWN";
  version: string;
  last_success?: string | null;
  last_failure?: string | null;
  consecutive_failures: number;
}

export const RuntimeHealthDashboard: React.FC = () => {
  const [healthData, setHealthData] = useState<Record<string, ComponentHealthItem>>({});
  const [runtimeState, setRuntimeState] = useState<string>("READY");
  const [metrics, setMetrics] = useState<any>({});
  const [loading, setLoading] = useState(false);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      const res = await fetch("http://127.0.0.1:8000/api/v1/browser/runtime/health");
      if (res.ok) {
        const data = await res.json();
        setHealthData(data.health.components || {});
        setRuntimeState(data.health.runtime_state || "READY");
      }
      const metricRes = await fetch("http://127.0.0.1:8000/api/v1/browser/runtime/metrics");
      if (metricRes.ok) {
        const data = await metricRes.json();
        setMetrics(data.metrics || {});
      }
    } catch (e) {
      // Backend may be in standalone or test mode
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleRestart = async (compName: string) => {
    try {
      await fetch("http://127.0.0.1:8000/api/v1/browser/runtime/supervisor/restart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ component_name: compName }),
      });
      fetchHealth();
    } catch (e) {}
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "HEALTHY":
        return <CheckCircle size={15} color="#10b981" />;
      case "DEGRADED":
        return <AlertTriangle size={15} color="#f59e0b" />;
      case "FAILED":
      case "UNAVAILABLE":
        return <XCircle size={15} color="#ef4444" />;
      default:
        return <Activity size={15} color="var(--text-muted)" />;
    }
  };

  const compList = Object.values(healthData);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Activity size={22} color="var(--accent-primary, #cba6f7)" />
          <div>
            <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 700 }}>Production Runtime & Subsystem Health</h2>
            <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
              Phase 14 Autonomous Runtime Supervisor, Circuit Breakers & Heartbeats
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              padding: "4px 10px",
              background: runtimeState === "RUNNING" ? "rgba(16, 185, 129, 0.2)" : "rgba(203, 166, 247, 0.2)",
              color: runtimeState === "RUNNING" ? "#10b981" : "var(--accent-primary, #cba6f7)",
              borderRadius: "6px",
              fontSize: "12px",
              fontWeight: 700,
            }}
          >
            STATE: {runtimeState}
          </div>
          <button onClick={fetchHealth} style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer" }}>
            <RefreshCw size={14} className={loading ? "spin" : ""} />
          </button>
        </div>
      </div>

      {/* Metrics Bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "10px" }}>
        <div style={{ background: "var(--bg-secondary, #1e1e2e)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color, #313244)" }}>
          <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Uptime</div>
          <div style={{ fontSize: "13px", fontWeight: 700, marginTop: "2px" }}>{metrics.uptime_seconds || 0}s</div>
        </div>
        <div style={{ background: "var(--bg-secondary, #1e1e2e)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color, #313244)" }}>
          <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Actions Executed</div>
          <div style={{ fontSize: "13px", fontWeight: 700, marginTop: "2px" }}>
            {metrics.actions_successful || 0} / {metrics.actions_total || 0}
          </div>
        </div>
        <div style={{ background: "var(--bg-secondary, #1e1e2e)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color, #313244)" }}>
          <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Avg Model Latency</div>
          <div style={{ fontSize: "13px", fontWeight: 700, marginTop: "2px" }}>{metrics.model_latency_avg_ms || 0} ms</div>
        </div>
        <div style={{ background: "var(--bg-secondary, #1e1e2e)", padding: "10px", borderRadius: "8px", border: "1px solid var(--border-color, #313244)" }}>
          <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase" }}>Circuit Breakers Open</div>
          <div style={{ fontSize: "13px", fontWeight: 700, marginTop: "2px", color: (metrics.circuit_breakers_open || 0) > 0 ? "#ef4444" : "#10b981" }}>
            {metrics.circuit_breakers_open || 0}
          </div>
        </div>
      </div>

      {/* Subsystem Health Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "10px" }}>
        {compList.map((comp) => (
          <div
            key={comp.component_name}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "10px 12px",
              background: "var(--bg-secondary, #1e1e2e)",
              border: "1px solid var(--border-color, #313244)",
              borderRadius: "8px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {getStatusIcon(comp.status)}
              <div>
                <div style={{ fontSize: "12px", fontWeight: 700 }}>{comp.component_name}</div>
                <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>v{comp.version} • {comp.status}</div>
              </div>
            </div>

            {comp.status !== "HEALTHY" && (
              <button
                onClick={() => handleRestart(comp.component_name)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  padding: "4px 8px",
                  background: "var(--accent-primary, #cba6f7)",
                  color: "#111",
                  border: "none",
                  borderRadius: "4px",
                  fontSize: "10px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                <Zap size={10} />
                Restart
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
