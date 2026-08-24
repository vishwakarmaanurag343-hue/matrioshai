# MATRIOSHAI Browser Subsystem — Native Architecture & Layout

## 1. Overview
The MATRIOSHAI browser subsystem hosts real external web pages using native OS webview technologies:
- **macOS**: `WKWebView` via Tauri v2 child webview window embedding.
- **Windows**: `WebView2` (Chromium).
- **Linux**: `WebKitGTK`.

## 2. Geometry & Bounds Synchronization
- Native child webviews are embedded into the main application window beneath the React UI toolbar.
- The DOM bounding box of `.main-stage-container` and the browser viewport box are measured via `getBoundingClientRect()`.
- Titlebar and window frame metrics are queried via `get_content_view_offset`.
- Rust updates logical positions and dimensions via `webview.set_position` and `webview.set_size`.
- Layer masking applies native rounded corners (`setCornerRadius: 14.0`, `setMasksToBounds: YES`) on macOS AppKit `NSView`.

## 3. Visibility Management & Clean Unmounting
- Non-active tabs are hidden with `webview.hide()`.
- Switching views in MATRIOSHAI (e.g. from Browser to New Chats, Notepad, or Settings) invokes `browser_hide_all_webviews` to ensure no native overlay persists across other views.
