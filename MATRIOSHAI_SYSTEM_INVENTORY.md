# MATRIOSHAI System Inventory & Component Dependency Map

## 1. Applications & Packages
- **`apps/backend`**: FastAPI Python 3.14 async server providing the core browser operating system runtime, WebSocket Bridge, Agent Loop, World Model, Verification Engine, Transaction Engine, Security Engine, Observability, and REST endpoints.
- **`apps/browser-extension`**: Chrome Extension Manifest V3 runtime with background service worker (`service-worker.ts`), browser controller (`browser-controller.ts`), content scripts (`observation-engine.ts`, `semantic-analyzer.ts`, `visual-engine.ts`, `action-dom-executor.ts`, `world-model-extractor.ts`), and popup UI.
- **`apps/desktop`**: Tauri 2.0 desktop application (React 18 + TypeScript + Vite + Tailwind CSS + Lucide Icons) with features for agent perception, workflow execution, transaction review, security center, and runtime health monitoring.

---

## 2. Subsystem File Inventory & Caller Mapping

| Subsystem | Key Files | Primary Callers / Upstream | Downstream Dependencies |
|---|---|---|---|
| **Phase 1: Foundation** | `apps/browser-extension/manifest.json`, `service-worker.ts`, `content-script.ts` | Chrome Browser, User actions | `chrome.tabs`, `chrome.windows`, DOM |
| **Phase 2: Communication Bridge** | `apps/backend/app/browser/bridge.py`, `apps/browser-extension/src/core/browser-bridge.ts` | `BrowserManager`, Background Worker | WebSocket `/api/v1/browser/bridge/ws` |
| **Phase 3: Browser Control** | `apps/backend/app/browser/manager.py`, `apps/browser-extension/src/core/browser-controller.ts` | `AgentExecutionLoop`, REST API `/api/v1/browser/` | `chrome.tabs.*`, `chrome.windows.*` |
| **Phase 4: Observation** | `apps/browser-extension/src/content/observation-engine.ts` | `content-script.ts`, `BrowserController` | Live DOM, CSS Computed Styles |
| **Phase 5: Semantics** | `apps/browser-extension/src/content/semantic-analyzer.ts`, `semantic-query-engine.ts` | `observation-engine.ts`, `content-script.ts` | ARIA attributes, Heuristics |
| **Phase 6: Visual Intelligence** | `apps/browser-extension/src/content/visual-engine.ts`, `visual-extractor.ts`, `visual-geometry.ts` | `content-script.ts`, `WorldModelExtractor` | DOM Bounding Boxes, Screenshots |
| **Phase 7: World Model** | `apps/backend/app/browser/world_model.py`, `apps/browser-extension/src/content/world-model-extractor.ts` | `AgentExecutionLoop`, `TransactionEngine` | `BrowserStateStore` |
| **Phase 8: Action Engine** | `apps/backend/app/browser/action_engine.py`, `apps/browser-extension/src/content/action-dom-executor.ts` | `AgentExecutionLoop`, `TransactionCommitEngine` | `SecurityEngine`, `BridgeClient`, DOM |
| **Phase 9: Verification** | `apps/backend/app/browser/verification_engine.py` | `AgentExecutionLoop`, `TransactionCommitEngine` | `world_model_engine`, DOM diffs |
| **Phase 10: Agent Loop** | `apps/backend/app/browser/agent_loop.py` | REST API, Workflow Engine | `world_model_engine`, `action_engine`, `verification_engine` |
| **Phase 11: Workflows** | `apps/backend/app/browser/agent_loop.py`, `manager.py` | REST API `/api/v1/browser/agent/` | `AgentExecutionLoop`, `BrowserStateStore` |
| **Phase 12: Transactions** | `apps/backend/app/browser/transaction_engine.py` | REST API `/api/v1/browser/transactions/` | `SecurityEngine`, `action_engine`, `verification_engine` |
| **Phase 13: Security** | `apps/backend/app/browser/security_engine.py` | `BrowserManager`, `action_engine`, `TransactionEngine` | `BrowserStateStore` |
| **Phase 14: Production Runtime** | `apps/backend/app/browser/runtime.py`, `observability.py`, `resilience.py`, `model_gateway.py`, `chaos.py` | `BrowserManager`, FastApi lifespan | All Subsystems |
