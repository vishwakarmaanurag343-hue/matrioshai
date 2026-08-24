# MATRIOSHAI Actual Architecture & Control/Data Flow Reconstruction

## 1. Verified Architecture Flow

```
USER INTENT (Desktop UI / REST API)
       │
       ▼
[Security Policy Engine] ──(Evaluate Request: Risk, Autonomy, Spending, Prompt Injection)
       │
  (Allowed / Token Issued)
       │
       ▼
[Agent Execution Loop] ──(Goal Normalization & Step Plan)
       │
       ▼
[World Model Engine] ──(Fetch Cached Snapshot or Trigger Observation)
       │
       ▼
[Bridge Client / WebSocket] ──(Send Request: action / observation / navigation)
       │
       ▼
[Chrome Extension Service Worker]
       │
       ▼
[Content Script DOM Executor] ──(Dispatch Synthetic Events: mousedown -> mouseup -> click)
       │
       ▼
[Live Website DOM]
       │
       ▼
[Observation Engine & Mutation Tracker] ──(DOM + ARIA + Computed Styles + Bounding Boxes)
       │
       ▼
[Postcondition Verification Engine] ──(Multi-signal verification: URL, DOM, Visual, State)
       │
       ▼
[State Store & Observability Manager] ──(Update World Version, Trace, Metrics, Audit Log)
       │
       ▼
RESULT RETURNED TO AGENT / USER
```

## 2. Documented Claims vs. Actual Code Findings

| Claimed Feature | Actual Code Status | Evidence |
|---|---|---|
| Bidirectional WebSocket Bridge | **VERIFIED & FUNCTIONAL** | `apps/backend/app/browser/bridge.py` & `apps/browser-extension/src/core/browser-bridge.ts` handle handshake, ping/pong, and JSON-RPC dispatch. |
| DOM Mutation Tracking | **VERIFIED & FUNCTIONAL** | `apps/browser-extension/src/content/mutation-tracker.ts` observes live DOM mutations with debounce. |
| Multi-Signal Verification | **VERIFIED & FUNCTIONAL** | `apps/backend/app/browser/verification_engine.py` evaluates 18 failure classifications and composite strategies (`ALL`, `ANY`, `AT_LEAST_N`). |
| Single-Use Action Authorization Tokens | **VERIFIED & FUNCTIONAL** | `apps/backend/app/browser/security_engine.py` validates and immediately consumes tokens upon execution to prevent replay. |
| Transaction Pre-Commit Freezing | **VERIFIED & FUNCTIONAL** | `apps/backend/app/browser/transaction_engine.py` validates `PREPARE != COMMIT` and snapshot immutability. |
| Circuit Breaker & Retry Engine | **VERIFIED & FUNCTIONAL** | `apps/backend/app/browser/resilience.py` trips on repeated failures and blocks blind retries on mutating actions. |
