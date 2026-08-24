# MATRIOSHAI Global Engineering & Async-First Rules

As the principal software architect and senior engineer of MATRIOSHAI, these principles govern all backend, frontend, agent runtime, and tooling code across the entire project.

---

## 🏛 1. Core Architectural Foundation

1. **Production-Grade & Asynchronous-First**:
   - MATRIOSHAI is an asynchronous, concurrent AI operating system.
   - Non-blocking I/O is mandatory for Network, Database, Filesystem, LLM inference, Tool executions, Browser automation, and Background tasks.
   - CPU-local, short, deterministic operations remain synchronous to avoid unnecessary overhead.

2. **Parallelize Independent Operations**:
   - Independent lookups (Memory + Knowledge Graph + Project Workspace + Permissions) MUST execute concurrently via `asyncio.gather()` / `Promise.all()` with structured error handling.
   - Never serialize independent I/O tasks.

3. **Intelligent Concurrency & Backpressure**:
   - Concurrency is bounded via worker pools, semaphores, connection pools, and rate limiters.
   - Heavy operations (Agent tasks, Large file ingestion, Embeddings) MUST execute in background workers and stream status via WebSocket/SSE rather than blocking the main HTTP request thread.

4. **Cancellation & Configurable Timeouts**:
   - All long-running operations MUST support cancellation (`asyncio.CancelledError`, `AbortController`, TaskGroups).
   - Every external I/O and tool execution MUST have explicit, configurable timeouts.

5. **Safe Retries & Idempotency**:
   - Transient failures (network glitches, rate limits) may be retried with exponential backoff and jitter.
   - Side-effecting operations (`send_message`, `write_file`, `apply_patch`, `mouse_click`) MUST NOT be automatically retried without idempotency keys.

6. **Streaming-First AI & Event Normalization**:
   - LLM generation streams tokens and progress events in real-time.
   - Raw agent events are normalized into structured `AgentEvent` records with correlation IDs before UI streaming.

7. **Security & Permission Boundaries**:
   - Concurrency must never bypass security gates (`ToolRegistry`, `PermissionEngine`, `ConfirmationSystem`).
   - Sensitive actions require explicit human confirmation with exact hash binding.

8. **Observability & Distributed Tracing**:
   - Every task and event MUST carry `request_id` and `correlation_id` through the full call chain for transparent debugging and audit trails.

---

## 🧭 Pre-Implementation Checklist for Every Feature

Before implementing any new module or refactor, verify:
- [ ] Is this operation I/O-bound? If yes, is it asynchronous?
- [ ] Are independent I/O tasks parallelized concurrently?
- [ ] Are timeouts and cancellation propagation configured?
- [ ] Does it have external side effects requiring idempotency keys?
- [ ] Does it pass through the ToolRegistry and ConfirmationSystem?
- [ ] Is it traceable via correlation IDs without exposing secrets?
- [ ] Is concurrency bounded to protect system CPU/RAM/GPU?
