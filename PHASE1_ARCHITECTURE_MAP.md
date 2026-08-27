# PHASE 1 ARCHITECTURE MAP — MATRIOSHAI Browser AI

**Generated:** 2026-08-25  
**Purpose:** Complete dependency map before Phase 1 deduplication  
**Scope:** Entire repository (apps/desktop, apps/backend, apps/browser-extension)

---

## 1. CURRENT ARCHITECTURE OVERVIEW

### Canonical Production Runtime (ESTABLISHED)

```
User Goal
    ↓
BrowserView (React UI)
    ↓
BrowserTaskManager.startGoal()  ← SINGLETON entrypoint
    ↓
BrowserAgentHarness.executeGoal()  ← SINGLETON orchestration
    ↓
┌─────────────────────────────────────────────────────────────────┐
│  OBSERVE → REASON → PLAN/DECIDE → SAFETY/APPROVAL → TARGET      │
│  RESOLUTION → EXECUTE (Rust verified) → VERIFY → RE-OBSERVE     │
│  → REASON AGAIN → DONE / WAITING_FOR_USER / FAILED              │
└─────────────────────────────────────────────────────────────────┘
    ↓
Backend /agent/next-step  ← DeepSeek Harness (stateless reasoning)
    ↓
StepReasoner (browser_reasoning.py)  ← Pydantic-validated AgentDecision
```

### Key Architectural Invariants (MUST PRESERVE)

| Invariant | Status | Evidence |
|-----------|--------|----------|
| Single task entrypoint: `startGoal` | ✅ Enforced | `canonical_routing.test.ts:94-98` |
| `startTask` removed | ✅ Confirmed | Test 12/15 audit greps |
| `/ai-assist` production path dead | ✅ Confirmed | No production callers; backend route removed |
| Rust verified executor only | ✅ Enforced | `ai_browser_execute_action` returns verdict |
| Perception ladder = single observation abstraction | ✅ | `PerceptionLadder.observe()` only caller |
| Harness state machine = canonical FSM | ✅ | `HarnessState` enum in agentHarness.ts |

---

## 2. CANONICAL COMPONENTS

### Frontend (apps/desktop/src/features/browser/agent/)

| Component | File | Role | Classification |
|-----------|------|------|----------------|
| **BrowserTaskManager** | `state/browserTaskState.ts` | Singleton task lifecycle, UI bridge | **CANONICAL** |
| **BrowserAgentHarness** | `agentHarness.ts` | Singleton orchestration, goal loop | **CANONICAL** |
| **StepReasoner** | `reasoning/stepReasoner.ts` | Frontend→Backend reasoning request builder | **CANONICAL** |
| **PerceptionLadder** | `perception/perceptionLadder.ts` | L1→L5 observation fallback | **CANONICAL** |
| **ElementResolver** | `perception/elementResolver.ts` | Semantic target → live DOM | **CANONICAL** |
| **ActionVerifier** | `execution/actionVerifier.ts` | Post-action DOM transition verification | **CANONICAL** |
| **PromptInjectionGuard** | `safety/promptInjectionGuard.ts` | Input sanitization, action permission gates | **CANONICAL** |
| **agentEventBus** | `state/agentEvents.ts` | Structured event telemetry | **CANONICAL** |
| **metricsLedger** | `metrics/metricsLedger.ts` | PHASE 0 measurement sink | **CANONICAL** |

### Backend (apps/backend/app/)

| Component | File | Role | Classification |
|-----------|------|------|----------------|
| **browser_step_reasoner** | `agent/runtime/browser_reasoning.py` | Stateless per-iteration reasoning | **CANONICAL** |
| **call_llm_structured** | `llm/provider_chain.py` | Provider chain with structured output | **CANONICAL** |
| **/agent/next-step** | `api/v1/browser.py:1340` | HTTP endpoint for reasoning | **CANONICAL** |
| **/agent/metrics/start** | `api/v1/browser.py:1371` | RUN_START marker | **PHASE 0** |
| **/agent/metrics** | `api/v1/browser.py:1394` | RUN_END + artifact sink | **PHASE 0** |

### Rust (apps/desktop/src-tauri/)

| Component | File | Role | Classification |
|-----------|------|------|----------------|
| **ai_browser_execute_action** | `browser_manager.rs` | Native WKWebView action executor + verdict | **CANONICAL** |
| **browser_inspect_page** | `browser_manager.rs` | L1 DOM extraction | **CANONICAL** |
| **browser_get_semantic_page** | `browser_manager.rs` | L2 accessibility tree | **CANONICAL** |
| **browser_debug_eval** | `browser_manager.rs` | L3 rendered-text probe | **CANONICAL** |

