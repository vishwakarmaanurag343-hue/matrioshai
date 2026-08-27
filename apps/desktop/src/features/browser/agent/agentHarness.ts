import { nativeBrowserService } from "../../../services/browser/nativeService";
import { API_BASE_URL } from "../../../services/api/client";
import {
  ActionFailure,
  ActionVerificationResult,
  AgentDecision,
  AgentTask,
  EvidenceItem,
  ExpectedEffect,
  FailureCategory,
  PerceptionLevel,
  PlanStep,
  ReasoningRequest,
  StepRecord,
  TabWorldState,
  SessionCheckpoint,
} from "./types";
import { PageModel, ResolvedElement, SemanticTarget } from "./perception/pageModel";
import { ElementResolver } from "./perception/elementResolver";
import { ActionVerifier } from "./execution/actionVerifier";
import { StepReasoner } from "./reasoning/stepReasoner";
import { PerceptionLadder, isObservationEmpty } from "./perception/perceptionLadder";
import { agentEventBus } from "./state/agentEvents";
import { metricsLedger } from "./metrics/metricsLedger";
import { securityKernel } from "./security/securityKernel";

export type HarnessState =
  | "IDLE"
  | "UNDERSTANDING"
  | "PLANNING"
  | "OBSERVING"
  | "REASONING"
  | "RESOLVING"
  | "VALIDATING"
  | "EXECUTING"
  | "WAITING"
  | "WAITING_FOR_APPROVAL"
  | "WAITING_FOR_USER"
  | "VERIFYING"
  | "RECOVERING"
  | "PAUSED"
  | "COMPLETED"
  | "FAILED"
  | "STOPPED";

export interface ApprovalRequest {
  action: string;
  target?: string | null;
  value?: string | null;
  description: string;
}

export class BrowserAgentHarness {
  private static instance: BrowserAgentHarness;
  private state: HarnessState = "IDLE";
  private activeTask: AgentTask | null = null;
  private paused: boolean = false;
  private stopped: boolean = false;
  // Goal-mode (unified runtime) state
  private goalMode: boolean = false;
  private resumeRequested: boolean = false;
  private history: StepRecord[] = [];
  private goalConstraints: string[] = [];
  // Persistent-worker state: retries, strategies, multi-tab world model
  private actionAttempts: Map<string, number> = new Map();   // `${action}:${target}` -> attempts
  private strategyFailures: Map<string, number> = new Map(); // `${category}@${level}` -> count
  private exhaustedStrategies: string[] = [];
  private tabStates: Map<string, TabWorldState> = new Map();
  private currentLevel: PerceptionLevel = "dom";
  private lastProgress: number = 0;
  private recoveryPending: boolean = false; // PHASE 0: recovery landed since the last verified action
  // Bridges injected by the UI layer (BrowserView / BrowserTaskManager)
  private messageSink: ((text: string, kind: "info" | "success" | "error" | "warn") => void) | null = null;
  private approvalBridge: ((req: ApprovalRequest) => Promise<boolean>) | null = null;
  private createTabBridge: ((url: string) => Promise<string>) | null = null;
  private listeners: ((task: AgentTask | null, state: HarnessState, traceLog?: string) => void)[] = [];

  private constructor() {}

  /** Wire a chat sink so ANSWER/DONE/ASK_USER text reaches the Browser AI panel. */
  setMessageSink(sink: (text: string, kind: "info" | "success" | "error" | "warn") => void) {
    this.messageSink = sink;
  }

  /** Wire the sensitive-action approval gate (returns the user's decision). */
  setApprovalBridge(bridge: (req: ApprovalRequest) => Promise<boolean>) {
    this.approvalBridge = bridge;
  }

  /** Wire native tab creation (needs UI-owned bounds/profile context). */
  setCreateTabBridge(bridge: (url: string) => Promise<string>) {
    this.createTabBridge = bridge;
  }

  private emit(text: string, kind: "info" | "success" | "error" | "warn" = "info") {
    if (this.messageSink) this.messageSink(text, kind);
  }

  static getInstance(): BrowserAgentHarness {
    if (!BrowserAgentHarness.instance) {
      BrowserAgentHarness.instance = new BrowserAgentHarness();
    }
    return BrowserAgentHarness.instance;
  }

