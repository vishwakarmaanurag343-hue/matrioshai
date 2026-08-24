# DeepSeek Harness (DSH) Integration & Agent Runtime Architecture

## Overview
DeepSeek Harness (DSH) is integrated into **MATRIOSHAI** as a pluggable **Agent Execution & Runtime Engine**, positioned under Matrioshai's authoritative **Control Plane**.

```text
                 MATRIOSHAI CONTROL PLANE
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
    IDENTITY             MEMORY               SECURITY
 (User / Session)    (Core / Recall / Graph) (Gatekeeper / Permissions)
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                       ORCHESTRATOR
                            │
                   AGENT RUNTIME API
                 (AgentRuntimeProvider)
                            │
               ┌────────────┴────────────┐
               │                         │
     NativeMatrioshaiProvider   DeepSeekHarnessProvider
                                         │
                                  ┌──────┴──────┐
                                  │             │
                               Model         Tools / Sandbox
                           (Via Gateway)   (Controlled via Matrioshai)
```

---

## 🔒 Security & Permission Invariants

1. **Control Plane Authority**:
   - Matrioshai owns Identity, Memory (Core/Recall/Graph), Privacy Gatekeepers, Context Builders, and Tool Permission policies.
   - DeepSeek Harness is an execution engine; it is never the source of truth for user memory or persistent state.
2. **Tool Permission Gateway**:
   - When DeepSeek Harness requests a tool execution (`search_code`, `read_file`, `write_file`, `apply_patch`, `mouse_click`, `send_message`), it is routed through `ToolRegistry` and `PermissionEngine`.
   - Tier 1 actions execute safely and autonomously.
   - Tier 2 actions require explicit human confirmation via `ConfirmationSystem`.
   - Tier 3 actions (destructive commands, credential exfiltration) are blocked unconditionally.
3. **Normalized Event Pipeline**:
   - Harness lifecycle updates are converted to normalized `AgentEvent` objects (`AGENT_STARTED`, `PLAN_CREATED`, `TOOL_REQUEST`, `TOOL_RESULT`, `PERMISSION_REQUESTED`, `AGENT_COMPLETED`, etc.) before being streamed over WebSocket/SSE to the desktop UI.

---

## ⚙️ Configuration & Pinning
- **Runtime Provider**: `deepseek_harness`
- **Adapter Location**: `apps/backend/app/agent/runtime/deepseek_harness.py`
- **Manager Registry**: `apps/backend/app/agent/runtime/manager.py`
- **Execution Limits**: `MAX_RUNTIME_SECONDS = 600`, `MAX_STEPS = 20`, `MAX_RETRIES = 3`.