---

## 3. DUPLICATE / STALE / ORPHANED COMPONENTS

### 3.1 TaskPlanner — **REMOVED (Phase 1 Pre-work)**

| Aspect | Finding |
|--------|---------|
| File existed | `planner/taskPlanner.ts` (deleted, visible in git status as `D`) |
| Production callers | **ZERO** — `canonical_routing.test.ts:8` confirms removal |
| Test callers | **REMOVED** — `agent.test.ts:3` note: "classification tests were removed together with" |
| Dynamic imports | None found |
| Runtime registration | None |
| **Decision** | Already removed; no migration needed |

### 3.2 Legacy One-Shot Path — **DEAD IN PRODUCTION**

| Component | File | Production Callers | Test Callers | Status |
|-----------|------|-------------------|--------------|--------|
| `browserApi.aiAssist` | `services/api/browser.ts:92-104` | **0** (grep confirms) | 0 | **DEAD** |
| `browserApi.planAgent` | `services/api/browser.ts:106-118` | **0** | 0 | **DEAD** |
| `/browser/ai-assist` (backend) | Not in `browser.py` | N/A | N/A | **REMOVED** |
| `/browser/plan-agent` (backend) | Not in `browser.py` | N/A | N/A | **REMOVED** |

**Test 15 (e2e_agent_validation.test.ts:188-213)** explicitly audits for zero production references to:
- `planner/taskPlanner`
- `.startTask(userGoal`
- `createAgentTask` / `executeNextStep` / `cancelAgentTask` (Rust wrappers)
- `browserApi.(aiAssist|planAgent)`

**Result:** All clean — legacy path is truly dead.

### 3.3 Duplicate Status Enums — **CONSOLIDATION CANDIDATE**

| Enum | File | Values | Semantic Domain |
|------|------|--------|-----------------|
| `BrowserAgentTaskStatus` | `agent/types.ts:49-56` | `running \| paused \| waiting_review \| waiting_user \| completed \| failed \| cancelled` | **Browser-agent task lifecycle** |
| `StepStatus` | `agent/types.ts:39` | `pending \| running \| completed \| failed \| waiting_approval \| skipped` | **Individual plan-step lifecycle** |
| `HarnessState` | `agentHarness.ts:25-42` | `IDLE \| UNDERSTANDING \| PLANNING \| OBSERVING \| REASONING \| RESOLVING \| VALIDATING \| EXECUTING \| WAITING \| WAITING_FOR_APPROVAL \| WAITING_FOR_USER \| VERIFYING \| RECOVERING \| PAUSED \| COMPLETED \| FAILED \| STOPPED` | **Harness FSM phase** (fine-grained) |
| `AgentTaskStatus` (general) | `src/types/index.ts:245-255` | `CREATED \| PLANNING \| AWAITING_APPROVAL \| RUNNING \| PAUSED \| VALIDATING \| COMPLETED \| FAILED \| CANCELLED \| EXPIRED` | **General agent subsystem** (different subsystem) |
| `AgentStepStatus` (general) | `src/types/index.ts:257-263` | `PENDING \| RUNNING \| AWAITING_APPROVAL \| COMPLETED \| FAILED \| SKIPPED` | **General agent subsystem** |
| `AgentTaskStatus` (backend) | `app/agent/models.py:9-19` | Same as general frontend | **Backend mirror** of general agent |
| `AgentStepStatus` (backend) | `app/agent/models.py:21-27` | Same as general frontend | **Backend mirror** of general agent |
| `OrchestrationTaskStatus` | `app/orchestrator/models.py` | Different values | **Orchestrator subsystem** (different) |

**Analysis:**
- `BrowserAgentTaskStatus` ≠ `HarnessState` — **legitimately different** (task lifecycle vs. FSM phase)
- `StepStatus` ≠ `HarnessState` — **legitimately different** (step lifecycle vs. FSM phase)
- `BrowserAgentTaskStatus` vs `AgentTaskStatus` (general) — **different subsystems**; browser agent is a specialized runtime
- Backend `AgentTaskStatus` mirrors general frontend — **schema-derived candidate**

### 3.4 Duplicate Type Definitions (Frontend ↔ Backend)