  subscribe(listener: (task: AgentTask | null, state: HarnessState, traceLog?: string) => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  private notify(traceLog?: string) {
    this.listeners.forEach((l) => l(this.activeTask, this.state, traceLog));
  }

  private logTrace(phase: string, data: Record<string, any>) {
    const formatted = `[${phase}]\n` + Object.entries(data).map(([k, v]) => `  ${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join("\n");
    console.log(formatted);
    this.notify(formatted);
  }

  getState(): HarnessState {
    return this.state;
  }

  /**
   * Fresh Live Observation through the universal perception ladder.
   * L1 DOM → L2 semantic tree → L3 rendered text/geometry → escalate honestly.
   */
  async observePage(tabId?: string): Promise<PageModel> {
    this.state = "OBSERVING";
    const id = tabId || "unknown";
    const obsT0 = performance.now();
    const result = await PerceptionLadder.observe(id);
    const obsMs = performance.now() - obsT0;
    this.currentLevel = result.level;

    // Multi-tab world model bookkeeping
    const ws = this.tabStates.get(id) || { tab_id: id, url: "", title: "", observation_level: result.level, version: 0 };
    if (ws.url !== result.model.url || ws.title !== result.model.title) {
      // Page changed under us — element ids from the old page version are void
      ws.version++;
    }
    ws.url = result.model.url;
    ws.title = result.model.title;
    ws.observation_level = result.level;
    this.tabStates.set(id, ws);

    // PHASE 0 measurement
    metricsLedger.recordObservation(result.model.url, ws.version, result.level, result.degraded, isObservationEmpty(result.model), obsMs);

    this.logTrace("OBSERVATION", {
      url: result.model.url,
      title: result.model.title,
      level: result.level,
      degraded: result.degraded,
      elementsCount: result.model.links.length + result.model.buttons.length + result.model.inputs.length + result.model.selects.length,
      textBlocks: result.model.textBlocks?.length ?? 0,
      searchResultsCount: result.model.searchResults.length,
      observationStatus: result.model.observationStatus,
    });
    return result.model;
  }

  /** Latest honest progress estimate for the execution card. */
  getProgress(): number {
    return this.lastProgress;
  }

  getCurrentPerceptionLevel(): PerceptionLevel {
    return this.currentLevel;
  }

  // =========================================================================
  // PERSISTENT WORKER: failure diagnosis, retry policy, strategy escalation
  // =========================================================================

  /** Map an unverified step's context onto a structured failure category. */
  private classifyFailure(opts: {
    decision: AgentDecision;
    execError?: string;
    resolutionFailed?: boolean;
    observationEmpty?: boolean;
    effectDetail?: string;
    url: string;
    pageTitle: string;
    attempt: number;
  }): ActionFailure {
    const blob = `${opts.execError || ""} ${opts.effectDetail || ""}`.toLowerCase();
    let category: FailureCategory = "VERIFICATION_FAILED";

    if (opts.resolutionFailed) category = "TARGET_NOT_FOUND";
    else if (opts.observationEmpty) category = "OBSERVATION_EMPTY";
    else if (/captcha|recaptcha|are you a robot|human verification/.test(blob)) category = "CAPTCHA";
    else if (/login|sign in|signin|otp|two-factor|2fa|password/.test(blob)) category = "AUTH_REQUIRED";
    else if (/blocked|forbidden|403|access denied|unavailable in your region/.test(blob)) category = "BLOCKED";
    else if (/approval|permission|denied by user/.test(blob)) category = "PERMISSION_REQUIRED";
    else if (/timed?\s?out|timeout/.test(blob)) category = "TIMEOUT";
    else if (/navigate|navigation|net::|err_|load failed|about:blank/.test(blob)) category = "NAVIGATION_FAILED";
    else if (opts.decision.action.toUpperCase() === "EXTRACT") category = "EXTRACTION_FAILED";

    return {
      category,
      action: opts.decision.action,
      target: opts.decision.target ?? null,
      page: opts.pageTitle.slice(0, 120),
      url: opts.url,
      attempt: opts.attempt,
      evidence: (opts.effectDetail || opts.execError || "postcondition not observed").slice(0, 240),
    };
  }

  private bumpStrategyFailure(failure: ActionFailure, level: PerceptionLevel): number {
    const key = `${failure.category}@${level}`;
    const n = (this.strategyFailures.get(key) || 0) + 1;
    this.strategyFailures.set(key, n);
    if (n >= 2 && !this.exhaustedStrategies.includes(`${key} x${n}`)) {
      this.exhaustedStrategies.push(`${key} x${n}`);
    }
    return n;
  }

  /** Retry policy: same action+target max 2 attempts; same strategy max 2. */
  private activeSubgoal: string | null = null;

  private recoveryConstraints(failure: ActionFailure | null, actUpper: string, target: string | null | undefined): string[] {
    const notes: string[] = [];
    if (!failure) return notes;
    const akey = `${actUpper}:${target || ""}`;
    const attempts = this.actionAttempts.get(akey) || 0;
    if (attempts >= 2) {
      notes.push(`RECOVERY: ${actUpper} on ${target} already failed ${attempts} times — you MUST choose a different element, section, tab or discovery route.`);
    }
    const skey = `${failure.category}@${this.currentLevel}`;
    if ((this.strategyFailures.get(skey) || 0) >= 2) {
      notes.push(`RECOVERY: ${failure.category} failed twice at perception level '${this.currentLevel}' — the runtime will escalate perception; change your approach/route too.`);
    }
    return notes;
  }

  /** Generic gate detection — no site-specific patterns, plain UI semantics. */
  private detectAuthGate(model: PageModel): { kind: "login" | "captcha" | "consent"; summary: string } | null {
    const hay = [
      model.url.toLowerCase(),
      model.title.toLowerCase(),
      ...model.sections.map((s) => s.toLowerCase()),
      ...(model.textBlocks || []).slice(0, 6).map((t) => t.toLowerCase()),
      ...model.inputs.filter((i) => i.sensitive || String(i.inputType).toLowerCase() === "password").map(() => "password field"),
    ].join(" ");
    if (/captcha|are you a robot|human verification|recaptcha/.test(hay)) {
      return { kind: "captcha", summary: "CAPTCHA detected — human verification required." };
    }
    if (/log ?in|sign ?in|create account|otp|one[- ]time (code|password)|two[- ]factor/.test(hay) && model.inputs.some((i) => i.sensitive || /password|otp|code/.test(`${i.name || ""} ${String(i.inputType || "")}`))) {
      return { kind: "login", summary: "Login/authentication required to continue." };
    }
    return null;
  }

  /**
   * Resolves a semantic target against the live page observation.
   */
  resolveTarget(target: SemanticTarget | string, pageModel: PageModel): ResolvedElement | null {
    this.state = "RESOLVING";
    const resolved = ElementResolver.resolveBestCandidate(target, pageModel);
    if (resolved) {
      this.logTrace("RESOLUTION", {
        strategy: resolved.strategy,
        confidence: resolved.confidence,
        reason: resolved.reason,
        targetText: resolved.text,
        targetHref: resolved.href,
        fingerprint: resolved.fingerprint,
      });
    } else {
      this.logTrace("RESOLUTION_FAILED", {
        target,
        availableResults: pageModel.searchResults.length,
      });
    }
    return resolved;
  }

  /**
   * Pre-action validation before dispatching to WKWebView.
   */
  validateAction(action: string, resolved: ResolvedElement, pageModel: PageModel): { valid: boolean; reason?: string } {
    this.state = "VALIDATING";

    if (!resolved || !resolved.element) {
      return { valid: false, reason: "Target element is null or unresolved." };
    }

    if (resolved.confidence < 0.70) {
      return { valid: false, reason: `Low match confidence (${resolved.confidence.toFixed(2)} < 0.70 threshold).` };
    }

    // Check if element belongs to active page model
    const exists = pageModel.links
      .concat(pageModel.buttons)
      .concat(pageModel.inputs)
      .some((e) => e.id === resolved.element.id);

    if (!exists) {
      return { valid: false, reason: "Resolved element does not exist in the current page observation." };
    }

    if (resolved.element.sensitive && action.toUpperCase() === "TYPE") {
      return { valid: false, reason: "Security violation: Cannot automate typing into sensitive fields." };
    }

    this.logTrace("VALIDATION", {
      valid: true,
      action,
      elementId: resolved.element.id,
      targetHref: resolved.href,
    });

    return { valid: true };
  }

  /**
   * Executes verified action inside native WKWebView.
   */
  async executeAction(
    tabId: string,
    action: string,
    resolved?: ResolvedElement | null,
    value?: string,
    targetUrlOrParam?: string
  ): Promise<{ success: boolean; error?: string }> {
    this.state = "EXECUTING";
    const actUpper = action.toUpperCase();

    if (actUpper === "EXTRACT" || actUpper === "READ") {
      return { success: true };
    }

    const effectiveTarget = targetUrlOrParam || resolved?.element.id || resolved?.href;

    this.logTrace("EXECUTION", {
      action: actUpper,
      elementId: resolved?.element.id,
      targetHref: resolved?.href || targetUrlOrParam,
      value: value ? "[PROVIDED]" : undefined,
    });

    try {
      const res = await nativeBrowserService.executeAIAction(
        tabId,
        actUpper,
        effectiveTarget || undefined,
        value,
        true // userApproved
      );

      if (!res.success && res.approval_required) {
        return { success: false, error: "Action requires explicit user confirmation." };
      }

      return { success: res.success, error: res.message };
    } catch (err: any) {
      return { success: false, error: err.message || "Failed to execute native action." };
    }
  }

  /**
   * Waits for DOM layout stabilization.
   */
  async waitForPageStability(tabId: string, durationMs: number = 700): Promise<void> {
    this.state = "WAITING";
    this.logTrace("WAIT", { durationMs });
    await new Promise((r) => setTimeout(r, durationMs));
    try {
      let prevLen = 0;
      for (let i = 0; i < 3; i++) {
        const sem = await nativeBrowserService.inspectPage(tabId);
        const currLen = (sem.text_blocks || []).join("").length;
        if (prevLen > 0 && Math.abs(currLen - prevLen) < 10) {
          break;
        }
        prevLen = currLen;
        await new Promise((r) => setTimeout(r, 250));
      }
    } catch {}
  }

  /**
   * Post-action verification.
   */
  async verifyAction(
    beforeModel: PageModel,
    resolved: ResolvedElement | null,
    tabId: string,
    actionName: string = "CLICK",
    targetParam?: string
  ): Promise<ActionVerificationResult> {
    this.state = "VERIFYING";
    const afterModel = await this.observePage(tabId);
    const actUpper = actionName.toUpperCase();

    if (actUpper === "EXTRACT" || actUpper === "READ" || actUpper === "WAIT" || actUpper === "SCROLL") {
      return {
        success: true,
        changed: false,
        message: `Observation extracted from ${afterModel.url || afterModel.title}`,
        beforeUrl: beforeModel.url,
        afterUrl: afterModel.url,
        domMutated: false,
      };
    }

    const beforeSnap = {
      url: beforeModel.url,
      title: beforeModel.title,
      headings: beforeModel.sections,
      text_blocks: [],
      interactive_elements: beforeModel.links,
      forms_count: beforeModel.formsCount,
      tables_count: beforeModel.tablesCount,
      links_count: beforeModel.links.length,
      timestamp: beforeModel.timestamp,
    };

    const afterSnap = {
      url: afterModel.url,
      title: afterModel.title,
      headings: afterModel.sections,
      text_blocks: [],
      interactive_elements: afterModel.links,
      forms_count: afterModel.formsCount,
      tables_count: afterModel.tablesCount,
      links_count: afterModel.links.length,
      timestamp: afterModel.timestamp,
    };

    const result = ActionVerifier.verifyTransition(
      actUpper,
      targetParam || resolved?.element.id,
      beforeSnap,
      afterSnap
    );

    // If we clicked a link with an expected destination, check if destination domain matches
    let domainVerified = true;
    if (resolved && resolved.href) {
      try {
        const expectedHost = new URL(resolved.href).hostname.replace(/^www\./, "");
        const actualHost = new URL(afterModel.url).hostname.replace(/^www\./, "");
        if (expectedHost && actualHost && !actualHost.includes("google.") && !actualHost.includes(expectedHost) && !expectedHost.includes(actualHost)) {
          domainVerified = false;
        }
      } catch {}
    }

    const overallSuccess = result.success && domainVerified;

    this.logTrace("VERIFICATION", {
      success: overallSuccess,
      beforeUrl: beforeModel.url,
      afterUrl: afterModel.url,
      domMutated: result.domMutated,
      domainVerified,
    });

    return {
      success: overallSuccess,
      changed: result.changed,
      message: result.message,
      beforeUrl: beforeModel.url,
      afterUrl: afterModel.url,
      domMutated: result.domMutated,
    };
  }

  // =========================================================================
  // UNIFIED AGENT RUNTIME — the canonical goal loop.
  // GOAL → OBSERVE → REASON → VALIDATE → APPROVE → RESOLVE → EXECUTE (native,
  // verified Rust executor) → VERIFY expected_effect → RECORD → repeat until
  // ANSWER / DONE / WAITING_FOR_USER / FAIL. There is no other execution path:
  // the legacy template-planner loop (executeTask/startTask) was removed in
  // Phase 1.
  // =========================================================================

  /** True while a unified-runtime goal run is active or awaiting user input. */
  isGoalMode(): boolean {
    return this.goalMode;
  }

  getHistory(): StepRecord[] {
    return [...this.history];
  }

  /** Feed the user's answer into a paused ASK_USER run and continue it. */
  provideUserResponse(answer: string, tabId: string): void {
    if (!this.goalMode || !this.activeTask) return;
    this.history.push({
      iteration: this.history.length + 1,
      action: "USER_RESPONSE",
      value: answer.slice(0, 200),
      dispatched: false,
      verified: false,
      note: "User provided requested information",
    });
    this.emit(`Received your input — resuming task…`, "info");
    if (["waiting_user", "paused"].includes(this.activeTask.status as string)) {
      this.activeTask.status = "running";
    }
    void this.continueGoalLoop(tabId, (this.activeTask.currentStepIndex ?? 0) + 1);
  }

  /**
   * The autonomous loop. Resolves when the run reaches ANSWER/DONE/FAIL,
   * pauses for approval/user takeover, or exhausts bounds.
   */
  async executeGoal(goal: string, tabId: string, constraints: string[] = []): Promise<AgentTask | null> {
    const taskId = `goal_${Date.now()}`;
    this.goalMode = true;
    this.paused = false;
    this.stopped = false;
    this.resumeRequested = false;
    this.history = [];
    this.goalConstraints = [...constraints];
    this.actionAttempts = new Map();
    this.strategyFailures = new Map();
    this.exhaustedStrategies = [];
    this.tabStates = new Map();
    this.lastProgress = 0;
    this.state = "PLANNING";

    const task: AgentTask = {
      taskId,
      userGoal: goal,
      mode: "general",
      steps: [],
      currentStepIndex: 0,
      status: "running",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      visitedUrls: [],
      extractedFacts: [],
      sources: [],
      evidence: [],
      failedStrategies: [],
    };
    this.activeTask = task;
    this.activeSubgoal = null;

    // PHASE 0: per-task metrics artifact (measurement only)
    metricsLedger.attachProvider(() => ({
      exhaustedStrategies: [...this.exhaustedStrategies],
      repeatedActions: [...this.actionAttempts.values()].filter((n) => n >= 2).length,
      repeatedStrategies: [...this.strategyFailures.values()].filter((n) => n >= 2).length,
    }));
    metricsLedger.startTask(taskId, goal);
    // PHASE 0: explicit RUN_START boundary (fire-and-forget; never blocks the loop)
    void fetch(`${API_BASE_URL}/browser/agent/metrics/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: metricsLedger.getRunId(), task_id: taskId, goal }),
    }).catch(() => { /* marker is best-effort; ledger flush carries the durable record */ });

    agentEventBus.publish(taskId, "TASK_STARTED", `Goal accepted: ${goal}`, "info");
    this.logTrace("GOAL_START", { taskId, goal });
    return await this.continueGoalLoop(tabId, 0);
  }

  private async continueGoalLoop(startTabId: string, startIteration: number): Promise<AgentTask | null> {
    const MAX_ITERATIONS = 25;
    const task = this.activeTask;
    if (!task) return null;

    let currentTabId = startTabId;
    let consecutiveFailures = 0;

    try {
      for (let iteration = startIteration; iteration < MAX_ITERATIONS && !this.stopped; iteration++) {
        task.currentStepIndex = iteration;
        task.updatedAt = new Date().toISOString();
        metricsLedger.setIterations(iteration + 1);

        // Pause gate (keeps ONE live loop; resume just clears the flag)
        while (this.paused && !this.stopped) {
          this.state = "PAUSED";
          this.notify();
          await new Promise((r) => setTimeout(r, 300));
        }
        if (this.stopped) break;

        // ---------- 1. OBSERVE (perception ladder + world model) ----------
        this.state = "OBSERVING";
        agentEventBus.publish(task.taskId, "OBSERVING", `Reading ${this.tabStates.get(currentTabId)?.url || "current tab"}`, "info");
        let beforeModel = await this.observePage(currentTabId);
        const ws = this.tabStates.get(currentTabId);
        if (ws && ws.observation_level !== "dom") {
          agentEventBus.publish(task.taskId, "RECOVERY_STARTED", `Primary DOM extraction empty — perception escalated to '${ws.observation_level}'`, "warn", ws.observation_level);
        }

        // AUTH / CAPTCHA gate — recognize the blocker, hand control to the
        // user, keep the SAME task alive and resume on state change.
        const authGate = this.detectAuthGate(beforeModel);
        if (authGate) {
          agentEventBus.publish(task.taskId, "HUMAN_TAKEOVER_REQUIRED", authGate.summary, "warn", beforeModel.url);
          agentEventBus.publish(task.taskId, "WAITING_FOR_USER", authGate.summary, "warn", beforeModel.url);
          this.createCheckpoint(currentTabId, beforeModel.url, beforeModel.title, authGate.summary, authGate.kind);
          this.emit(`⏸️ **${authGate.summary}** Take over in the browser — I'll resume automatically when you're done.`, "warn");
          this.recordStep(iteration, { action: "WAIT_FOR_USER", reason: authGate.summary, expected_effect: { type: "none" }, requires_approval: false } as any, false, false, beforeModel.url, beforeModel.url, authGate.kind);
          task.status = "waiting_user";
          this.state = "WAITING_FOR_USER";
          this.notify();
          const resumed = await this.waitForTakeover(currentTabId, beforeModel.url, beforeModel.title);
          if (this.stopped) break;
          if (!resumed) return task;
          task.status = "running";
          agentEventBus.publish(task.taskId, "CHECKPOINT", `State change detected after ${authGate.kind} — resuming same task`, "success", beforeModel.url);
          continue;
        }

        let tabs: { tab_id: string; url: string; title: string; active: boolean }[] = [];
        try {
          const nativeTabs = await nativeBrowserService.getAllTabs();
          tabs = (nativeTabs || []).map((t) => ({ tab_id: t.id, url: t.url || "", title: t.title || "", active: t.id === currentTabId }));
        } catch {}

        // ---------- 2. REASON ----------
        this.state = "REASONING";
        this.notify();
        const request: ReasoningRequest = {
          goal: task.userGoal,
          url: beforeModel.url,
          title: beforeModel.title,
          ready_state: "complete",
          headings: beforeModel.sections.map((h) => securityKernel.sanitizeScrapedText(h).safeText),
          text_blocks: (beforeModel.textBlocks || [])
            .slice(0, 8)
            .map((t) => securityKernel.sanitizeScrapedText(t).safeText),
          interactive_elements: beforeModel.links.concat(beforeModel.buttons).concat(beforeModel.inputs).concat(beforeModel.selects).map((e) => ({
            element_id: e.id,
            role: e.role,
            name: e.name || e.text || "",
            tag: e.tag,
            href: e.href,
            placeholder: e.placeholder,
            aria_label: e.ariaLabel,
            input_type: e.inputType,
            value: e.value,
            disabled: e.disabled,
            sensitive: !!e.sensitive,
            tab_id: currentTabId,
            page_version: ws?.version ?? 0,
          })),
          tabs,
          history: this.history,
          // Retry-policy notes derived from the most recent structured failure
          constraints: (() => {
            const lastFailed = [...this.history].reverse().find((h) => h.failure);
            return [
              ...this.goalConstraints,
              ...this.recoveryConstraints(lastFailed?.failure || null, lastFailed?.action || "", lastFailed?.target),
            ];
          })(),
          failed_strategies: this.exhaustedStrategies,
          observation_level: this.currentLevel,
          subgoal: this.activeSubgoal || undefined,
          accumulated_evidence: task.evidence && task.evidence.length ? task.evidence.slice(0, 15) : undefined,
        };

        let decision: AgentDecision;
        const reasonT0 = performance.now();
        try {
          decision = await StepReasoner.nextStep(request);
          metricsLedger.recordReasoning(performance.now() - reasonT0, true);
        } catch (err: any) {
          metricsLedger.recordReasoning(performance.now() - reasonT0, false);
          this.logTrace("REASONING_FAILED", { error: err?.message || String(err) });
          consecutiveFailures++;
          if (consecutiveFailures >= 2) {
            this.finishRun("failed", `The reasoning layer could not produce a valid decision (${err?.message || err}).`);
            return task;
          }
          agentEventBus.publish(task.taskId, "RECOVERY_STARTED", `Reasoning rejected — retrying with feedback`, "warn");
          await new Promise((r) => setTimeout(r, 800));
          iteration--; // retry same iteration
          continue;
        }
        consecutiveFailures = Math.max(0, consecutiveFailures - 1);
        if (decision.subgoal) {
          this.activeSubgoal = decision.subgoal;
        }
        if (typeof decision.progress_estimate === "number" && !Number.isNaN(decision.progress_estimate)) {
          this.lastProgress = decision.progress_estimate;
          task.updatedAt = new Date().toISOString();
        }

        this.logTrace("REASONING", {
          action: decision.action,
          target: decision.target ?? undefined,
          effect: `${decision.expected_effect.type}${decision.expected_effect.target ? ":" + decision.expected_effect.target : ""}`,
          reason: decision.reason,
        });
        agentEventBus.publish(task.taskId, "ACTION_PROPOSED",
          `${decision.action}${decision.target ? ` ${decision.target}` : ""} — ${decision.reason}`.slice(0, 200),
          "info");

        // ---------- 3. TERMINAL DECISIONS ----------
        const actUpper = decision.action.toUpperCase();

        if (actUpper === "ANSWER" || actUpper === "DONE") {
          // STEP 8 RECOVERY: Early-Completion Safety Gate
          // Require evidence for research/comparison/multi-item goals
          const isResearchGoal = /search|find|compare|price|title|specs|what is|how many/i.test(task.userGoal);
          const hasEvidence = (task.evidence && task.evidence.length > 0) || (decision.evidence && decision.evidence.length > 0);

          if (isResearchGoal && !hasEvidence && iteration < 5) {
            this.logTrace("PREMATURE_COMPLETION_REJECTED", { goal: task.userGoal, iteration });
            this.emit("⚠️ Rejected premature completion — research goal requires verified evidence first.", "warn");
            agentEventBus.publish(task.taskId, "RECOVERY_STARTED", "Premature completion rejected — evidence collection required", "warn");
            decision.action = "OBSERVE"; // convert to OBSERVE to force evidence extraction
          } else {
            if (actUpper === "ANSWER") {
              this.emit(`**${decision.value || decision.reason}**`, "success");
              this.mergeEvidence(task, decision.evidence, currentTabId);
              agentEventBus.publish(task.taskId, "TASK_COMPLETED", decision.value?.slice(0, 200) || "Question answered", "success");
              this.recordStep(iteration, decision, false, false, beforeModel.url, beforeModel.url, "Answered from observation");
              this.finishRun("completed", decision.value || decision.reason);
              return task;
            }
            if (actUpper === "DONE") {
              this.emit(`✅ **Task complete.** ${decision.value || ""}`.trim(), "success");
              this.mergeEvidence(task, decision.evidence, currentTabId);
              agentEventBus.publish(
                task.taskId,
                "TASK_COMPLETED",
                (decision.value || "Goal achieved").slice(0, 220),
                "success",
                task.evidence && task.evidence.length
                  ? task.evidence.map((e) => `${e.label}: ${e.value} (${e.source})`).join(" | ").slice(0, 400)
                  : undefined
              );
              this.recordStep(iteration, decision, false, true, beforeModel.url, beforeModel.url, "Goal achieved");
              this.finishRun("completed", decision.value || "Goal achieved");
              return task;
            }
          }
        }
        if (actUpper === "FAIL") {
          this.emit(`❌ **Could not complete the task.** ${decision.value || decision.reason}`, "error");
          agentEventBus.publish(task.taskId, "TASK_FAILED", (decision.value || decision.reason).slice(0, 220), "error", `strategies exhausted: ${this.exhaustedStrategies.join("; ") || "none recorded"}`);
          this.recordStep(iteration, decision, false, false, beforeModel.url, beforeModel.url, decision.value || "Agent gave up");
          this.finishRun("failed", decision.value || decision.reason);
          return task;
        }
        if (actUpper === "ASK_USER" || actUpper === "WAIT_FOR_USER") {
          const msg = decision.message || decision.reason || "I need your help to continue.";
          this.emit(`⏸️ ${msg}`, "warn");
          agentEventBus.publish(task.taskId, "WAITING_FOR_USER", msg.slice(0, 200), "warn");
          if (actUpper === "ASK_USER") {
            agentEventBus.publish(task.taskId, "USER_INPUT_REQUIRED", msg.slice(0, 200), "warn");
          }
          this.recordStep(iteration, decision, false, false, beforeModel.url, beforeModel.url, actUpper === "WAIT_FOR_USER" ? "Waiting for user takeover" : "Waiting for user information");
          this.pushPlanStep(task, decision, "completed", msg);

          if (actUpper === "WAIT_FOR_USER") {
            // Auto-detect takeover completion: poll for URL/title change.
            const resumed = await this.waitForTakeover(currentTabId, beforeModel.url, beforeModel.title);
            if (this.stopped) break;
            if (!resumed) {
              this.emit(`⏸️ Still waiting on you in the browser — press Resume once you've completed the step, or send a message with an update.`, "warn");
              task.status = "waiting_user";
              this.state = "WAITING_FOR_USER";
              this.notify();
              return task; // stays WAITING_FOR_USER; user resumes via button/message
            }
            this.emit(`Detected the page changed — resuming task automatically…`, "info");
            continue;
          }
          // ASK_USER ends the live loop; next user chat message continues it.
          task.status = "waiting_user";
          this.state = "WAITING_FOR_USER";
          this.notify();
          return task;
        }

        // ---------- 4. POLICY / APPROVAL GATE (REVIEW != COMMIT) ----------
        if (decision.requires_approval && this.approvalBridge) {
          this.state = "WAITING_FOR_APPROVAL";
          task.status = "waiting_review";
          this.notify();
          this.emit(`🔒 **Review required:** ${decision.reason} (${actUpper}${decision.target ? ` on ${decision.target}` : ""})`, "warn");
          agentEventBus.publish(task.taskId, "READY_FOR_REVIEW",
            `${actUpper}${decision.target ? ` on ${decision.target}` : ""} prepared — awaiting your confirmation`,
            "warn", decision.value ? `value: ${decision.value.slice(0, 120)}` : undefined);
          metricsLedger.recordIntervention("approval_prompt");
          const approved = await this.approvalBridge({
            action: actUpper,
            target: decision.target,
            value: decision.value,
            description: decision.reason || `${actUpper} ${decision.target || ""}`,
          });
          if (this.stopped) break;
          task.status = "running";
          if (!approved) {
            this.emit(`Denied — asking the agent to find another way…`, "warn");
            const denyFailure = this.classifyFailure({
              decision, resolutionFailed: false, observationEmpty: false,
              effectDetail: "action denied by user (PERMISSION_REQUIRED)", url: beforeModel.url,
              pageTitle: beforeModel.title, attempt: 1,
            });
            denyFailure.category = "PERMISSION_REQUIRED";
            this.recordStep(iteration, decision, false, false, beforeModel.url, beforeModel.url, "User denied approval", currentTabId, denyFailure);
            metricsLedger.recordStep({ iteration: iteration + 1, url: beforeModel.url, world_version: -1, action: actUpper, target: decision.target ?? null, strategy: this.metricStrategy(beforeModel.url), result: "not_dispatched", verified: false, failure_class: "PERMISSION_REQUIRED", recovery: this.recoveryPending });
            this.pushPlanStep(task, decision, "failed", "Denied by user");
            agentEventBus.publish(task.taskId, "ACTION_FAILED", `${actUpper} denied by user — finding an alternative`, "warn");
            consecutiveFailures = this.trackFailure(decision, consecutiveFailures);
            if (consecutiveFailures >= 3) break;
            continue;
          }
        }

        // ---------- 5. RESOLVE TARGET ----------
        let resolved: ResolvedElement | null = null;
        if (["CLICK", "TYPE", "SELECT", "CHECK", "UNCHECK"].includes(actUpper)) {
          this.state = "RESOLVING";
          resolved = this.resolveTarget(decision.target!, beforeModel);
          const validation = resolved ? this.validateAction(actUpper, resolved, beforeModel) : { valid: false, reason: `Target ${decision.target} not found in fresh observation` };
          if (!resolved || !validation.valid) {
            // STEP 2 RECOVERY: STALE_ELEMENT / ELEMENT_NOT_FOUND recovery
            // Re-observe fresh page state and attempt deterministic re-resolution
            this.logTrace("RECOVERY_ATTEMPT", { action: actUpper, target: decision.target, reason: "Target stale/not found — re-observing tab" });
            const freshModel = await this.observePage(currentTabId);
            resolved = this.resolveTarget(decision.target!, freshModel);
            const freshValidation = resolved ? this.validateAction(actUpper, resolved, freshModel) : { valid: false, reason: "Target still unresolvable after re-observation" };

            if (resolved && freshValidation.valid) {
              this.logTrace("RECOVERY_SUCCESS", { action: actUpper, target: decision.target, resolvedId: resolved.element.id, strategy: resolved.strategy });
              beforeModel = freshModel; // update beforeModel to fresh observation
            } else {
              const why = freshValidation.reason || validation.reason || "unresolvable target";
              this.logTrace("RESOLUTION_FAILED", { target: decision.target, why });
              const failure = this.classifyFailure({
                decision, resolutionFailed: true, observationEmpty: isObservationEmpty(freshModel),
                effectDetail: why, url: freshModel.url, pageTitle: freshModel.title,
                attempt: this.bumpAttempt(actUpper, decision.target),
              });
              failure.category = "STALE_ELEMENT";
              this.registerRecovery(failure);
              agentEventBus.publish(task.taskId, "ACTION_FAILED", `${actUpper} ${decision.target}: STALE_ELEMENT`, "error", failure.evidence);
              this.recordStep(iteration, decision, false, false, freshModel.url, freshModel.url, why, currentTabId, failure);
              metricsLedger.recordStep({ iteration: iteration + 1, url: freshModel.url, world_version: this.tabStates.get(currentTabId)?.version ?? -1, action: actUpper, target: decision.target ?? null, strategy: this.metricStrategy(freshModel.url), result: "not_dispatched", verified: false, failure_class: failure.category, recovery: true });
              this.pushPlanStep(task, decision, "failed", why);
              consecutiveFailures = this.trackFailure(decision, consecutiveFailures);
              if (consecutiveFailures >= 3) break;
              continue; // reasoner sees structured failure + failed strategies and replans
            }
          }
        }

        // ---------- 6. EXECUTE (native verified executor) ----------
        this.state = "EXECUTING";
        agentEventBus.publish(task.taskId, "ACTION_EXECUTING", `${actUpper}${decision.target ? ` ${decision.target}` : ""}`, "info");

        // ---------- 6.5 ZERO-TRUST SECURITY KERNEL V2 GATE ----------
        const secCheck = securityKernel.validateProposedAction(decision, resolved?.element, beforeModel.url);
        if (!secCheck.allowed) {
          agentEventBus.publish(task.taskId, "SECURITY_POLICY_BLOCKED", secCheck.reason, "error");
          const failure = this.classifyFailure({
            decision,
            execError: secCheck.reason,
            resolutionFailed: false,
            observationEmpty: false,
            effectDetail: secCheck.reason,
            url: beforeModel.url,
            pageTitle: beforeModel.title,
            attempt: this.bumpAttempt(actUpper, decision.target),
          });
          this.registerRecovery(failure);
          this.recordStep(iteration, decision, false, false, beforeModel.url, beforeModel.url, secCheck.reason, currentTabId, failure);
          continue;
        }

        if (secCheck.requiresApproval && !decision.requires_approval) {
          decision.requires_approval = true;
          // Re-run policy gate check if we need approval now
          this.state = "WAITING_FOR_APPROVAL";
          task.status = "waiting_review";
          this.notify();
          this.emit(`🔒 **Security Review required:** ${decision.reason}`, "warn");
          const approved = await this.approvalBridge!({
            action: actUpper,
            target: decision.target,
            value: decision.value,
            description: `Security Policy: ${secCheck.reason}`,
          });
          if (this.stopped) break;
          task.status = "running";
          if (!approved) {
             const denyFailure = this.classifyFailure({
              decision, resolutionFailed: false, observationEmpty: false,
              effectDetail: "action denied by user (PERMISSION_REQUIRED)", url: beforeModel.url,
              pageTitle: beforeModel.title, attempt: 1,
            });
            denyFailure.category = "PERMISSION_REQUIRED";
            this.recordStep(iteration, decision, false, false, beforeModel.url, beforeModel.url, "User denied security approval", currentTabId, denyFailure);
            continue;
          }
        }

        agentEventBus.publish(task.taskId, "SECURITY_KERNEL_VERIFIED", `Passed Risk [${secCheck.riskLevel}]`, "info");

        // ---------- 7. EXECUTE & VERIFY ----------
        const execT0 = performance.now();
        const execRes = await this.executeDecision(decision, currentTabId, resolved);
        const execMs = performance.now() - execT0;

        // Rust-side hard gate can still demand approval (defense in depth)
        if (!execRes.dispatched && execRes.needsApproval && this.approvalBridge) {
          this.state = "WAITING_FOR_APPROVAL";
          this.notify();
          const approved = await this.approvalBridge({ action: actUpper, target: decision.target, value: decision.value, description: decision.reason || `${actUpper} requires approval` });
          if (approved) {
            Object.assign(execRes, await this.executeDecision(decision, currentTabId, resolved, true));
          }
        }

        if (!execRes.dispatched) {
          // STEP 2 RECOVERY: NAVIGATION_TIMEOUT recovery
          // Re-observe tab to see if navigation or load actually succeeded despite error/timeout
          const freshModel = await this.observePage(currentTabId);
          const targetUrl = (decision.value || decision.target || "").toLowerCase();
          const loadedUrl = freshModel.url.toLowerCase();

          if (actUpper === "NAVIGATE" && targetUrl && loadedUrl.includes(targetUrl.replace(/^https?:\/\//, ""))) {
            this.logTrace("RECOVERY_SUCCESS", { action: "NAVIGATE", target: decision.target, loadedUrl: freshModel.url, reason: "Navigation succeeded despite timeout/dispatch warning" });
            execRes.dispatched = true;
            execRes.rustVerified = true;
          } else {
            const failure = this.classifyFailure({
              decision, execError: execRes.error, resolutionFailed: false,
              observationEmpty: isObservationEmpty(freshModel), effectDetail: undefined,
              url: freshModel.url, pageTitle: freshModel.title,
              attempt: this.bumpAttempt(actUpper, decision.target),
            });
            this.registerRecovery(failure);
            agentEventBus.publish(task.taskId, "ACTION_FAILED", `${actUpper}: ${failure.category}`, "error", failure.evidence);
            this.recordStep(iteration, decision, false, false, freshModel.url, freshModel.url, execRes.error || "dispatch failed", currentTabId, failure);
            metricsLedger.recordStep({ iteration: iteration + 1, url: freshModel.url, world_version: this.tabStates.get(currentTabId)?.version ?? -1, action: actUpper, target: decision.target ?? null, strategy: this.metricStrategy(freshModel.url), result: "not_dispatched", verified: false, failure_class: failure.category, recovery: true });
            this.pushPlanStep(task, decision, "failed", execRes.error || "dispatch failed");
            consecutiveFailures = this.trackFailure(decision, consecutiveFailures);
            if (consecutiveFailures >= 3) break;
            continue;
          }
        }

        // Tab-flow actions change which tab we observe next
        if (execRes.newTabId) currentTabId = execRes.newTabId;

        // ---------- 7. WAIT + VERIFY ----------
        await this.waitForPageStability(currentTabId, actUpper === "NAVIGATE" || actUpper === "CLICK" ? 900 : 500);
        this.state = "VERIFYING";
        const afterModel = await this.observePage(currentTabId);

        const transition = ActionVerifier.verifyTransition(
          actUpper === "SUBMIT" || actUpper === "PRESS_KEY" ? "CLICK" : actUpper,
          decision.target || undefined,
          {
            url: beforeModel.url, title: beforeModel.title, headings: beforeModel.sections,
            text_blocks: [], interactive_elements: beforeModel.links,
            forms_count: beforeModel.formsCount, tables_count: beforeModel.tablesCount,
            links_count: beforeModel.links.length, timestamp: beforeModel.timestamp,
          } as any,
          {
            url: afterModel.url, title: afterModel.title, headings: afterModel.sections,
            text_blocks: [], interactive_elements: afterModel.links,
            forms_count: afterModel.formsCount, tables_count: afterModel.tablesCount,
            links_count: afterModel.links.length, timestamp: afterModel.timestamp,
          } as any
        );
        const effectVerified = this.verifyExpectedEffect(decision.expected_effect, beforeModel, afterModel, execRes);
        const rustVerified = execRes.rustVerified;
        const verified = rustVerified !== false && (decision.expected_effect.type === "none" ? transition.success : (effectVerified.ok || transition.success));

        this.logTrace("VERIFICATION", {
          action: actUpper,
          dispatchVerified: rustVerified,
          expectedEffect: decision.expected_effect.type,
          effectVerified: effectVerified.ok,
          effectDetail: effectVerified.detail,
          beforeUrl: beforeModel.url,
          afterUrl: afterModel.url,
        });

        // Collect facts on EXTRACT steps
        if (actUpper === "EXTRACT") {
          afterModel.searchResults.slice(0, 6).forEach((r) => {
            task.sources.push({ title: r.title, url: r.href || "", snippet: r.visibleText });
            task.extractedFacts.push(`${r.title}: ${r.visibleText || r.href}`);
          });
          if (afterModel.searchResults.length === 0 && (afterModel.textBlocks || []).length > 0) {
            afterModel.textBlocks!.slice(0, 5).forEach((t) => task.extractedFacts.push(t));
            const extractItems: EvidenceItem[] = (afterModel.textBlocks || []).slice(0, 3).map((t, idx) => ({
              id: `ev_ext_${Date.now()}_${idx}`,
              label: `summary_content_${idx + 1}`,
              value: t,
              source: afterModel.url || afterModel.title,
              confidence: 0.95,
              evidence_type: "OBSERVED",
              validity: "CURRENT",
            }));
            this.mergeEvidence(task, extractItems, currentTabId);
          } else if (afterModel.searchResults.length === 0) {
            afterModel.sections.slice(0, 5).forEach((s) => task.extractedFacts.push(s));
            const extractItems: EvidenceItem[] = afterModel.sections.slice(0, 3).map((s, idx) => ({
              id: `ev_sec_${Date.now()}_${idx}`,
              label: `section_heading_${idx + 1}`,
              value: s,
              source: afterModel.url || afterModel.title,
              confidence: 0.95,
              evidence_type: "OBSERVED",
              validity: "CURRENT",
            }));
            this.mergeEvidence(task, extractItems, currentTabId);
          }
        }
        // Model-declared evidence merges into the task's goal-predicate store
        this.mergeEvidence(task, decision.evidence);
        if (afterModel.url && !task.visitedUrls.includes(afterModel.url)) task.visitedUrls.push(afterModel.url);

        // ---------- 8. RECORD (with structured failure diagnosis) ----------
        let failure: ActionFailure | null = null;
        if (!verified) {
          failure = this.classifyFailure({
            decision,
            execError: undefined,
            resolutionFailed: false,
            observationEmpty: isObservationEmpty(afterModel),
            effectDetail: effectVerified.detail || transition.message,
            url: afterModel.url,
            pageTitle: afterModel.title,
            attempt: this.bumpAttempt(actUpper, decision.target),
          });
          this.registerRecovery(failure);
          agentEventBus.publish(task.taskId, "ACTION_FAILED", `${actUpper}${decision.target ? ` ${decision.target}` : ""}: dispatched but ${failure.category}`, "error", failure.evidence);
        } else {
          agentEventBus.publish(task.taskId, "ACTION_VERIFIED", `${actUpper}${decision.target ? ` ${decision.target}` : ""} — ${effectVerified.detail}`.slice(0, 200), "success");
        }

        this.recordStep(iteration, decision, true, verified, beforeModel.url, afterModel.url,
          verified ? effectVerified.detail : `NOT VERIFIED: ${effectVerified.detail || transition.message}`,
          currentTabId, failure);
        // PHASE 0 measurement — one ledger row per dispatched action
        metricsLedger.recordStep({
          iteration: iteration + 1,
          url: afterModel.url,
          world_version: this.tabStates.get(currentTabId)?.version ?? -1,
          action: actUpper,
          target: decision.target ?? null,
          strategy: this.metricStrategy(afterModel.url),
          result: "dispatched",
          verified,
          failure_class: failure?.category ?? null,
          recovery: this.recoveryPending,
          latency_ms: Math.round(execMs),
          rust: !["WAIT", "OBSERVE", "EXTRACT"].includes(actUpper),
          tab_event: execRes.newTabId
            ? {
                kind: actUpper === "OPEN_TAB" ? "opened" : "switched",
                raw_target: decision.target ?? undefined,
                normalized_target: String(execRes.newTabId),
                resolved_tab_id: String(execRes.newTabId),
                resolved_url: actUpper === "OPEN_TAB" ? (decision.value || decision.target || "") : afterModel.url,
              }
            : undefined,
        });
        if (verified) this.recoveryPending = false;
        this.pushPlanStep(task, decision, verified ? "completed" : "failed", verified ? effectVerified.detail : transition.message);

        if (!verified) {
          consecutiveFailures = this.trackFailure(decision, consecutiveFailures);
          if (consecutiveFailures >= 3) {
            this.finishRun("failed", `Three consecutive unverified actions (last: ${actUpper} ${decision.target || ""}). Stopping honestly instead of pretending.`);
            return task;
          }
        } else {
          consecutiveFailures = 0;
        }
      }

      if (this.stopped) {
        this.finishRun("cancelled", "Task cancelled by user.");
      } else if (!["completed", "failed", "cancelled", "waiting_user"].includes(task.status as string)) {
        this.finishRun("failed", `Reached the ${MAX_ITERATIONS}-iteration safety bound without completing the goal.`);
      }
      return task;
    } finally {
      // Keep goal-mode alive while the run is paused or waiting on the user —
      // resume()/provideUserResponse() re-enter the SAME loop (no new stack).
      this.goalMode = !!this.activeTask && ["waiting_user", "paused"].includes(this.activeTask.status as string);
      this.notify();
    }
  }

  /** Wait for human takeover: poll until URL/title changed, resume requested, or timeout. */
  private async waitForTakeover(tabId: string, waitUrl: string, waitTitle: string): Promise<boolean> {
    const POLL_MS = 2000;
    const TIMEOUT_MS = 180_000;
    const deadline = Date.now() + TIMEOUT_MS;
    metricsLedger.recordIntervention("takeover_wait");
    void metricsLedger.flush(false); // partial artifact safety while paused on the user
    while (Date.now() < deadline && !this.stopped) {
      if (this.resumeRequested) {
        this.resumeRequested = false;
        return true;
      }
      if (this.paused) {
        await new Promise((r) => setTimeout(r, 300));
        continue;
      }
      try {
        const sem = await nativeBrowserService.inspectPage(tabId);
        const urlChanged = (sem.url || "") !== waitUrl;
        const titleChanged = (sem.title || "") !== waitTitle;
        if (urlChanged || titleChanged) return true;
      } catch {}
      await new Promise((r) => setTimeout(r, POLL_MS));
    }
    return !this.stopped;
  }

  /** Dispatch one decision through the native verified executor / tab bridges. */
  private async executeDecision(
    decision: AgentDecision,
    tabId: string,
    resolved: ResolvedElement | null,
    preApproved: boolean = false
  ): Promise<{ dispatched: boolean; error?: string; rustVerified?: boolean; newTabId?: string; needsApproval?: boolean }> {
    const act = decision.action.toUpperCase();
    const effectiveTarget = decision.target || resolved?.element.id || undefined;

    try {
      switch (act) {
        case "OPEN_TAB": {
          if (!this.createTabBridge) return { dispatched: false, error: "No tab-creation bridge registered" };
          const newId = await this.createTabBridge(decision.value || decision.target || "");
          this.logTrace("EXECUTION", { action: "OPEN_TAB", newTabId: newId, url: decision.value });
          return { dispatched: !!newId, rustVerified: true, newTabId: newId };
        }
        case "SWITCH_TAB": {
          // Defense-in-depth: strip a "tab <uuid>" echo if the backend missed it
          const tabTarget = String(effectiveTarget).replace(/^tab\s+/i, "");
          await nativeBrowserService.activateTab(tabTarget);
          this.logTrace("EXECUTION", { action: "SWITCH_TAB", tabId: tabTarget });
          return { dispatched: true, rustVerified: true, newTabId: tabTarget };
        }
        case "CLOSE_TAB": {
          await nativeBrowserService.closeTab(String(effectiveTarget));
          return { dispatched: true, rustVerified: true };
        }
        case "WAIT":
        case "OBSERVE":
        case "EXTRACT":
          // Read-only / dispatch-only steps: extraction happens from the fresh
          // observation inside the loop — no executor round-trip needed.
          return { dispatched: true, rustVerified: true };
        default: {
          // Map agent vocabulary onto the Rust executor's action set.
          const rustAction =
            act === "GO_BACK" ? "BACK"
            : act === "GO_FORWARD" ? "FORWARD"
            : act === "SUBMIT" ? "SUBMIT_FORM"
            : act === "CHECK" || act === "UNCHECK" ? "CLICK" // toggling a checkbox/radio
            : act;
          const res = await nativeBrowserService.executeAIAction(
            tabId,
            rustAction,
            effectiveTarget,
            decision.value || undefined,
            true
          );
          if (res.approval_required && !preApproved) {
            return { dispatched: false, needsApproval: true, error: res.message };
          }
          const data = (res.data || {}) as any;
          const jsOk = data.ok === true || data.verified === true || data.verified === undefined && res.success;
          this.logTrace("EXECUTION", {
            action: act,
            elementId: effectiveTarget,
            value: decision.value ? "[PROVIDED]" : undefined,
            success: res.success,
            message: res.message,
            rustData: data,
          });
          return { dispatched: res.success, error: res.success ? undefined : res.message, rustVerified: jsOk !== false };
        }
      }
    } catch (err: any) {
      return { dispatched: false, error: err?.message || String(err) };
    }
  }

  /** Check the model's declared postcondition against the re-observed page. */
  private verifyExpectedEffect(
    effect: ExpectedEffect,
    before: PageModel,
    after: PageModel,
    execRes: { newTabId?: string }
  ): { ok: boolean; detail: string } {
    const allAfter = after.links.concat(after.buttons).concat(after.inputs).concat(after.selects);
    switch (effect.type) {
      case "none":
        return { ok: true, detail: "no postcondition declared" };
      case "url_changed":
        return { ok: before.url !== after.url, detail: `url ${before.url} → ${after.url}` };
      case "url_contains": {
        const rawNeedle = (effect.value || effect.target || "").toLowerCase().replace(/^\s*https?:\/\//, "");
        const needle = rawNeedle.includes("q=") ? rawNeedle.split("q=")[1].split("&")[0] : rawNeedle;
        const normNeedle = decodeURIComponent(needle.replace(/\+/g, " "));
        const normHay = decodeURIComponent(after.url.toLowerCase().replace(/\+/g, " "));
        const ok = (!!normNeedle && normHay.includes(normNeedle)) || (before.url !== after.url && after.url.length > 0 && !after.url.startsWith("about:blank"));
        return { ok, detail: `expected url to contain "${needle}", got "${after.url}"` };
      }
      case "value_changed": {
        const elId = effect.target || "";
        const expected = (effect.value || "").trim().toLowerCase();
        const el = allAfter.find((e) => e.id === elId) as any;
        const actual = String(el?.value ?? "").trim().toLowerCase();
        // If native typing caused navigation/submit or populated input text, count as verified
        const ok = (!!expected && actual.includes(expected)) || (actual.length > 0) || (before.url !== after.url);
        return { ok, detail: `input ${elId} value="${actual ? actual.slice(0, 40) : "(empty)"}"` };
      }
      case "text_present": {
        const needle = (effect.value || effect.target || "").toLowerCase();
        const hay = (after.sections.join(" ") + " " + after.links.map((l) => l.text || l.name || "").join(" ")).toLowerCase();
        return { ok: !!needle && hay.includes(needle), detail: `expected visible text "${needle.slice(0, 60)}"` };
      }
      case "element_appeared": {
        const needle = (effect.value || effect.target || "").toLowerCase();
        const ok = allAfter.some((e) => `${(e as any).name || ""} ${(e as any).text || ""}`.toLowerCase().includes(needle));
        return { ok, detail: `expected element matching "${needle}"` };
      }
      case "dom_mutated": {
        const changed =
          before.url !== after.url ||
          before.title !== after.title ||
          JSON.stringify(before.sections) !== JSON.stringify(after.sections) ||
          before.links.length !== after.links.length ||
          before.inputs.some((i, idx) => String((i as any).value ?? "") !== String(((after.inputs[idx] as any)?.value) ?? ""));
        return { ok: changed, detail: changed ? "DOM/page state changed" : "no observable DOM change" };
      }
      case "tab_opened":
        return { ok: !!execRes.newTabId, detail: execRes.newTabId ? `new tab ${execRes.newTabId}` : "no new tab observed" };
      default:
        return { ok: true, detail: `unknown effect type ${effect.type} treated as pass` };
    }
  }

  /** Retry bookkeeping: attempts per action+target (policy cap = 2). */
  private bumpAttempt(action: string, target: string | null | undefined): number {
    const key = `${action}:${target || ""}`;
    const n = (this.actionAttempts.get(key) || 0) + 1;
    this.actionAttempts.set(key, n);
    return n;
  }

  /** Record an exhausted strategy so future reasoning cycles see it. */
  private registerRecovery(failure: ActionFailure) {
    this.recoveryPending = true;
    const count = this.bumpStrategyFailure(failure, this.currentLevel);
    if (count === 2 && this.activeTask) {
      agentEventBus.publish(
        this.activeTask.taskId,
        "STRATEGY_CHANGED",
        `${failure.category} failed ${count}× at level '${this.currentLevel}' — strategy marked exhausted; switching approach`,
        "warn",
        failure.evidence
      );
      this.emit(`↻ ${failure.category} keeps failing (${count}×) — switching strategy.`, "warn");
    }
    if (this.activeTask) {
      this.activeTask.failedStrategies = [...this.exhaustedStrategies];
    }
  }



  private recordStep(
    iteration: number,
    d: AgentDecision,
    dispatched: boolean,
    verified: boolean,
    urlBefore: string,
    urlAfter: string,
    note: string,
    tabId?: string,
    failure?: ActionFailure | null
  ) {
    this.history.push({
      iteration: iteration + 1,
      action: d.action,
      target: d.target,
      value: d.value ? d.value.slice(0, 120) : undefined,
      dispatched,
      verified,
      url_before: urlBefore,
      url_after: urlAfter,
      note: note.slice(0, 240),
      tab_id: tabId ?? null,
      strategy: `${this.currentLevel}@${(() => { try { return new URL(urlAfter || urlBefore).hostname.replace(/^www\./, ""); } catch { return "unknown"; } })()}`,
      failure: failure ?? null,
    });
  }

  /** PHASE 0: canonical strategy signature for the metrics ledger. */
  private metricStrategy(url: string): string {
    return `${this.currentLevel}@${(() => {
      try {
        return new URL(url).hostname.replace(/^www\./, "");
      } catch {
        return "unknown";
      }
    })()}`;
  }

  private pushPlanStep(task: AgentTask, d: AgentDecision, status: PlanStep["status"], message: string) {    task.steps.push({
      id: `it_${task.steps.length + 1}`,
      goal: d.reason || d.action,
      tool: d.action.toLowerCase(),
      target: d.target || undefined,
      value: d.value ? d.value.slice(0, 80) : undefined,
      riskLevel: d.requires_approval ? "High" : "Low",
      status,
      resultMessage: message,
    });
  }

  /** Stuck detection: identical action+target failing twice in a row escalates. */
  private trackFailure(d: AgentDecision, current: number): number {
    const sig = `${d.action}:${d.target || ""}`;
    const last = this.history[this.history.length - 1];
    const prevSameSig = this.history.filter((h) => `${h.action}:${h.target || ""}` === sig && !h.verified);
    if (prevSameSig.length >= 2) {
      last.note = `${last.note} [REPEATED FAILURE]`;
      this.emit(`⚠️ Same step keeps failing (${sig}) — the agent will be asked to change strategy.`, "warn");
    }
    return current + 1;
  }

  /** Normalize monetary/numeric values without destroying original string. */
  private normalizeValue(raw: string): string {
    if (!raw) return "";
    const clean = raw.trim();
    // Currency matching (e.g. "$1,299.00" -> "1299.00 USD", "₹15,999" -> "15999 INR")
    const currMatch = clean.match(/^([$₹€£]|rs\.?\s?)?([\d,]+(?:\.\d+)?)\s*(usd|inr|eur|gbp)?$/i);
    if (currMatch) {
      const symbol = (currMatch[1] || "").trim();
      const num = currMatch[2].replace(/,/g, "");
      let code = (currMatch[3] || "").toUpperCase();
      if (!code) {
        if (symbol === "$") code = "USD";
        else if (symbol === "₹" || /^rs/i.test(symbol)) code = "INR";
        else if (symbol === "€") code = "EUR";
        else if (symbol === "£") code = "GBP";
      }
      return code ? `${num} ${code}` : num;
    }
    return clean.toLowerCase();
  }

  private mergeEvidence(task: AgentTask, items?: EvidenceItem[] | null, tabId?: string) {
    if (!items || items.length === 0) return;
    if (!task.evidence) task.evidence = [];
    const nowIso = new Date().toISOString();
    for (const item of items) {
      const normVal = this.normalizeValue(item.value);
      const enrichedItem: EvidenceItem = {
        ...item,
        id: item.id || `ev_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        normalized_value: item.normalized_value || normVal,
        tab_id: item.tab_id || tabId || undefined,
        timestamp: item.timestamp || nowIso,
        confidence: item.confidence ?? 0.9,
        evidence_type: item.evidence_type || "OBSERVED",
        validity: item.validity || "CURRENT",
      };

      const normLabel = item.label.toLowerCase().trim();
      const normSource = (item.source || "").toLowerCase().trim();

      // Check for exact same source + label -> deduplicate/update
      const sameSourceIdx = task.evidence.findIndex(
        (e) => e.label.toLowerCase().trim() === normLabel && e.source.toLowerCase().trim() === normSource
      );

      if (sameSourceIdx >= 0) {
        task.evidence[sameSourceIdx] = enrichedItem;
      } else {
        // Check for cross-source contradiction (same label, different source, different normalized value)
        const conflictIdx = task.evidence.findIndex(
          (e) => e.label.toLowerCase().trim() === normLabel && e.source.toLowerCase().trim() !== normSource
        );

        if (conflictIdx >= 0) {
          const existing = task.evidence[conflictIdx];
          if ((existing.normalized_value || existing.value) !== (enrichedItem.normalized_value || enrichedItem.value)) {
            existing.validity = "CONTRADICTED";
            enrichedItem.validity = "CONTRADICTED";
            this.emit(`⚠️ Contradiction detected for '${item.label}': ${existing.source} (${existing.value}) vs ${enrichedItem.source} (${enrichedItem.value})`, "warn");
          }
        }
        task.evidence.push(enrichedItem);
      }

      // Index evidence in TabWorldState
      if (enrichedItem.tab_id) {
        const ws = this.tabStates.get(enrichedItem.tab_id);
        if (ws) {
          if (!ws.extracted_facts) ws.extracted_facts = [];
          const tabFactIdx = ws.extracted_facts.findIndex((f) => f.label.toLowerCase().trim() === normLabel);
          if (tabFactIdx >= 0) {
            ws.extracted_facts[tabFactIdx] = enrichedItem;
          } else {
            ws.extracted_facts.push(enrichedItem);
          }
        }
      }
    }
    // Hard cap evidence array at 15 items to bound context size
    if (task.evidence.length > 15) {
      task.evidence = task.evidence.slice(task.evidence.length - 15);
    }
  }

  private finishRun(status: "completed" | "failed" | "cancelled", summary: string) {
    const task = this.activeTask;
    if (!task) return;
    task.status = status;
    this.state = status === "completed" ? "COMPLETED" : status === "failed" ? "FAILED" : "STOPPED";
    if (status === "failed") this.emit(`❌ ${summary}`, "error");
    else if (status === "cancelled") this.emit(`⏹️ ${summary}`, "warn");
    agentEventBus.publish(
      task.taskId,
      status === "completed" ? "TASK_COMPLETED" : status === "failed" ? "TASK_FAILED" : "TASK_CANCELLED",
      summary.slice(0, 220),
      status === "completed" ? "success" : status === "failed" ? "error" : "warn",
      status !== "completed"
        ? undefined
        : task.evidence?.length
          ? task.evidence.map((e) => `${e.label}: ${e.value}`).join(" | ").slice(0, 400)
          : undefined
    );
    this.logTrace("GOAL_END", { status, summary, iterations: this.history.length, evidenceItems: task.evidence?.length ?? 0 });
    metricsLedger.setFinal(status, summary);
    void metricsLedger.flush(true); // Persist durable run JSON artifact to benchmarks/runs/
    if (status !== "cancelled") this.goalMode = false;
    this.notify();
  }

  private activeCheckpoint: SessionCheckpoint | null = null;

  createCheckpoint(
    tabId: string,
    url: string,
    title: string,
    reason: string,
    kind: "captcha" | "login" | "consent" | "ambiguous" | "user_request" | "unknown" = "unknown"
  ): SessionCheckpoint | null {
    if (!this.activeTask) return null;
    const actionAttemptsObj: Record<string, number> = {};
    this.actionAttempts.forEach((v, k) => { actionAttemptsObj[k] = v; });
    const strategyFailuresObj: Record<string, number> = {};
    this.strategyFailures.forEach((v, k) => { strategyFailuresObj[k] = v; });

    // Redact any sensitive passwords or secrets from action history values
    const safeHistory = this.history.map((h) => ({
      ...h,
      value: h.action.toUpperCase() === "TYPE" && (h as any).sensitive ? "[REDACTED]" : h.value,
    }));

    const checkpoint: SessionCheckpoint = {
      checkpointId: `chk_${Date.now()}`,
      taskId: this.activeTask.taskId,
      userGoal: this.activeTask.userGoal,
      tabId,
      url,
      title,
      subgoal: this.activeSubgoal,
      takeoverReason: reason,
      takeoverKind: kind,
      createdAt: new Date().toISOString(),
      actionHistory: safeHistory,
      evidence: [...(this.activeTask.evidence || [])],
      failedStrategies: [...this.exhaustedStrategies],
      actionAttempts: actionAttemptsObj,
      strategyFailures: strategyFailuresObj,
      stepIndex: this.activeTask.currentStepIndex || 0,
      version: 1,
    };

    this.activeCheckpoint = checkpoint;
    agentEventBus.publish(
      this.activeTask.taskId,
      "SESSION_CHECKPOINT_CREATED",
      `Checkpoint ${checkpoint.checkpointId} created for ${reason}`,
      "info",
      url
    );
    return checkpoint;
  }

  getActiveCheckpoint(): SessionCheckpoint | null {
    return this.activeCheckpoint;
  }

  async validateAndResumeFromCheckpoint(_tabId: string, freshModel: PageModel): Promise<boolean> {
    if (!this.activeCheckpoint || !this.activeTask) {
      agentEventBus.publish(
        this.activeTask?.taskId || "unknown",
        "SESSION_CHECKPOINT_REJECTED",
        "No active checkpoint found",
        "error"
      );
      return false;
    }

    const chk = this.activeCheckpoint;

    // Checkpoint validation gates
    if (chk.taskId !== this.activeTask.taskId) {
      agentEventBus.publish(this.activeTask.taskId, "SESSION_CHECKPOINT_REJECTED", "Checkpoint task ID mismatch", "error");
      return false;
    }

    if (!freshModel.url || freshModel.url === "about:blank") {
      agentEventBus.publish(this.activeTask.taskId, "SESSION_CHECKPOINT_REJECTED", "Fresh perception returned empty tab state", "error");
      return false;
    }

    agentEventBus.publish(
      this.activeTask.taskId,
      "SESSION_CHECKPOINT_VALIDATED",
      `Checkpoint ${chk.checkpointId} validated successfully against fresh perception (${freshModel.url})`,
      "success",
      freshModel.url
    );

    agentEventBus.publish(this.activeTask.taskId, "HUMAN_TAKEOVER_RESUMED", "Autonomous execution resumed from checkpoint", "success");

    this.resumeRequested = true;
    this.paused = false;
    this.activeTask.status = "running";
    this.state = "OBSERVING";
    return true;
  }

  pause() {
    this.paused = true;
    metricsLedger.recordIntervention("pause");
    this.state = "PAUSED";
    if (this.activeTask) {
      this.createCheckpoint(
        "unknown",
        this.activeTask.visitedUrls[this.activeTask.visitedUrls.length - 1] || "",
        "User Paused",
        "User manual pause",
        "user_request"
      );
      agentEventBus.publish(this.activeTask.taskId, "HUMAN_TAKEOVER_PAUSED", "Autonomous execution paused by user", "warn");
    }
    this.logTrace("PAUSE", { taskId: this.activeTask?.taskId });
    this.notify();
  }

  resume(_tabId: string) {
    if (this.goalMode) {
      // Wake a paused loop or re-enter after user takeover / ASK_USER.
      this.resumeRequested = true;
      this.paused = false;
      if (this.activeTask && ["paused", "waiting_user"].includes(this.activeTask.status as string)) {
        this.activeTask.status = "running";
      }
      if (this.state === "WAITING_FOR_USER") {
        // The live loop has returned; re-enter the SAME goal loop.
        this.state = "OBSERVING";
        this.emit(`Resume requested — re-observing the browser…`, "info");
        void this.continueGoalLoop(_tabId, (this.activeTask?.currentStepIndex ?? 0) + 1);
      }
      this.logTrace("RESUME", { taskId: this.activeTask?.taskId, mode: "goal" });
      this.notify();
      return;
    }
    this.paused = false;
    this.notify();
  }

  stop() {
    this.stopped = true;
    this.resumeRequested = false;
    this.paused = false;
    this.state = "STOPPED";
    metricsLedger.recordIntervention("stop");
    if (this.activeTask) {
      this.activeTask.status = "cancelled";
    }
    this.logTrace("STOP", { taskId: this.activeTask?.taskId });
    this.notify();
  }
}
