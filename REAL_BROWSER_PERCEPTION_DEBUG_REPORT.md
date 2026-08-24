# REAL BROWSER PERCEPTION DEBUG & FIX REPORT

## 1. Executive Summary

During hands-on adversarial real-world browser execution against `https://www.google.com`, the desktop browser subsystem exhibited total perception failure:
- **Observation Result**: `elements: 0`, `links: 0`, `text_blocks: 1`
- **Execution Log**: `[EXTRACTION_TIMEOUT_OR_FALLBACK] took=2027ms`
- **Safety Violation**: Action was falsely marked as `Approved & Executed: Successfully executed action on target` despite zero verified interactive elements on the page.

Investigation identified the root cause in the **Tauri desktop app's native WebKit JS evaluation synchronization pipeline** (`apps/desktop/src-tauri/src/browser_manager.rs`), completely independent of the Chrome extension or backend.

---

## 2. Root Cause Analysis — Complete Failure Chain

### Root Cause 1: WebKit Async Completion Deadlock via Spin-Poll
- **File**: `apps/desktop/src-tauri/src/browser_manager.rs`
- **Mechanism**: `WKWebView.evaluateJavaScript:completionHandler:` dispatches JavaScript evaluation asynchronously and schedules its completion block on the Cocoa main thread run loop.
- **The Defect**: `eval_js_with_result` attempted to bridge this asynchronous callback to a synchronous return using a `thread::sleep(25ms)` loop for 40 iterations (1000ms total). On complex pages with strict CSP and heavy scripts, the completion block was starved/raced by the polling window, causing an unconditional timeout at 1000ms.

### Root Cause 2: Compounded Cache Spin-Poll Delay (2027ms Total)
- **File**: `apps/desktop/src-tauri/src/browser_manager.rs`
- **Mechanism**: When `eval_js_with_result` timed out (1000ms), `browser_get_semantic_page` entered a secondary fallback loop polling `semantic_page_cache` for 25 iterations × 40ms = 1000ms.
- **Total Duration**: `1000ms (eval timeout) + 1000ms (cache poll) + ~27ms (IPC overhead) = 2027ms`, precisely matching the log `[EXTRACTION_TIMEOUT_OR_FALLBACK] took=2027ms`.

### Root Cause 3: Silent Fabricated Fallback Model Masking Perception Failure
- **The Defect**: When both extraction strategies timed out, the engine silently synthesized a fake fallback `SemanticPageModel` containing `interactive_elements: vec![]` and `text_blocks: vec!["Structured document for Google (...)"]`.
- **Impact**: Downstream callers and LLMs received an empty shell that looked like a successful observation of an empty page rather than an observation error.

### Root Cause 4: Unconditional Action Execution Success Without Target Verification
- **The Defect**: `ai_browser_execute_action` returned `Ok(AIActionResult { success: true, message: "Successfully executed action on target" })` without verifying whether the target existed or whether the prior page observation had failed.

---

## 3. Fixes Implemented

### 1. Replaced Spin-Poll with POSIX/Cocoa `Condvar` Synchronization
- **File**: `apps/desktop/src-tauri/src/browser_manager.rs`
- **Change**: `eval_js_with_result` now wraps the result container in `Arc<(Mutex<Option<Result<String, String>>>, Condvar)>`. When WebKit's completion handler fires on the Cocoa run loop, it calls `cvar.notify_one()`. The background thread awaits with `cvar.wait_timeout_while()`, eliminating spin-lock starvation and properly yielding CPU.

### 2. Observation Lifecycle Status & Failure Tracking
- **Files**: `browser_manager.rs`, `nativeService.ts`, `types.ts`, `pageModel.ts`
- **Added Fields**:
  - `observation_status`: `"OBSERVATION_SUCCESS" | "OBSERVATION_TIMEOUT" | "OBSERVATION_FAILED" | "OBSERVATION_UNAVAILABLE"`
  - `observation_failed: bool`: Explicitly flags whether observation succeeded or encountered a failure.