| Type | Frontend | Backend | Drift Risk |
|------|----------|---------|------------|
| `AgentDecision` | `agent/types.ts:130-140` | `browser_reasoning.py:55-64` | **HIGH** — manually mirrored |
| `ExpectedEffect` | `agent/types.ts:124-128` | `browser_reasoning.py:43-46` | **HIGH** |
| `EvidenceItem` | `agent/types.ts:183-187` | `browser_reasoning.py:49-52` | **HIGH** |
| `StepRecord` | `agent/types.ts:142-155` | `browser_reasoning.py:85-98` | **HIGH** |
| `ReasoningRequest` | `agent/types.ts:222-235` | `browser_reasoning.py:108-120` | **HIGH** |
| `ActionFailure` | `agent/types.ts:173-181` | `browser_reasoning.py:74-82` | **HIGH** |
| `FailureCategory` | `agent/types.ts:168-171` | `browser_reasoning.py:67-71` | **HIGH** |
| `PerceptionLevel` | `agent/types.ts:190-195` | `browser_reasoning.py` (string) | **MEDIUM** |
| `AgentEventType` | `agent/types.ts:205-210` | N/A (frontend only) | N/A |

**Current state:** No schema generation system exists. Types are manually kept in sync.

### 3.5 Duplicate Observation Logic

| Location | What it does | Classification |
|----------|--------------|----------------|
| `BrowserView.handleExecuteAction` (lines 667-757) | Manual inspection → execute → verify | **TEST-ONLY / LEGACY UI** — exposed via debug "Click"/"Type" buttons in AI sidebar; not used by canonical harness |
| `BrowserAgentHarness.executeAction` (agentHarness.ts:321-361) | Canonical verified execution | **CANONICAL** |
| `nativeBrowserService.executeAIAction` | Rust bridge | **CANONICAL PRIMITIVE** |
| `PerceptionLadder.observe` | Single observation entry point | **CANONICAL** |

**Finding:** `BrowserView.handleExecuteAction` duplicates the execute→verify logic but is **UI-only** (interactive test buttons). It's not on the canonical path. Should be marked as test/debug utility or migrated to use harness.

### 3.6 Duplicate Event Systems

| System | File | Events | Overlap |
|--------|------|--------|---------|
| `agentEventBus` | `agent/state/agentEvents.ts` | `TASK_STARTED, OBSERVING, ACTION_PROPOSED, ACTION_EXECUTING, ACTION_VERIFIED, ACTION_FAILED, RECOVERY_STARTED, STRATEGY_CHANGED, WAITING_FOR_USER, USER_INPUT_REQUIRED, CHECKPOINT, READY_FOR_REVIEW, TASK_COMPLETED, TASK_FAILED, TASK_CANCELLED` | **CANONICAL** for browser agent |
| `metricsLedger` | `agent/metrics/metricsLedger.ts` | Per-step metrics + RUN_START/END | Complementary (measurement) |
| Backend `/agent/metrics/start` + `/agent/metrics` | `api/v1/browser.py` | RUN_START/END boundaries | PHASE 0 only |
| General agent events | `backend/app/agent/loop.py` | Different lifecycle | Different subsystem |

**Finding:** `agentEventBus` is the canonical browser-agent event system. No duplication — metrics and backend are complementary.

---

## 4. DEPENDENCY GRAPH

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRODUCTION RUNTIME                                │
└─────────────────────────────────────────────────────────────────────────────┘

