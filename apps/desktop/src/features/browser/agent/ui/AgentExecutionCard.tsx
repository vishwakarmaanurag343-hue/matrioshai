import { useEffect, useMemo, useRef, useState } from "react";
import { AgentEvent, AgentEventType, AgentTask } from "../types";
import { agentEventBus } from "../state/agentEvents";
import { BrowserTaskManager } from "../state/browserTaskState";
import { BrowserAgentHarness } from "../agentHarness";

/**
 * AGENT EXECUTION CARD — the structured runtime UI for the persistent
 * autonomous worker. Consumes the AgentEvent stream (never raw model
 * chain-of-thought) and mirrors the harness's honest progress estimate.
 * Rendered as a dedicated panel by BrowserView — never as a chat message.
 */

const STATUS_META: Record<string, { label: string; color: string; dot: string }> = {
  planning: { label: "Planning", color: "#2563eb", dot: "#2563eb" },
  running: { label: "Running", color: "#10b981", dot: "#10b981" },
  paused: { label: "Paused", color: "#6b7280", dot: "#6b7280" },
  waiting_user: { label: "Waiting for you", color: "#d97706", dot: "#d97706" },
  waiting_review: { label: "Ready for review", color: "#d97706", dot: "#d97706" },
  completed: { label: "Completed", color: "#10b981", dot: "#10b981" },
  failed: { label: "Failed", color: "#ef4444", dot: "#ef4444" },
  cancelled: { label: "Cancelled", color: "#6b7280", dot: "#6b7280" },
};

function eventIcon(type: AgentEventType, status: AgentEvent["status"]): { glyph: string; color: string } {
  switch (type) {
    case "WAITING_FOR_USER":
    case "USER_INPUT_REQUIRED":
      return { glyph: "⏸", color: "#d97706" };
    case "READY_FOR_REVIEW":
      return { glyph: "⏳", color: "#d97706" };
    case "STRATEGY_CHANGED":
    case "RECOVERY_STARTED":
      return { glyph: "↻", color: "#7c3aed" };
    case "CHECKPOINT":
      return { glyph: "◆", color: "#2563eb" };
    case "TASK_COMPLETED":
      return { glyph: "✓", color: "#10b981" };
    case "TASK_FAILED":
    case "TASK_CANCELLED":
      return { glyph: "✕", color: status === "error" ? "#ef4444" : "#6b7280" };
    default:
      if (status === "success") return { glyph: "✓", color: "#10b981" };
      if (status === "error") return { glyph: "✕", color: "#ef4444" };
      if (status === "warn") return { glyph: "⚠", color: "#d97706" };
      return { glyph: "↻", color: "#6b7280" };
  }
}

interface Props {
  task: AgentTask;
  currentAction: string;
  activeTabId?: string | null;
}

