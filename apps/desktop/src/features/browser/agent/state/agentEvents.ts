import { AgentEvent, AgentEventType } from "../types";

/**
 * Structured agent event stream — the single source the Agent Execution Card
 * consumes. The runtime stays UI-independent: it only publishes events.
 * No raw model chain-of-thought ever enters this stream; publishers pass
 * concise structured summaries only.
 */
export class AgentEventBus {
  private static instance: AgentEventBus;
  private listeners: ((e: AgentEvent) => void)[] = [];
  private buffers: Map<string, AgentEvent[]> = new Map();
  private seq = 0;

  static getInstance(): AgentEventBus {
    if (!AgentEventBus.instance) AgentEventBus.instance = new AgentEventBus();
    return AgentEventBus.instance;
  }

  publish(taskId: string, type: AgentEventType, summary: string, status: AgentEvent["status"] = "info", evidence?: string): AgentEvent {
    const e: AgentEvent = {
      id: `ev_${++this.seq}`,
      task_id: taskId,
      timestamp: new Date().toISOString(),
      type,
      summary,
      status,
      evidence,
    };
    const buf = this.buffers.get(taskId) || [];
    buf.push(e);
    if (buf.length > 300) buf.splice(0, buf.length - 300);
    this.buffers.set(taskId, buf);
    this.listeners.forEach((l) => l(e));
    return e;
  }

  eventsFor(taskId: string): AgentEvent[] {
    return [...(this.buffers.get(taskId) || [])];
  }

  subscribe(l: (e: AgentEvent) => void): () => void {
    this.listeners.push(l);
    return () => {
      this.listeners = this.listeners.filter((x) => x !== l);
    };
  }
}

export const agentEventBus = AgentEventBus.getInstance();
