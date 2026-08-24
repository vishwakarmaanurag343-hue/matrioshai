# MATRIOSHAI Browser Subsystem — Extension Compatibility Analysis

## 1. Executive Summary
Under the current macOS engine (`WKWebView`), arbitrary Chrome Web Store extensions (`.crx` / Manifest V3) cannot be loaded directly as if in Chromium, because Apple's `WKWebView` sandbox does not expose Chromium extension runtime APIs (`chrome.runtime`, `chrome.tabs`, `chrome.declarativeNetRequest`).

## 2. Technical Capabilities on WKWebView
- **Content Scripts**: Fully supported via user script injection (`WKUserScript` / `initialization_script`).
- **CSS Injection & Modification**: Supported dynamically via `eval` and stylesheet tags.
- **Custom Native API Gateways**: Supported via Tauri IPC (`invoke`, `listen`, `eval`).
- **DOM & Semantic Extraction**: Supported safely without leaking private context.

## 3. Migration Recommendation
For full Chrome Web Store and Manifest V3 extension compatibility, a dedicated Chromium-based engine (e.g. CEF or Ultralight) or Chrome Native Messaging Host can be targeted in a future platform upgrade.
