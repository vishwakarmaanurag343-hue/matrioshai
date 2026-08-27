# PHASE 1 — DEFERRED FINDINGS

Weaknesses discovered during the Phase 1 audit that are OUTSIDE Phase 1 scope.
Recorded per the critical rule: do not silently fix; document, propose phase, estimate.

---

## DF-1: Backend closed-loop browser agent = second execution system — [RESOLVED in Phase 2D]
- **Resolution**: Retired dead backend autonomous loop (`apps/backend/app/browser/agent_loop.py`), retired dead manager methods (`create_agent_task`, `start_agent_task`, `pause_agent_task`, `resume_agent_task`, `abort_agent_task`, `get_agent_task`), and removed dead `/api/v1/browser/agent/tasks*` route registrations. All live supporting infrastructure (`bridge.py`, `security_engine.py`, `transaction_engine.py`, `action_engine.py`, `verification_engine.py`, `world_model.py`, `state_store.py`, history, tabs) and canonical desktop Browser AI execution (`BrowserAgentHarness` → `/agent/next-step` → Rust) remain 100% intact and verified across full test matrices.

## DF-2: Hardcoded backend origin in runtime dashboards — [RESOLVED in Phase 1.5]
- **Resolution**: All production network requests in `chat.ts`, `RuntimeHealthDashboard.tsx`, `ObservabilityPanel.tsx`, `SecurityCenter.tsx`, and `MainLayout.tsx` have been migrated to import and use the canonical `API_BASE_URL` from `services/api/client.ts`. Anti-regression test added to `e2e_agent_validation.test.ts` (Test 15).

## DF-3: GET /openapi.json returns HTTP 500 on the running backend — [RESOLVED in Phase 1.5]
- **Resolution**: In `app/api/v1/browser.py`, `SecurityRequest` was missing from module imports, causing Pydantic's OpenAPI schema generator to fail with a `ForwardRef` definition error on `POST /browser/security/evaluate`. Added `from app.browser.state_store import SecurityRequest`. Schema generation now returns HTTP 200 (178 paths, 176KB schema). Automated regression test added to `test_backend.py`.

## DF-4: Dual trace channels (logTrace console stream vs AgentEventBus)
- **Problem**: harness emits both `logTrace()` (console + subscribe traceLog) and `agentEventBus.publish()`. Overlapping but non-identical payloads; AgentExecutionCard consumes both indirectly.
- **Impact**: two places to update when adding lifecycle stages; minor drift risk.
- **Proposed future phase**: derive developer trace from the event bus (single emitter) once event model gains REASONING stage (R4 lands the additive piece).
- **Risk**: LOW-MED (UI rendering assumptions). **Complexity**: M.

## DF-5: FFI-boundary type triplication for page model (TS ↔ Rust ↔ Python)
- **Problem**: `SemanticPageModel` exists as Rust struct, hand-written TS interface (nativeService), and backend pydantic models; same for `AIActionResult`.
- **Impact**: silent drift possible across three definitions.
- **Proposed future phase**: extend the R5 JSON-Schema golden-contract approach to FFI structs (Rust side needs schemars or hand-written golden files).
- **Risk**: MED (Rust codegen dependency decision). **Complexity**: M–L.

## DF-6: Extension owns a parallel agent command vocabulary
- **Problem**: browser-extension defines `agent.createGoal/startTask/pauseTask/…` message commands and its own state machine, independent of the desktop harness vocabulary.
- **Impact**: conceptual duplication only today (extension drives backend bridge, not WKWebView directly); risk of divergent semantics.
- **Proposed future phase**: extension alignment after DF-1 resolution.
- **Risk**: unknown until DF-1 lands. **Complexity**: M.