### 3. Hard Safety Invariants: `OBSERVATION_FAILURE => ACTION_BLOCKED` & `TARGET_UNVERIFIED => ACTION_BLOCKED`
- **File**: `browser_manager.rs`
  - In `ai_browser_execute_action`, all write actions (`CLICK`, `TYPE`, `NAVIGATE`, `SUBMIT_FORM`, `SELECT`, `PRESS_KEY`) are strictly blocked if `cached.observation_failed == true`, returning an explicit error:
    `OBSERVATION_FAILURE — tab '{tab_id}' observation_status='{status}'. Target element cannot be verified.`
- **File**: `features/browser/agent/agentHarness.ts`
  - Added pre-action validation for targeted actions (`CLICK`, `TYPE`, `SELECT`): if target is unverified or unresolved, step fails immediately with `TARGET_UNVERIFIED => ACTION_BLOCKED`.

### 4. Pure Semantic DOM Extraction (Zero Site-Specific Selectors)
- **File**: `browser_manager.rs` (`EXTRACT_PAGE_CONTENT_SCRIPT`)
  - Purged all hardcoded Google-specific selectors (`#search`, `#rso`, `.VwiC3b`, `.b_algo`, `div.g`, `.MjjYud`, `.tF2Cxc`, `.yuRUbf`).
  - Implemented pure semantic / ARIA selectors:
    - Search inputs: `[role="searchbox"], [role="search"] input, input[type="search"], textarea[type="search"]`
    - Headings: `h1, h2, h3, h4, [role="heading"]`
    - Content: `main, [role="main"], article, [role="article"], [role="feed"]`
    - Action controls: `button, input:not([type="hidden"]), select, textarea, [role="button"], [role="link"], [role="tab"], [role="menuitem"]`

### 5. Structured Diagnostic Trace
- **Log Format**:
  - `[OBSERVATION_TRACE/START] request_id='...' tab_id='...' url='...'`
  - `[OBSERVATION_TRACE/EVAL_OK] request_id='...' eval_duration_ms=... json_len=...`
  - `[OBSERVATION_TRACE/SUCCESS] total_ms=... eval_ms=... elements=... links=... observation_status=OBSERVATION_SUCCESS`
  - `[OBSERVATION_TRACE/FAILED] total_ms=... url=... observation_status=OBSERVATION_TIMEOUT`

---

## 4. Verification & Validation Results

| Test Suite / Component | Status | Details |
|---|---|---|
| **Rust Backend Compilation** (`cargo check`) | **PASS** | 0 errors |
| **Desktop TypeScript Typecheck** (`tsc --noEmit`) | **PASS** | 0 errors |
| **Desktop Frontend Build** (`npm run build`) | **PASS** | 1662 modules transformed, built in 1.28s |
| **Python Backend Test Suite** (`pytest`) | **PASS** | **194 passed**, 0 failed in 2.48s |
| **Browser Extension Vitest Suite** | **PASS** | **57 passed** across 12 test files |

---

## 5. Remaining Limitations & Operating Boundaries

1. **JavaScript-Disabled Pages / Heavy Canvas UIs**: Web applications rendered purely onto HTML5 `<canvas>` (e.g. Google Docs canvas mode or complex WebGL apps) do not expose DOM nodes; visual grounding / VLM perception is required for those targets.
2. **Rate Limits / Captchas**: High-frequency autonomous navigation on adversarial search engines may trigger CAPTCHA challenges; the human takeover system (`takeover_state: HUMAN_CONTROL`) remains the designated fallback for interactive CAPTCHA resolution.
3. **Cross-Origin iFrames**: Cross-origin iframes with `sandbox` or strict `SameSite` policies restrict direct DOM traversal across frame boundaries unless extension bridge permissions are active.

---

## 6. Final Status

**FIXED** — Native WebKit perception pipeline is unblocked from the spin-poll deadlock, explicit observation health status is propagated throughout the system, and safety invariants block execution whenever perception is unverified.
