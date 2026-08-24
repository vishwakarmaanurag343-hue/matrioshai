import React, { useState, useEffect } from "react";
import {
  Bot,
  Play,
  Pause,
  XCircle,
  CheckCircle,
  AlertTriangle,
  History,
  Send,
  Loader2,
  Terminal
} from "lucide-react";
import { agentApi } from "../../services/api/agent";
import { workspacesApi } from "../../services/api/workspaces";
import { AgentTask, Workspace } from "../../types";

export const AgentView: React.FC = () => {
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [activeTask, setActiveTask] = useState<AgentTask | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>("");
  const [goalInput, setGoalInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"current" | "history">("current");

  useEffect(() => {
    loadData();
    const interval = setInterval(refreshActiveTask, 3000);
    return () => clearInterval(interval);
  }, [activeTask?.id]);

  const loadData = async () => {
    try {
      const [taskList, wsList] = await Promise.all([
        agentApi.listTasks(),
        workspacesApi.list(),
      ]);
      setTasks(taskList);
      setWorkspaces(wsList);
      if (wsList.length > 0 && !selectedWorkspaceId) {
        setSelectedWorkspaceId(wsList[0].id);
      }
      if (taskList.length > 0 && !activeTask) {
        setActiveTask(taskList[0]);
      }
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const refreshActiveTask = async () => {
    if (!activeTask) return;
    try {
      const updated = await agentApi.getTask(activeTask.id);
      setActiveTask(updated);
    } catch (e) {
      // ignore transient polling error
    }
  };

  const handleStartTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalInput.trim()) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const created = await agentApi.createTask(goalInput.trim(), selectedWorkspaceId || undefined);
      setActiveTask(created);
      setGoalInput("");
      setViewMode("current");
      await loadData();
    } catch (e: any) {
      setErrorMsg(`Failed to start agent task: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async () => {
    if (!activeTask) return;
    try {
      const updated = await agentApi.pauseTask(activeTask.id);
      setActiveTask(updated);
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleResume = async () => {
    if (!activeTask) return;
    try {
      const updated = await agentApi.resumeTask(activeTask.id);
      setActiveTask(updated);
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleCancel = async () => {
    if (!activeTask) return;
    try {
      const updated = await agentApi.cancelTask(activeTask.id);
      setActiveTask(updated);
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleApproveStep = async (stepId: string, approved: boolean) => {
    if (!activeTask) return;
    try {
      const updated = await agentApi.approveStep(activeTask.id, stepId, approved);
      setActiveTask(updated);
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return "var(--status-green)";
      case "RUNNING":
      case "PLANNING":
        return "var(--accent-primary)";
      case "AWAITING_APPROVAL":
        return "var(--status-amber)";
      case "FAILED":
      case "CANCELLED":
      case "EXPIRED":
        return "var(--status-red)";
      default:
        return "var(--text-muted)";
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Top Header */}
      <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Bot size={20} color="var(--accent-primary)" />
          <h2 style={{ fontSize: "16px", fontWeight: 700 }}>Agent Runtime & Controlled Autonomy</h2>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            className={`nav-item ${viewMode === "current" ? "active" : ""}`}
            onClick={() => setViewMode("current")}
            style={{ fontSize: "11px", padding: "4px 10px" }}
          >
            <Bot size={13} /> Active Task
          </button>
          <button
            className={`nav-item ${viewMode === "history" ? "active" : ""}`}
            onClick={() => setViewMode("history")}
            style={{ fontSize: "11px", padding: "4px 10px" }}
          >
            <History size={13} /> Task History ({tasks.length})
          </button>
        </div>
      </div>

      {errorMsg && (
        <div style={{ padding: "8px 16px", background: "rgba(239, 68, 68, 0.15)", color: "var(--status-red)", fontSize: "12px" }}>
          {errorMsg}
        </div>
      )}

      {/* Main Split: Goal Prompt Bar & Execution Panel */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "16px", overflowY: "auto" }}>
        {/* Goal Form */}
        <form onSubmit={handleStartTask} style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
          {workspaces.length > 0 && (
            <select
              value={selectedWorkspaceId}
              onChange={(e) => setSelectedWorkspaceId(e.target.value)}
              style={{ background: "var(--bg-tertiary)", color: "var(--text-primary)", border: "1px solid var(--border-color)", padding: "8px 12px", borderRadius: "6px", fontSize: "12px", outline: "none" }}
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          )}
          <input
            type="text"
            value={goalInput}
            onChange={(e) => setGoalInput(e.target.value)}
            placeholder="State your goal (e.g. Inspect package dependencies, run tests, and fix lint errors)..."
            style={{ flex: 1, background: "var(--bg-secondary)", border: "1px solid var(--border-color)", padding: "8px 12px", borderRadius: "6px", color: "var(--text-primary)", fontSize: "13px", outline: "none" }}
            disabled={loading}
          />
          <button type="submit" className="new-chat-btn" disabled={loading} style={{ padding: "8px 16px", fontSize: "13px" }}>
            {loading ? <Loader2 className="spinning" size={14} /> : <Send size={14} />} Execute Goal
          </button>
        </form>

        {viewMode === "current" && activeTask ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {/* Task Banner & Controls */}
            <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: "14px", fontWeight: 700, marginBottom: "4px" }}>Goal: {activeTask.user_goal}</div>
                <div style={{ fontSize: "12px", color: "var(--text-muted)", display: "flex", gap: "16px" }}>
                  <span>Status: <strong style={{ color: getStatusColor(activeTask.status) }}>{activeTask.status}</strong></span>
                  <span>Progress: <strong>{activeTask.steps_completed} / {activeTask.steps.length} steps</strong></span>
                  <span>Retries: <strong>{activeTask.retry_count} / {activeTask.max_retries}</strong></span>
                </div>
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                {activeTask.status === "RUNNING" && (
                  <button className="action-btn" onClick={handlePause} style={{ fontSize: "11px", gap: "4px" }}>
                    <Pause size={13} /> Pause
                  </button>
                )}
                {activeTask.status === "PAUSED" && (
                  <button className="new-chat-btn" onClick={handleResume} style={{ fontSize: "11px", gap: "4px" }}>
                    <Play size={13} /> Resume
                  </button>
                )}
                {["RUNNING", "PAUSED", "PLANNING", "AWAITING_APPROVAL"].includes(activeTask.status) && (
                  <button className="action-btn" onClick={handleCancel} style={{ fontSize: "11px", gap: "4px", color: "var(--status-red)" }}>
                    <XCircle size={13} /> Cancel
                  </button>
                )}
              </div>
            </div>

            {/* Steps Timeline */}
            <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px" }}>
              <h3 style={{ fontSize: "13px", fontWeight: 700, marginBottom: "12px", display: "flex", alignItems: "center", gap: "6px" }}>
                <Terminal size={14} color="var(--accent-primary)" /> Execution Plan Steps ({activeTask.steps.length})
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {activeTask.steps.map((step) => (
                  <div
                    key={step.id}
                    style={{
                      background: "var(--bg-tertiary)",
                      border: `1px solid ${step.status === "RUNNING" ? "var(--accent-primary)" : "var(--border-color)"}`,
                      borderRadius: "6px",
                      padding: "12px"
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontSize: "11px", fontWeight: 700, background: "var(--bg-primary)", padding: "2px 6px", borderRadius: "4px" }}>
                          Step {step.sequence}
                        </span>
                        <strong style={{ fontSize: "13px" }}>{step.objective}</strong>
                      </div>
                      <span style={{ fontSize: "11px", fontWeight: 700, color: getStatusColor(step.status) }}>
                        {step.status}
                      </span>
                    </div>

                    <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" }}>
                      Tool: <code>{step.tool_name}</code> {Object.keys(step.arguments).length > 0 && `| Args: ${JSON.stringify(step.arguments)}`}
                    </div>

                    {/* Tier 2 Approval Card */}
                    {step.status === "AWAITING_APPROVAL" && (
                      <div style={{ background: "rgba(245, 158, 11, 0.1)", border: "1px solid var(--status-amber)", borderRadius: "6px", padding: "10px", marginTop: "8px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--status-amber)", fontWeight: 700, fontSize: "12px", marginBottom: "6px" }}>
                          <AlertTriangle size={14} /> Tier 2 User Confirmation Required
                        </div>
                        <div style={{ fontSize: "12px", marginBottom: "8px" }}>
                          The agent is requesting permission to execute <code>{step.tool_name}</code> with side effects.
                        </div>
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button className="new-chat-btn" onClick={() => handleApproveStep(step.id, true)} style={{ fontSize: "11px", padding: "4px 10px" }}>
                            <CheckCircle size={12} /> Approve & Continue
                          </button>
                          <button className="action-btn" onClick={() => handleApproveStep(step.id, false)} style={{ fontSize: "11px", padding: "4px 10px", color: "var(--status-red)" }}>
                            <XCircle size={12} /> Reject Step
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Step Result Output */}
                    {step.result && (
                      <pre style={{ margin: "6px 0 0 0", padding: "8px", background: "var(--bg-primary)", borderRadius: "4px", fontSize: "11px", overflowX: "auto", color: "var(--text-primary)" }}>
                        {step.result}
                      </pre>
                    )}
                    {step.error && (
                      <div style={{ margin: "6px 0 0 0", padding: "8px", background: "rgba(239, 68, 68, 0.1)", borderRadius: "4px", fontSize: "11px", color: "var(--status-red)" }}>
                        {step.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : viewMode === "history" ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {tasks.map((t) => (
              <div
                key={t.id}
                onClick={() => { setActiveTask(t); setViewMode("current"); }}
                style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "6px", padding: "12px", cursor: "pointer" }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                  <strong>{t.user_goal}</strong>
                  <span style={{ fontSize: "11px", fontWeight: 700, color: getStatusColor(t.status) }}>{t.status}</span>
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  {t.steps_completed} steps completed | Created: {new Date(t.created_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "13px" }}>
            Enter a high-level goal above to initiate an autonomous agent task.
          </div>
        )}
      </div>
    </div>
  );
};