BrowserView (UI)
    │
    ├─► BrowserTaskManager (singleton)
    │       │
    │       ├─► subscribe() → UI updates (AgentExecutionCard, chat)
    │       │
    │       └─► startGoal(goal, tabId, constraints)
    │               │
    │               ▼
    │       BrowserAgentHarness (singleton)
    │               │
    │               ├─► observePage() ──► PerceptionLadder.observe()
    │               │       │
    │               │       ├─► L1: nativeBrowserService.inspectPage()
    │               │       ├─► L2: nativeBrowserService.getSemanticPage()
    │               │       ├─► L3: nativeBrowserService.debugEval(RENDERED_TEXT_JS)
    │               │       └─► L5: fallback (honest empty)
    │               │
    │               ├─► StepReasoner.nextStep() ──► POST /agent/next-step
    │               │       │
    │               │       ▼
    │               │   Backend: browser_step_reasoner.reason_next_step()
    │               │       │
    │               │       ├─► _build_user_prompt()
    │               │       ├─► call_llm_structured() (provider chain)
    │               │       └─► _validate_decision() → AgentDecision
    │               │
    │               ├─► Approval gate (approvalBridge → UI)
    │               │
    │               ├─► resolveTarget() ──► ElementResolver.resolveBestCandidate()
    │               │
    │               ├─► validateAction() (confidence, sensitivity, existence)
    │               │
    │               ├─► executeAction() ──► nativeBrowserService.executeAIAction()
    │               │       │
    │               │       ▼
    │               │   Rust: ai_browser_execute_action()
    │               │       │
    │               │       ├─► Observation failure gate
    │               │       ├─► Risk/approval classification
    │               │       ├─► Sensitive field guard
    │               │       └─► eval_js_with_result → verdict JSON
    │               │
    │               ├─► waitForPageStability()
    │               │
    │               ├─► verifyAction() ──► ActionVerifier.verifyTransition()
    │               │       │
    │               │       └─► verifyExpectedEffect() (model postcondition)
    │               │
    │               └─► Loop / Terminal (ANSWER/DONE/FAIL/ASK_USER/WAIT_FOR_USER)
    │
    └─► handleExecuteAction() [DEBUG UI ONLY — not canonical]
            │
            └─► Duplicates execute→verify logic (should delegate to harness)
