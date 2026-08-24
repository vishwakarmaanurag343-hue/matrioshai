import { apiRequest } from "./client";

export interface SubsystemHealth {
  name: string;
  status: 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE' | 'DISABLED';
  latency_ms: number;
  details?: string;
}

export interface HealthStatus {
  overall_status: 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE' | 'DISABLED';
  app_version: string;
  uptime_seconds: number;
  subsystems: SubsystemHealth[];
}

export interface SystemMetrics {
  request_count: number;
  request_latency_ms: number;
  llm_request_count: number;
  llm_latency_ms: number;
  tool_execution_count: number;
  confirmation_count: number;
  memory_records_count: number;
  knowledge_entities_count: number;
  active_proactive_signals: number;
  circuit_breaker_open_count: number;
}

export interface StructuredEvent {
  event_id: string;
  timestamp: string;
  correlation_id: string;
  component: string;
  operation: string;
  status: string;
  details?: string;
}

export interface DatabaseBackup {
  backup_id: string;
  timestamp: string;
  filename: string;
  size_bytes: number;
  integrity_status: string;
}

export interface DiagnosticsReport {
  timestamp: string;
  overall_health: string;
  checks_passed: number;
  checks_failed: number;
  diagnostics: Array<{ name: string; status: string; details: string }>;
}

export const systemApi = {
  getHealth: (): Promise<HealthStatus> =>
    apiRequest<HealthStatus>("/system/health"),

  getMetrics: (): Promise<SystemMetrics> =>
    apiRequest<SystemMetrics>("/system/metrics"),

  getEvents: (limit: number = 50): Promise<StructuredEvent[]> =>
    apiRequest<StructuredEvent[]>(`/system/events?limit=${limit}`),

  runDiagnostics: (): Promise<DiagnosticsReport> =>
    apiRequest<DiagnosticsReport>("/system/diagnostics", { method: "POST" }),

  createBackup: (): Promise<DatabaseBackup> =>
    apiRequest<DatabaseBackup>("/system/backup", { method: "POST" }),

  listBackups: (): Promise<DatabaseBackup[]> =>
    apiRequest<DatabaseBackup[]>("/system/backups"),
};
