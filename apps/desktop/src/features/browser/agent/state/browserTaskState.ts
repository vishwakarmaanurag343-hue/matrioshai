import { AgentTask } from "../types";
import { BrowserAgentHarness } from "../agentHarness";

export type AgentListener = (task: AgentTask | null, activeActionDesc?: string) => void;

export class BrowserTaskManager {
  private static instance: BrowserTaskManager;
  private currentTask: AgentTask | null = null;
  private isRunning: boolean = false;
  private listeners: Set<AgentListener> = new Set();
  private activeActionDesc: string = "";

  static getInstance(): BrowserTaskManager {
    if (!this.instance) {
      this.instance = new BrowserTaskManager();
    }
    return this.instance;
  }

  subscribe(listener: AgentListener): () => void {
    this.listeners.add(listener);
    listener(this.currentTask, this.activeActionDesc);
    return () => this.listeners.delete(listener);
  }

  private notify() {
    for (const l of this.listeners) {
      l(this.currentTask ? { ...this.currentTask } : null, this.activeActionDesc);
    }
  }

  getCurrentTask(): AgentTask | null {
    return this.currentTask;
  }

  /**
   * Emergency immediate stop button handler.
   */
  stopAgent(): void {
    this.isRunning = false;
    BrowserAgentHarness.getInstance().stop();
    this.activeActionDesc = "Agent stopped by user.";
    if (this.currentTask) {
      this.currentTask.status = "cancelled";
    }
    this.notify();
  }

  pauseAgent(): void {
    if (this.isRunning) {
      BrowserAgentHarness.getInstance().pause();
      if (this.currentTask) {
        this.currentTask.status = "paused";
      }
      this.activeActionDesc = "Agent paused.";
      this.notify();
    }
  }

  resumeAgent(tabId: string): void {
    if (this.currentTask && this.currentTask.status === "paused") {
      this.isRunning = true;
      this.currentTask.status = "running";
      this.notify();
      BrowserAgentHarness.getInstance().resume(tabId);
    }
  }

  /**
   * UNIFIED AGENT RUNTIME entry point — every user prompt goes through here.
   * Runs the canonical observe→reason→act→verify loop via the backend
   * step-reasoner; no template planner, no one-shot path.
   */
  async startGoal(userGoal: string, tabId: string, constraints: string[] = []): Promise<AgentTask | null> {
    const harness = BrowserAgentHarness.getInstance();
    this.stopAgent(); // reset previous run
    this.isRunning = true;
    this.activeActionDesc = `Starting goal: "${userGoal}"`;
    this.notify();

    const unsub = harness.subscribe((task, _state, trace) => {
      if (task) this.currentTask = task;
      if (trace) this.activeActionDesc = trace.split("\n")[0] || "";
      this.notify();
    });

    try {
      const task = await harness.executeGoal(userGoal, tabId, constraints);
      if (task && ["waiting_user", "paused"].includes(task.status as string)) {
        this.isRunning = true; // keep controls live for resume / answer
      }
      return task;
    } finally {
      unsub();
      this.isRunning = false;
      this.notify();
    }
  }

  /**
   * Continues a WAITING_FOR_USER goal with the user's chat answer (ASK_USER)
   * or after manual takeover (WAIT_FOR_USER).
   */
  provideUserAnswer(answer: string, tabId: string): void {
    BrowserAgentHarness.getInstance().provideUserResponse(answer, tabId);
  }

  isGoalWaitingForUser(): boolean {
    return this.currentTask?.status === "waiting_user";
  }
}
