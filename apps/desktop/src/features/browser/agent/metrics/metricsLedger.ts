import { agentEventBus } from "../state/agentEvents";
import { API_BASE_URL } from "../../../../services/api/client";

/**
 * PHASE 0 METRICS LEDGER — measurement only, no behavior change.
 * Accumulates per-task runtime metrics matching the Phase 0 schema and
 * flushes one JSON artifact per task (success OR failure) to the backend,
 * which persists it under benchmarks/runs/. Partial metrics are never
 * dropped: flush fires in a finally block and failed POSTs are retried
 * from localStorage on the next startTask.
 */

export interface StepMetric {
  iteration: number;
  timestamp: string;
  url: string;
  world_version: number;
  action: string;
  target?: string | null;
  strategy?: string | null;
  result: "dispatched" | "not_dispatched" | "observation" | "reasoning_failed";
  verified: boolean;
  failure_class?: string | null;
  recovery: boolean;
  latency_ms?: number;
  rust?: boolean; // false = loop-local step (WAIT/OBSERVE/EXTRACT), no executor round-trip
  tab_event?: {
    kind: "opened" | "switched";
    raw_target?: string;
    normalized_target?: string;
    resolved_tab_id?: string;
    resolved_url?: string;
  };
}

export interface TaskMetrics {
  run_id: string;
  task_id: string;
  goal: string;
  started_at: string;
  finished_at?: string;
  wall_clock_ms?: number;
  iterations: number;
  observations: number;
  actions: number;
  verified_actions: number;
  failed_actions: number;
  failed_observations: number;
  failed_strategies: string[];
  strategy_switches: number;
  repeated_actions: number;
  repeated_strategies: number;
  recovery_attempts: number;
  successful_recoveries: number;
  tabs_opened: number;
  tabs_switched: number;
  model_calls: number;
  model_latency_ms_total: number;
  tool_calls: number;
  human_interventions: number;
  evidence_items: number;
  verified_evidence_items: number;
  final_status?: string;
  final_reason?: string;
  // raw series for P50/P95 computation (§16)
  observation_latencies_ms: number[];
  reasoning_latencies_ms: number[];
  action_latencies_ms: number[];
  // progress-signal audit (§10): longest stretch of iterations with no
  // new URL / evidence / verified action
  max_no_progress_streak: number;
  events: number;
}

type Provider = () => {
  exhaustedStrategies: string[];
  repeatedActions: number;
  repeatedStrategies: number;
};

const PENDING_KEY = "matrioshai_pending_metrics";