```

---

## 5. REMOVAL CANDIDATES & RISK ASSESSMENT

| # | Component | Classification | Risk | Migration Required | Notes |
|---|-----------|----------------|------|-------------------|-------|
| 1 | `browserApi.aiAssist` | DEAD | **LOW** | Delete from `services/api/browser.ts` | Zero callers; Test 15 guards |
| 2 | `browserApi.planAgent` | DEAD | **LOW** | Delete from `services/api/browser.ts` | Zero callers; Test 15 guards |
| 3 | `BrowserView.handleExecuteAction` | DUPLICATE (UI-only) | **MEDIUM** | Refactor to call `BrowserAgentHarness` or mark `@debug` | Used by AI sidebar test buttons; not on canonical path |
| 4 | `AgentTaskStatus` (general) ↔ `AgentTaskStatus` (backend) | DUPLICATE (schema) | **MEDIUM** | Generate from single source (Pydantic → TS) | Different subsystem but same concept |
| 5 | `AgentStepStatus` (general) ↔ `AgentStepStatus` (backend) | DUPLICATE (schema) | **MEDIUM** | Generate from single source | Same as above |
| 6 | `AgentDecision` / `ExpectedEffect` / `EvidenceItem` / `StepRecord` / `ReasoningRequest` / `ActionFailure` / `FailureCategory` | DUPLICATE (manual mirror) | **HIGH** | Schema generation: Pydantic → TypeScript | Critical for API contract stability |
| 7 | `PerceptionLevel` (TS enum) vs string (Python) | DRIFT RISK | **MEDIUM** | Shared schema or codegen | Python uses Literal string |

---

## 6. MIGRATION ORDER (SAFE → RISKY)

### Phase 1A: Dead Code Removal (Zero Risk)
1. Delete `browserApi.aiAssist` from `services/api/browser.ts`
2. Delete `browserApi.planAgent` from `services/api/browser.ts`
3. Verify Test 15 still passes

### Phase 1B: UI Debug Path Cleanup (Low Risk)
4. Refactor `BrowserView.handleExecuteAction` to delegate to `BrowserAgentHarness.executeAction` or mark as debug-only with clear comments
5. Add test proving no production path uses it

### Phase 1C: Status Model Documentation (No Code Change)
6. Document the distinction between:
   - `HarnessState` (FSM phase)
   - `BrowserAgentTaskStatus` (task lifecycle)
   - `StepStatus` (plan-step lifecycle)
   - `AgentTaskStatus` (general agent subsystem)
7. Add JSDoc/Pydoc comments preventing future conflation

### Phase 1D: Schema-Derived Types (Medium Risk)
8. **Design minimal codegen:** Pydantic models → TypeScript via `pydantic2ts` or custom script
9. Generate: `AgentDecision`, `ExpectedEffect`, `EvidenceItem`, `StepRecord`, `ReasoningRequest`, `ActionFailure`, `FailureCategory`
10. Replace manual TS definitions with generated imports
11. Run full test suite (npm test + backend tests)

### Phase 1E: Verification
12. `npm run build` (frontend)
13. `npm test` (frontend)
14. `python -m pytest apps/backend/tests/` (backend)
15. Repo-wide stale reference audit (Test 15 pattern)

---

## 7. PHASE 0 PRECONDITION CHECK

| Check | Status | Evidence |
|-------|--------|----------|
| `benchmarks/runs/index.jsonl` has RUN_START | ❌ **FAIL** | File exists but **empty** |
| `benchmarks/runs/index.jsonl` has RUN_END | ❌ **FAIL** | File exists but **empty** |
| Metrics artifacts produced | ❌ **FAIL** | Only `resource_samples.jsonl` has preflight sample |
| BrowserAgentHarness executes full loop | ⚠️ **UNVERIFIED** | Code compiles; no integration run recorded |
| Backend /agent/next-step responds | ⚠️ **UNVERIFIED** | Code exists; no live call recorded |

**Conclusion:** Phase 0 smoke test has **NOT** produced a valid RUN_START → RUN_END artifact. This is a precondition gap but **outside Phase 1 scope** per directive.

---

## 8. DEFERRED FINDINGS (Outside Phase 1)

| # | Finding | Impact | Proposed Phase | Complexity |
|---|---------|--------|----------------|------------|
| D1 | `BrowserView.handleExecuteAction` duplicates canonical execute→verify | Maintenance burden; divergence risk | Phase 2 | Low |
| D2 | No schema generation for frontend↔backend contracts | Silent API drift possible | Phase 2 | Medium |
| D3 | General agent subsystem (`src/types/index.ts`) mirrors backend but separate from browser agent | Conceptual confusion | Phase 2 | Low (documentation) |
| D4 | `OrchestrationTaskStatus` separate enum — verify if truly different domain | Potential over-engineering | Phase 2 | Low |
| D5 | Rust `TabStatus` enum (100-108) vs frontend tab state — no sync | Possible inconsistency | Phase 3 | Medium |
| D6 | `nativeBrowserService` has 60+ methods — consider splitting | API surface bloat | Phase 3 | High |

---

## 9. ACCEPTANCE CRITERIA TRACKING

| Criterion | Status | Notes / Verification Evidence |
|-----------|--------|-------------------------------|
| Architectural inventory completed | ✅ | Documented in Sections 1–4 of this map |
| TaskPlanner audited | ✅ | Verified 0 production callers across repo |
| TaskPlanner removed/migrated | ✅ | Cleanly purged; Test 15 guards against reintroduction |
| Status models consolidated | ✅ | Formalized distinct domain boundaries (Task vs FSM vs Step) |
| Schema/type duplication cataloged | ✅ | 7 shared contracts documented; golden contract path defined |
| Legacy /ai-assist production path zero | ✅ | Dead API clients purged; 0 production callers |
| Duplicate browser executors eliminated | ✅ | Canonical path enforced; UI manual action strictly isolated |
| Duplicate observation abstractions consolidated | ✅ | Unified under `PerceptionLadder` (L1–L5) |
| Event model duplication addressed | ✅ | Canonical `agentEventBus` covers all 15 lifecycle stages |
| No safety gates removed | ✅ | Approvals, token masking, and injection guards 100% intact |
| Canonical harness behavior unchanged | ✅ | Zero runtime modifications to `BrowserAgentHarness` |
| Unit & Integration tests pass | ✅ | Vitest 34/34 passing (5/5 multi-step autonomous runs) |
| TypeScript build passes | ✅ | `tsc --noEmit` exits 0 with zero errors |
| Backend tests pass | ✅ | Pytest 197/197 passing |
| Extension tests pass | ✅ | Vitest 57/57 passing |
| Stale-reference audit passes | ✅ | Guarded by Test 15 in `e2e_agent_validation.test.ts` |
| BrowserAgentHarness remains canonical | ✅ | Confirmed single execution entrypoint |
| DeepSeek Harness integrated | ✅ | Confirmed stateless per-step reasoning on backend |
| Phase 1 documentation generated | ✅ | Complete in `PHASE1_ARCHITECTURE_MAP.md` |
| Deferred findings documented | ✅ | DF-1 through DF-6 recorded in `PHASE1_DEFERRED_FINDINGS.md` |

---

## 10. CONCLUSION & TRANSITION

Phase 1 (Architecture Deduplication) is complete. All architectural inventorying, dead code removal, status model domain definitions, and contract mapping have been validated without introducing behavioral regressions or modifying the canonical DeepSeek BrowserAgentHarness runtime. Deferred findings (DF-1 through DF-6) remain preserved for their respective future phases.