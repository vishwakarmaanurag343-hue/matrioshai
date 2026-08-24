# MATRIOSHAI Browser Subsystem — Production Architecture Audit

## 1. Executive Summary & Stack Baseline

- **Platform & Host OS**: macOS (Apple Silicon / Intel), Windows, Linux (Tauri 2 cross-platform target).
- **Core Framework**: Tauri v2.0 (`tauri = "2.0.0"`, `features = ["unstable"]`).
- **Backend Language**: Rust 2021 edition (`matrioshai_lib`).
- **Frontend Framework**: React 18 (`react`, `react-dom`), TypeScript 5.2, Vite 5.
- **Native Browser Surface Architecture**: Multi-webview single-window child architecture via `tauri::window::Window::add_child(...)` embedding native `WKWebView` (macOS) / `WebView2` (Windows) / `WebKitGTK` (Linux).
- **Excluded Subsystems**: Tor Browser/routing (EXCLUDED), Crypto/Web3 Wallet (EXCLUDED).

---

## 2. Current Browser Architecture vs. Target Specification

| Subsystem | Current State | Target Brave-Level State | Gap & Action Plan |
|---|---|---|---|
| **Native WebView Compositing** | Child WebViews added to main window; runtime geometry calibrated with asymmetric insets (`MARGIN_TOP = 34px`, `MARGIN_SIDES = 4px`). | Deterministic layout synchronization system tracking window resizes, sidebar collapse/expand, and scale factor. | Maintain robust zero-lag synchronization without arbitrary viewport regressions. |
| **Search Engine Resolver** | `SearchEngineResolver` in `resolver.ts` with Google, Bing, Brave, DuckDuckGo. | Full search engine selection with suggestions, customizable templates (Startpage, Ecosia, Custom), and profile persistence. | Expand search suggestion provider and profile-bound defaults. |
| **Privacy & Ad-Shields** | In-memory evaluation and statistics tracking in `browser_manager.rs`. Global and per-site shields. | Full Brave-grade privacy pipeline: ad-blocking, tracker prevention, fingerprinting defenses, cookie partitioning, HTTPS upgrade, query param stripping, and WebRTC privacy. | Enhance network-level request classification and cosmetic filter list engines. |
| **Profiles & Isolation** | Data structures for `BrowserProfile` (REGULAR, PRIVATE, GUEST). | Full data partition across cookies, localStorage, cache, bookmarks, passwords, and history per profile. | Integrate profile storage isolation and session restore. |
| **Credentials & Autofill** | Basic permission schema. | OS keychain credential store (macOS Keychain, Windows Credential Manager) with passkey support and zero-plaintext storage. | Build secure OS credential adapter. |
| **History & Bookmarks** | Initial state handling. | Full profile-scoped bookmarks (folders, tags, search) and date-grouped history with privacy-first deletion. | Implement persistent indexed store for bookmarks and history. |
| **Downloads Manager** | Standard Tauri opener. | Full download lifecycle manager (pause, resume, retry, security inspection, folder reveal). | Connect native download event interceptor and download UI drawer. |
| **AI Assistant & Context Security** | Semantic page extraction with read-only gates. | Independent AI sidebar with prompt-injection defenses, untrusted-input sanitization, multi-tab reasoning, and explicit human confirmation for sensitive actions. | Fortify untrusted-content prompt boundaries and interactive approval gates. |
| **Extension Feasibility** | WKWebView native container. | Comprehensive documentation of WKWebView extension limitations vs. content script injection engine. | Document `docs/browser/EXTENSION_COMPATIBILITY.md`. |

---

## 3. WebView Lifecycle & Window Coordinate Geometry

1. **Window Hierarchy**:
   - `tauri::Window` ("main") hosts the React shell UI (Sidebar, Tab Bar, Address Bar, AI Assistant Drawer).
   - Each browser tab corresponds to a native child `tauri::Webview` embedded inside the content stage container.
2. **Coordinate & Bounds Synchronization**:
   - `containerRef.getBoundingClientRect()` computes logical coordinates in DOM space.
   - `get_content_view_offset` measures OS titlebar/frame insets.
   - Rust applies `webview.set_position(LogicalPosition)` and `webview.set_size(LogicalSize)`.
   - Native macOS CALayer masking applies `setCornerRadius(14.0)` and `setMasksToBounds(YES)` directly on `NSView` for matching rounded aesthetic.
3. **Visibility Management**:
   - Non-active tabs are hidden via `webview.hide()`.
   - On navigation out of the Browser view into other MATRIOSHAI modules (Chats, Notepad), `hideAllWebviews()` ensures zero visual overlap on other app screens.

---

## 4. Security & Untrusted Web Context Model

- Webpage content is treated as **untrusted external data**.
- AI tools and semantic analysis operate over structured, sanitised DOM snapshots (`SemanticPageModel`).
- Sensitive operations (financial actions, form submission, external API triggers) require human authorization via the `HumanApprovalGate` modal.
- Passwords and private tokens are excluded from logs, telemetry, and unencrypted state stores.

---

## 5. Implementation Roadmap

- **M1**: Native Browser Foundation & Hardened Layout Synchronization.
- **M2**: Tabs, Multi-Window, & Navigation Management.
- **M3**: Multi-Engine Search & Dynamic Suggestions.
- **M4**: Profiles, Storage Partitioning, & Private Mode.
- **M5**: Privacy Shields & Network Filter Lists.
- **M6**: Security, OS Keyring Passwords, & Autofill.
- **M7**: Bookmarks, History, & Download Management.
- **M8**: AI Sidebar, Multi-Tab Reasoning, & Injection Protection.
- **M9**: Agentic Browser Automation with Human-in-the-Loop Gates.
- **M10**: Documentation & Production Readiness Verification.
