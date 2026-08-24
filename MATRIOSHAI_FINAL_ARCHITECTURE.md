# MATRIOSHAI Unified Personal AI Operating System
## Master Architecture & Production Runtime Specification (Phases 1 — 14)

---

## 1. Executive Overview

**MATRIOSHAI** is a stateful, policy-controlled, verified autonomous browser and computer-use operating system. It transforms fragmented web tasks and complex multi-step digital workflows into deterministic, resilient, and verifiable autonomous executions.

```
                         USER
                           │
                           ▼
                 ┌───────────────────┐
                 │  USER CONTROL     │
                 │  SECURITY CENTER  │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ SECURITY ENGINE   │ (Phase 13: Master Security Boundary)
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ RUNTIME SUPERVISOR│ (Phase 14: Health & Resilience)
                 │ & OBSERVABILITY   │
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ WORKFLOW ENGINE   │ (Phase 11: Long-Horizon Workflows)
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ AGENT RUNTIME     │ (Phase 10: Closed-Loop Planning)
                 └─────────┬─────────┘
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
        ┌─────────────────┐  ┌─────────────────┐
        │ TRANSACTION     │  │ WORLD MODEL     │
        │ ENGINE (P12)    │  │ (P7)            │
        └────────┬────────┘  └────────┬────────┘
                 │                    │
                 └─────────┬──────────┘
                           ▼
                 ┌───────────────────┐
                 │ ACTION ENGINE     │ (Phase 8: Deterministic Action Dispatch)
                 └─────────┬─────────┘
                           ▼
                 ┌───────────────────┐
                 │ BROWSER RUNTIME   │ (P1-P6: Observation, Semantics & Visuals)
                 └─────────┬─────────┘
                           │
                           ▼
                       WEBSITE
                           │
                           ▼
                 ┌───────────────────┐
                 │ VERIFICATION      │ (Phase 9: Postcondition & Recovery Engine)
                 └─────────┬─────────┘
                           │
                           ▼
                 ┌───────────────────┐
                 │ CHECKPOINT /      │
                 │ EVENT / AUDIT     │
                 └───────────────────┘
```

---

## 2. Complete Phase Breakdown (Phases 1 to 14)

| Phase | Subsystem | Core Responsibilities |
|---|---|---|
| **Phase 1** | **Extension Foundation** | Manifest V3 background service worker, secure popup UI, content scripts, DOM mutation observers. |
| **Phase 2** | **Browser ↔ Backend Bridge** | Localhost-only, token-authenticated, bidirectional WebSocket bridge (`/api/v1/browser/bridge/ws`) with versioned JSON-RPC protocol v1.0. |
| **Phase 3** | **Deterministic Browser Manager** | Tab/window lifecycle, active tab synchronization, deterministic navigation, history tracking, reload, and back/forward navigation. |
| **Phase 4** | **Page Observation Engine** | High-fidelity DOM tree serialization, computed styles, interactive element indexing, frame hierarchy traversal. |
| **Phase 5** | **Semantic & Accessibility Intelligence** | ARIA tree extraction, role/name/value mapping, live region tracking, semantic search & ambiguity resolution. |
| **Phase 6** | **Visual Page Intelligence** | Coordinate math, client-side PII visual redaction, screenshot capture, canvas/SVG/overlay detection, point-to-element mapping. |
| **Phase 7** | **Unified Browser World Model** | Temporal state graph, immutable snapshots (`world_model_version`), element stability tracking, and state diffing. |
| **Phase 8** | **Safe Browser Action Engine** | Single-step deterministic action execution (`CLICK`, `TYPE`, `CLEAR`, `SELECT`, `CHECK`, `UNCHECK`, `SCROLL`, `KEY_PRESS`), FIFO tab action serialization, dry-run mode. |
| **Phase 9** | **Action Verification & Recovery** | Multi-signal postcondition verification (`ALL`, `ANY`, `AT_LEAST_N`), 18 discrete failure classifications, and idempotency-gated recovery recommendations. |
| **Phase 10** | **Agent Planning & Execution Loop** | Closed-loop planning (`OBSERVE ➔ MODEL ➔ PLAN ➔ AUTHORIZE ➔ ACT ➔ VERIFY`), loop oscillation detection, dynamic replanning, and goal satisfaction criteria. |
| **Phase 11** | **Long-Horizon Workflow Engine** | Directed Acyclic Graph (DAG) task orchestration, cross-tab coordination, milestone checkpointing, and partial failure isolation. |
| **Phase 12** | **Real-World Transaction Engine** | High-consequence transaction pipeline (`DISCOVERY ➔ COMPARISON ➔ SELECTION ➔ PREPARATION ➔ SNAPSHOT ➔ REVIEW ➔ CONFIRM ➔ REVALIDATE ➔ COMMIT ➔ VERIFY ➔ RECEIPT`). Enforces `PREPARE != COMMIT`, `CLICK != COMPLETED`, `UNKNOWN != SUCCESS`. |
| **Phase 13** | **Security, Permissions & Human-in-the-Loop** | Master security boundary (`USER > SECURITY > WORKFLOW > AGENT > TRANSACTION > ACTION`), prompt injection defense, secret redaction, single-use `ActionAuthorization` tokens, human takeover, and global emergency stop kill switch. |
| **Phase 14** | **Production Hardening & Runtime** | `MatrioshaiRuntime` state machine, `RuntimeSupervisor` with exponential backoff restart policy, `CircuitBreaker` states (`CLOSED`, `OPEN`, `HALF_OPEN`), `RetryEngine` risk classification, `DeadLetterQueue`, and distributed tracing (`correlation_id`, `trace_id`). |