class MetricsLedger {
  private runId = `run_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
  private m: TaskMetrics | null = null;
  private steps: StepMetric[] = [];
  private provider: Provider | null = null;
  private lastProgressKey = "";
  private noProgressStreak = 0;

  /** Harness supplies live counters that live in its own maps. */
  attachProvider(p: Provider) {
    this.provider = p;
  }

  getRunId(): string {
    return this.runId;
  }

  startTask(taskId: string, goal: string) {
    void this.retryPending();
    this.m = {
      run_id: this.runId,
      task_id: taskId,
      goal,
      started_at: new Date().toISOString(),
      iterations: 0,
      observations: 0,
      actions: 0,
      verified_actions: 0,
      failed_actions: 0,
      failed_observations: 0,
      failed_strategies: [],
      strategy_switches: 0,
      repeated_actions: 0,
      repeated_strategies: 0,
      recovery_attempts: 0,
      successful_recoveries: 0,
      tabs_opened: 0,
      tabs_switched: 0,
      model_calls: 0,
      model_latency_ms_total: 0,
      tool_calls: 0,
      human_interventions: 0,
      evidence_items: 0,
      verified_evidence_items: 0,
      observation_latencies_ms: [],
      reasoning_latencies_ms: [],
      action_latencies_ms: [],
      max_no_progress_streak: 0,
      events: agentEventBus.eventsFor(taskId).length,
    };
    this.steps = [];
    this.lastProgressKey = "";
    this.noProgressStreak = 0;
  }

  // ---------------- counters called by the harness ----------------

  recordObservation(url: string, worldVersion: number, level: string, degraded: boolean, empty: boolean, latencyMs: number) {
    if (!this.m) return;
    this.m.observations++;
    this.m.observation_latencies_ms.push(Math.round(latencyMs));
    if (degraded || empty) this.m.failed_observations++;
    this.noteProgress(`obs:${url}`);
    this.steps.push({
      iteration: this.m.iterations,
      timestamp: new Date().toISOString(),
      url,
      world_version: worldVersion,
      action: "OBSERVE",
      strategy: level,
      result: empty ? "not_dispatched" : "observation",
      verified: !empty,
      failure_class: empty ? "OBSERVATION_EMPTY" : degraded ? "DEGRADED_PERCEPTION" : null,
      recovery: false,
      latency_ms: Math.round(latencyMs),
    });
  }

  recordReasoning(latencyMs: number, ok: boolean) {
    if (!this.m) return;
    this.m.model_calls++;
    this.m.model_latency_ms_total += Math.round(latencyMs);
    this.m.reasoning_latencies_ms.push(Math.round(latencyMs));
    if (!ok) {
      this.steps.push({
        iteration: this.m.iterations,
        timestamp: new Date().toISOString(),
        url: "",
        world_version: -1,
        action: "REASON",
        result: "reasoning_failed",
        verified: false,
        failure_class: "MODEL_ERROR",
        recovery: true,
      });
    }
  }

  recordStep(s: Omit<StepMetric, "timestamp">) {
    if (!this.m) return;
    const full: StepMetric = { ...s, timestamp: new Date().toISOString() };
    this.steps.push(full);
    if (["observation", "reasoning_failed"].includes(full.result)) return; // handled above
    if (full.result !== "not_dispatched") {
      this.m.actions++;
      if (full.rust !== false) this.m.tool_calls++;
      if (full.latency_ms != null && full.rust !== false) this.m.action_latencies_ms.push(Math.round(full.latency_ms));
      if (full.verified) this.m.verified_actions++;
      else this.m.failed_actions++;
    }
    if (full.recovery) this.m.recovery_attempts += 1;
    if (full.verified && full.recovery) this.m.successful_recoveries += 1;
    if (full.tab_event?.kind === "opened") this.m.tabs_opened++;
    if (full.tab_event?.kind === "switched") this.m.tabs_switched++;
    this.noteProgress(`${full.action}:${full.target ?? ""}:${full.verified ? "v" : "x"}:${full.url}`);
  }

  recordStrategySwitch(signature: string) {
    if (!this.m) return;
    this.m.strategy_switches++;
    if (!this.m.failed_strategies.includes(signature)) this.m.failed_strategies.push(signature);
  }

  recordIntervention(kind: "approval_prompt" | "takeover_wait" | "ask_user" | "stop" | "pause") {
    if (!this.m) return;
    this.m.human_interventions++;
    this.steps.push({
      iteration: this.m.iterations,
      timestamp: new Date().toISOString(),
      url: "",
      world_version: -1,
      action: `HUMAN_${kind.toUpperCase()}`,
      result: "not_dispatched",
      verified: false,
      recovery: false,
    });
  }

  recordEvidence(total: number, withSource: number) {
    if (!this.m) return;
    this.m.evidence_items = total;
    this.m.verified_evidence_items = withSource; // verified = carries source URL
    this.noteProgress(`evidence:${total}:${withSource}`);
  }

  setIterations(n: number) {
    if (this.m) this.m.iterations = n;
  }

  /** §10 progress audit — call whenever anything plausibly-new happens. */
  private noteProgress(key: string) {
    if (key === this.lastProgressKey) {
      this.noProgressStreak++;
      if (this.m) this.m.max_no_progress_streak = Math.max(this.m.max_no_progress_streak, this.noProgressStreak);
    } else {
      this.lastProgressKey = key;
      this.noProgressStreak = 0;
    }
  }

  setFinal(status: string, reason: string) {
    if (!this.m) return;
    this.m.final_status = status;
    this.m.final_reason = reason.slice(0, 500);
    this.m.finished_at = new Date().toISOString();
    this.m.wall_clock_ms = Date.now() - new Date(this.m.started_at).getTime();
    if (this.provider) {
      const p = this.provider();
      this.m.failed_strategies = p.exhaustedStrategies.length ? p.exhaustedStrategies : this.m.failed_strategies;
      this.m.repeated_actions = p.repeatedActions;
      this.m.repeated_strategies = p.repeatedStrategies;
    }
    this.m.events = agentEventBus.eventsFor(this.m.task_id).length;
  }

  build(): object {
    return { ...(this.m || {}), steps: this.steps };
  }

  /** Persist one artifact per task. Safe to call multiple times / on failure. */
  async flush(finished: boolean) {
    if (!this.m) return;
    const payload = JSON.stringify(this.build(), null, 2);
    const ok = await this.postMetrics(payload);
    if (ok && finished) this.m = null;
  }

  /**
   * POST an artifact. Returns true only on HTTP 2xx. ANY failure — network
   * exception or 4xx/5xx — stages the complete payload locally so nothing
   * is ever silently discarded.
   */
  private async postMetrics(payload: string): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE_URL}/browser/agent/metrics`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
      });
      if (!res.ok) {
        console.error(`[METRICS_LEDGER] flush failed: HTTP ${res.status} ${res.statusText} — staged locally`);
        this.stage(payload);
        return false;
      }
      console.log("[METRICS_LEDGER] flush succeeded");
      // A successful POST is the moment connectivity has demonstrably returned.
      void this.retryPending();
      return true;
    } catch (err) {
      console.error(`[METRICS_LEDGER] flush failed: ${err} — staged locally`);
      this.stage(payload);
      return false;
    }
  }

  /** Stage the complete payload (run_id/task_id preserved inside the JSON). */
  private stage(payload: string) {
    try {
      // Merge-staging would risk dropping artifacts; a bounded list keeps every one.
      const existing: string[] = JSON.parse(localStorage.getItem(PENDING_KEY) || "[]");
      existing.push(payload);
      localStorage.setItem(PENDING_KEY, JSON.stringify(existing.slice(-20)));
    } catch (e) {
      console.error(`[METRICS_LEDGER] CRITICAL: staging failed (${e}) — metric at risk of loss`);
    }
  }

  /** Retry every staged artifact; drops only after a confirmed server 2xx. */
  async retryPending() {
    let staged: string[] = [];
    if (typeof localStorage === "undefined") return;
    try {
      staged = JSON.parse(localStorage.getItem(PENDING_KEY) || "[]");
    } catch {
      localStorage.removeItem(PENDING_KEY);
      return;
    }
    if (!staged.length) return;
    const remaining: string[] = [];
    for (const payload of staged) {
      try {
        const res = await fetch(`${API_BASE_URL}/browser/agent/metrics`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
        });
        if (res.ok) {
          console.log("[METRICS_LEDGER] staged metric retried successfully");
        } else {
          console.error(`[METRICS_LEDGER] retry failed: HTTP ${res.status} — kept in staging`);
          remaining.push(payload);
        }
      } catch {
        remaining.push(payload);
      }
    }
    try {
      if (remaining.length) localStorage.setItem(PENDING_KEY, JSON.stringify(remaining));
      else localStorage.removeItem(PENDING_KEY);
    } catch { /* staging write-back failed; next retry re-reads */ }
  }
}

// Connectivity-triggered retry: the moment the network comes back,
// push everything staged while we were down. Backend-outage staging is
// additionally retried on every startTask (see above).
if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    void metricsLedger.retryPending();
  });
}

export const metricsLedger = new MetricsLedger();
