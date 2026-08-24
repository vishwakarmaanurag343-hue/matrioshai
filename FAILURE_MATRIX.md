# MATRIOSHAI Failure & Resilience Matrix

| Failure Mode | Detection Mechanism | System Impact | Retry Strategy | Recovery Strategy | User Action Required | Risk Level | Implementation Status |
|---|---|---|---|---|---|---|---|
| **Browser Disconnect** | Heartbeat failure / WebSocket close event | Agent actions fail with `DISCONNECTED` | Exponential backoff (max 5) | Automatic reconnect to localhost bridge | None (automatic) | Low | 🟢 COMPLETE |
| **Page Navigation Timeout** | `WaitForNavigation` timeout (5000ms) | Plan step marked `NAVIGATION_FAILED` | Safe retry on idempotent GET | Re-observe DOM & refresh tab state | None | Medium | 🟢 COMPLETE |
| **Element Not Found** | Semantic & Visual Element Resolver failure | Action blocked with `TARGET_NOT_FOUND` | Safe retry after DOM stabilization | Dynamic replanning with alternative selector | Clarification if ambiguous | Medium | 🟢 COMPLETE |
| **Action Execution Failure** | `ActionExecutor` DOM event exception | Action marked `FAILED` | Check `RetryEngine.can_retry()` | Rollback to last `WorkflowCheckpoint` | User Takeover if stuck | Medium | 🟢 COMPLETE |
| **Postcondition Failure** | `VerificationEngine` multi-signal check | Task pauses with `VERIFICATION_FAILED` | No blind retry on mutating actions | Evaluate `RecoveryTrace` recommendations | Manual review or intervention | High | 🟢 COMPLETE |
| **Price / Terms Drift** | `TransactionSnapshot` diff comparison | Commit blocked with `DRIFT_DETECTED` | Never retry | Regenerate review & request user confirmation | Re-confirm new terms | Critical | 🟢 COMPLETE |
| **Prompt Injection in DOM** | `PromptInjectionDefense` pattern scan | Text marked `UNTRUSTED_CONTENT` | Discard malicious instruction | Continue with sanitized goal | None | High | 🟢 COMPLETE |
| **Model Provider Outage** | `ModelProvider` circuit breaker trips | Primary LLM requests fail fast | Auto-route to `Fallback` provider | Circuit cooldown & half-open trial | None | High | 🟢 COMPLETE |
| **Infinite Action Loop** | `LoopDetector` 3x repetition detection | Agent loop halted with `LOOP_DETECTED` | Abort task | Request user intervention | Resolve ambiguity | High | 🟢 COMPLETE |
| **Emergency Stop Active** | Global kill switch flag checked in security gate | All autonomous actions blocked | Never retry while active | Invalidate pending authorizations | Manual emergency stop reset | Critical | 🟢 COMPLETE |