---

## 3. Fundamental Operating Principles

1. **Hierarchy of Authority**:
   ```
   USER > SYSTEM SECURITY POLICY > USER POLICY > WORKFLOW > AGENT PLAN > WEBSITE CONTENT
   ```
   - Webpage content is **untrusted data** and can never override security policies.
   - LLMs are untrusted reasoning engines and cannot grant themselves permissions.
2. **Fail-Closed Principle**:
   - Unknown domains, unknown security state, or missing authorizations default to `DENY` or `REQUIRE_USER`.
3. **Transaction Invariants**:
   - `PREPARE != COMMIT`: Preparation only freezes the pre-commit snapshot.
   - `REVIEW != COMMIT`: Review displays price/fee breakdowns without modifying state.
   - `CLICKED != COMPLETED`: Clicking commit dispatches an intent and awaits multi-signal verification.
   - `UNKNOWN != SUCCESS`: An unknown outcome halts automatic retries to avoid duplicate charges or bookings.
4. **Resilience & Fault Isolation**:
   - Failure of one tab does not crash other sessions.
   - Failure of one model call routes through `ModelRouter` to fallback models.
   - Cascading failures trip `CircuitBreaker` (`CLOSED ➔ OPEN ➔ HALF_OPEN ➔ CLOSED`).
   - Unrecoverable events are captured in the `DeadLetterQueue`.

---

## 4. API & Subsystem Contracts

- **Security Gate**: `evaluate_security_request(request: SecurityRequest) -> (SecurityDecision, Optional[ActionAuthorization], str)`
- **Transaction Engine**: `commit_transaction(transaction_id, commit_action, auth) -> (TransactionState, Optional[TransactionReceipt], str)`
- **Action Engine**: `execute_action(intent: ActionIntent, authorization_id: str) -> ActionResult`
- **Verification Engine**: `verify_action(action_result, before_snapshot, after_snapshot) -> VerificationResult`
- **Runtime Supervisor**: `attempt_restart(component_name: str, policy: RestartPolicy) -> (bool, str)`
- **Observability**: `start_trace(op, correlation_id) -> trace_id`, `end_trace(trace_id, status)`

---

## 5. Verification Matrix Summary

- **Backend Pytest Suite**: **97 / 97 PASSED** (0 failures).
- **Extension Vitest Suite**: **57 / 57 PASSED** (12 test suites, 0 failures).
- **TypeScript Typechecks**: **0 errors** (`tsc --noEmit`).
- **Production Extension Bundle**: Built cleanly via Vite with Manifest V3 compatibility.
