# MATRIOSHAI Critical Findings & Adversarial Audit Log

## Severity Classification
- **P0**: System Blocker (Architecture failure, unrecoverable crash)
- **P1**: Critical (Data corruption, security bypass, unauthorized transaction)
- **P2**: High (Workflow failure under edge cases, circuit breaker stalls)
- **P3**: Medium (Suboptimal fallback, non-critical latency)
- **P4**: Low (Cosmetic UI state, minor logging discrepancy)

---

### Finding P2-01: Synchronous Model Generation Mock Fallback
- **Severity**: P2 (High)
- **Location**: `apps/backend/app/browser/model_gateway.py` -> `ModelProvider.generate_response()`
- **Problem**: When external LLM API keys (OpenAI / Anthropic / Gemini) are absent in the local development environment, the provider falls back to simulated responses to keep local pytest suites hermetic.
- **Impact**: In live production deployment, real API keys must be loaded via environment variables to avoid default simulated completions.
- **Fix**: Document required environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) and provide graceful validation warnings on startup.

### Finding P3-01: In-Memory Browser State Store Persistence Across Server Restarts
- **Severity**: P3 (Medium)
- **Location**: `apps/backend/app/browser/state_store.py`
- **Problem**: `BrowserStateStore` maintains world models, transaction snapshots, and authorizations in an in-memory thread-safe data structure (`_lock = threading.RLock()`).
- **Impact**: If the backend process is killed abruptly during an active long-horizon workflow, in-memory state is cleared. However, when the browser extension reconnects, it immediately triggers `reconcile_state()` and state synchronization via `/api/v1/browser/bridge/ws`.
- **Fix**: Maintain SQLite / PostgreSQL WAL persistence for active workflow checkpoints (`WorkflowCheckpoint`) across server restarts.

### Finding P4-01: Service Worker Background Heartbeat Interval
- **Severity**: P4 (Low)
- **Location**: `apps/browser-extension/src/background/service-worker.ts`
- **Problem**: Chrome MV3 service workers can be terminated by the browser after ~30s of inactivity.
- **Impact**: The persistent WebSocket connection in `BrowserBridgeClient` keeps the service worker active via heartbeat pings.
- **Fix**: The existing WebSocket ping/pong every 5s (`HEARTBEAT_INTERVAL_MS`) prevents early service worker termination.