export function AgentExecutionCard({ task, currentAction, activeTabId }: Props) {
  const [expanded, setExpanded] = useState(true);
  const [events, setEvents] = useState<AgentEvent[]>(() => agentEventBus.eventsFor(task.taskId));
  const [progress, setProgress] = useState<number>(() => BrowserAgentHarness.getInstance().getProgress());
  const [perceptionLevel, setPerceptionLevel] = useState<string>(() =>
    BrowserAgentHarness.getInstance().getCurrentPerceptionLevel()
  );
  const listRef = useRef<HTMLDivElement | null>(null);
  const terminal = ["completed", "failed", "cancelled"].includes(task.status);
  const meta = STATUS_META[task.status] || STATUS_META.running;

  // Live event stream for THIS task + periodic progress/perception refresh.
  useEffect(() => {
    const unsub = agentEventBus.subscribe((e) => {
      if (e.task_id !== task.taskId) return;
      setEvents((prev) => [...prev.slice(-299), e]);
      setProgress(BrowserAgentHarness.getInstance().getProgress());
      setPerceptionLevel(BrowserAgentHarness.getInstance().getCurrentPerceptionLevel());
    });
    const tick = setInterval(() => {
      setProgress(BrowserAgentHarness.getInstance().getProgress());
      setPerceptionLevel(BrowserAgentHarness.getInstance().getCurrentPerceptionLevel());
    }, 1000);
    return () => {
      unsub();
      clearInterval(tick);
    };
  }, [task.taskId]);

  // Keep the activity checklist pinned to the newest event.
  useEffect(() => {
    if (expanded && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [events.length, expanded]);

  const visible = useMemo(() => events.slice(-40), [events]);
  const manager = BrowserTaskManager.getInstance();

  return (
    <div
      style={{
        background: "rgba(107, 33, 168, 0.05)",
        border: `1px solid ${terminal ? "rgba(107,33,168,0.15)" : "rgba(107, 33, 168, 0.35)"}`,
        borderRadius: "14px",
        padding: "10px 12px",
        marginBottom: "12px",
        flexShrink: 0,
      }}
    >
      {/* Header — always visible (collapsed state) */}
      <div
        onClick={() => setExpanded((v) => !v)}
        style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", userSelect: "none" }}
      >
        <span style={{ fontSize: "13px" }}>🤖</span>
        <span style={{ fontSize: "11px", fontWeight: 800, letterSpacing: "0.5px", color: "#6b21a8" }}>AGENT MODE</span>
        <span style={{ fontSize: "9.5px", fontWeight: 700, padding: "2px 7px", borderRadius: "9px", background: meta.color, color: "#fff", textTransform: "uppercase" }}>
          {meta.label}
        </span>
        {!terminal && (
          <div style={{ width: "7px", height: "7px", borderRadius: "50%", background: meta.dot, animation: "pulse 1.5s infinite" }} />
        )}
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)" }}>{progress}%</span>
        <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>{expanded ? "▾" : "▸"}</span>
      </div>

      <div
        onClick={() => setExpanded((v) => !v)}
        style={{
          marginTop: "4px",
          fontSize: "11.5px",
          fontWeight: 700,
          color: "var(--text-primary)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: expanded ? "normal" : "nowrap",
          cursor: "pointer",
        }}
      >
        Goal: {task.userGoal}
      </div>

      {expanded && (
        <>
          {/* Progress bar */}
          <div style={{ marginTop: "8px", height: "5px", borderRadius: "3px", background: "rgba(107,33,168,0.12)", overflow: "hidden" }}>
            <div
              style={{
                width: `${Math.max(2, Math.min(100, progress))}%`,
                height: "100%",
                background: `linear-gradient(90deg, #7c3aed, ${meta.color})`,
                transition: "width 0.6s ease",
              }}
            />
          </div>

          {/* Activity checklist — structured events only */}
          <div
            ref={listRef}
            className="no-scrollbar"
            style={{
              marginTop: "8px",
              maxHeight: "150px",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "3px",
              paddingRight: "2px",
            }}
          >
            {visible.length === 0 && (
              <div style={{ fontSize: "10.5px", color: "var(--text-muted)", fontStyle: "italic" }}>Starting worker…</div>
            )}
            {visible.map((e) => {
              const ic = eventIcon(e.type, e.status);
              return (
                <div key={e.id} style={{ display: "flex", alignItems: "baseline", gap: "6px", fontSize: "10.5px", lineHeight: 1.45 }}>
                  <span style={{ color: ic.color, fontWeight: 700, flexShrink: 0 }}>{ic.glyph}</span>
                  <span style={{ color: e.status === "error" ? "#ef4444" : e.status === "warn" ? "#b45309" : "var(--text-secondary)" }}>
                    {e.summary}
                    {e.evidence ? <span style={{ color: "var(--text-muted)" }}> · {e.evidence}</span> : null}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Current action + perception level */}
          {(currentAction || !terminal) && (
            <div style={{ marginTop: "7px", display: "flex", alignItems: "center", gap: "6px", fontSize: "10.5px", color: "var(--text-muted)" }}>
              {!terminal && <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#6b21a8", animation: "pulse 1.5s infinite", flexShrink: 0 }} />}
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontStyle: "italic" }}>
                {currentAction || "Working…"}
              </span>
              {perceptionLevel !== "dom" && (
                <span style={{ flexShrink: 0, fontSize: "9px", fontWeight: 700, padding: "1px 6px", borderRadius: "8px", background: "#fef3c7", color: "#92400e" }}>
                  perception: {perceptionLevel}
                </span>
              )}
            </div>
          )}

          {/* Collected evidence summary */}
          {(task.evidence?.length ?? 0) > 0 && (
            <div style={{ marginTop: "7px", borderTop: "1px solid rgba(107,33,168,0.12)", paddingTop: "6px" }}>
              <div style={{ fontSize: "9.5px", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                Evidence collected ({task.evidence!.length})
              </div>
              {task.evidence!.slice(-5).map((ev, i) => (
                <div key={i} style={{ fontSize: "10.5px", color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  • <strong>{ev.label}</strong>: {ev.value}
                  {ev.source ? <span style={{ color: "var(--text-muted)" }}> ({ev.source})</span> : null}
                </div>
              ))}
            </div>
          )}

          {/* Controls: Pause / Resume / Stop */}
          {!terminal && (
            <div style={{ display: "flex", gap: "6px", marginTop: "8px", justifyContent: "flex-end" }}>
              {task.status === "running" && (
                <button
                  onClick={(e) => { e.stopPropagation(); manager.pauseAgent(); }}
                  style={{ background: "#f59e0b", color: "#fff", border: "none", borderRadius: "6px", padding: "3px 10px", fontSize: "10.5px", fontWeight: 700, cursor: "pointer" }}
                >
                  Pause
                </button>
              )}
              {task.status === "paused" && activeTabId && (
                <button
                  onClick={(e) => { e.stopPropagation(); manager.resumeAgent(activeTabId); }}
                  style={{ background: "#10b981", color: "#fff", border: "none", borderRadius: "6px", padding: "3px 10px", fontSize: "10.5px", fontWeight: 700, cursor: "pointer" }}
                >
                  Resume
                </button>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); manager.stopAgent(); }}
                style={{ background: "#ef4444", color: "#fff", border: "none", borderRadius: "6px", padding: "3px 10px", fontSize: "10.5px", fontWeight: 700, cursor: "pointer" }}
              >
                Stop
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
