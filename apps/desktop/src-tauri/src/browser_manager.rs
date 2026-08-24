use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter, Manager, State, WebviewUrl};
use url::Url;

#[cfg(target_os = "macos")]
fn apply_rounded_corners<R: tauri::Runtime>(webview: &tauri::Webview<R>, radius: f64) {
    use cocoa::base::id;
    use cocoa::base::YES;
    use objc::{msg_send, sel, sel_impl};

    let _ = webview.with_webview(move |platform_webview| {
        #[cfg(target_os = "macos")]
        unsafe {
            let ns_view: id = platform_webview.inner() as id;
            let () = msg_send![ns_view, setWantsLayer: YES];
            let layer: id = msg_send![ns_view, layer];
            if !layer.is_null() {
                let () = msg_send![layer, setCornerRadius: radius];
                let () = msg_send![layer, setMasksToBounds: YES];
            }
        }
    });
}

#[cfg(target_os = "macos")]
pub fn eval_js_with_result<R: tauri::Runtime>(
    webview: &tauri::Webview<R>,
    js: &str,
) -> Result<String, String> {
    use block::ConcreteBlock;
    use cocoa::base::{id, nil};
    use cocoa::foundation::NSString;
    use objc::{msg_send, sel, sel_impl};
    use std::sync::Condvar;

    // Use Condvar instead of spin-poll to correctly bridge WebKit's async
    // completionHandler back to this synchronous Tauri command thread.
    // Spin-poll with thread::sleep was causing a race where the 1000ms
    // deadline expired before WKWebView's completion block could be
    // dispatched on the Cocoa run loop.
    let pair = Arc::new((Mutex::new(None::<Result<String, String>>), Condvar::new()));
    let pair_clone = pair.clone();
    let js_owned = js.to_string();

    let _ = webview.with_webview(move |platform_webview| {
        unsafe {
            let ns_view: id = platform_webview.inner() as id;
            let t0 = std::time::Instant::now();
            println!(
                "[EVAL_BRIDGE/1_CLOSURE_RAN] len={} ns_view_ptr={:p}",
                js_owned.len(), ns_view
            );
            if ns_view != nil {
                let ns_js = NSString::alloc(nil).init_str(&js_owned);
                let pair_cb = pair_clone.clone();
                let block = ConcreteBlock::new(move |res: id, err: id| {
                    println!(
                        "[EVAL_BRIDGE/3_COMPLETION_FIRED] after_ms={} err_nonnil={} res_nonnil={}",
                        t0.elapsed().as_millis(),
                        err != nil,
                        res != nil
                    );
                    let result = if err != nil {
                        let desc: id = msg_send![err, localizedDescription];
                        if desc != nil {
                            let bytes: *const std::os::raw::c_char = msg_send![desc, UTF8String];
                            if !bytes.is_null() {
                                Err(std::ffi::CStr::from_ptr(bytes).to_string_lossy().into_owned())
                            } else {
                                Err("JS evaluation failed (no description)".to_string())
                            }
                        } else {
                            Err("JS evaluation failed".to_string())
                        }
                    } else if res != nil {
                        let desc_ns: id = msg_send![res, description];
                        if desc_ns != nil {
                            let bytes: *const std::os::raw::c_char = msg_send![desc_ns, UTF8String];
                            if !bytes.is_null() {
                                Ok(std::ffi::CStr::from_ptr(bytes).to_string_lossy().into_owned())
                            } else {
                                Ok(String::new())
                            }
                        } else {
                            Ok(String::new())
                        }
                    } else {
                        Ok(String::new())
                    };

                    // Signal the waiting thread — this is the Condvar notify.
                    let (lock, cvar) = &*pair_cb;
                    if let Ok(mut guard) = lock.lock() {
                        *guard = Some(result);
                        cvar.notify_one();
                    }
                });
                let block = block.copy();
                let () = msg_send![ns_view, evaluateJavaScript:ns_js completionHandler:&*block];
                println!("[EVAL_BRIDGE/2_EVAL_SENT] after_ms={}", t0.elapsed().as_millis());
                // NOTE (Phase 15): Do NOT pump the main NSRunLoop here to force
                // completion delivery. Blocking the Cocoa main thread inside
                // tao's message handler re-enters the event loop and hard-freezes
                // the app. Result delivery latency is handled elsewhere.
            } else {
                // webview inner is nil — signal immediately with error
                let (lock, cvar) = &*pair_clone;
                if let Ok(mut guard) = lock.lock() {
                    *guard = Some(Err("WKWebView inner is nil".to_string()));
                    cvar.notify_one();
                }
            }
        }
    });

    // Wait for the Condvar signal with a 3-second timeout.
    // This correctly yields the thread without spin-polling.
    let (lock, cvar) = &*pair;
    let timeout = std::time::Duration::from_secs(3);
    if let Ok(guard) = lock.lock() {
        match cvar.wait_timeout_while(guard, timeout, |result| result.is_none()) {
            Ok((mut guard, _)) => {
                return guard.take().unwrap_or(Err("JS evaluation timed out (Condvar)".to_string()));
            }
            Err(_) => {}
        }
    }
    Err("JS evaluation timed out (Condvar wait failed)".to_string())
}

#[cfg(not(target_os = "macos"))]
fn apply_rounded_corners<R: tauri::Runtime>(_webview: &tauri::Webview<R>, _radius: f64) {}

#[cfg(not(target_os = "macos"))]
pub fn eval_js_with_result<R: tauri::Runtime>(_webview: &tauri::Webview<R>, _js: &str) -> Result<String, String> {
    Err("Direct JS evaluation with result only supported on macOS".to_string())
}

pub const MODERN_USER_AGENT: &str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15";

pub const BRAVE_ADBLOCK_AND_YOUTUBE_SCRIPT: &str = r#"
(() => {
    // 1. Hide WebKit scrollbars cleanly
    function injectScrollbarHide() {
        if (!document.getElementById('matrioshai-hide-scrollbar')) {
            const style = document.createElement('style');
            style.id = 'matrioshai-hide-scrollbar';
            style.textContent = `
                ::-webkit-scrollbar {
                    width: 0px !important;
                    height: 0px !important;
                    display: none !important;
                }
                * {
                    scrollbar-width: none !important;
                    -ms-overflow-style: none !important;
                }
            `;
            (document.head || document.documentElement).appendChild(style);
        }
    }

    let totalBlockedInPage = 0;

    // 2. Cosmic / Cosmetic Ad-Blocker CSS rules
    function injectCosmeticAdblock() {
        if (!document.getElementById('matrioshai-adblock-cosmetic')) {
            const style = document.createElement('style');
            style.id = 'matrioshai-adblock-cosmetic';
            style.textContent = `
                /* Web Ads */
                .adsbygoogle, [id^="google_ads_"], [id^="gpt-ad-"], .ad-banner, .advertisement,
                .ad-container, .ad-placeholder, .taboola-ad, .outbrain-ad, [data-ad-unit],
                /* YouTube Safe Cosmetic Filtering */
                ytd-banner-promo-renderer, ytd-in-feed-ad-layout-renderer, #masthead-ad,
                ytd-promoted-sparkles-web-renderer, ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-ads"],
                ytd-statement-banner-renderer, ytd-merch-shelf-renderer, tp-yt-paper-dialog:has(ytd-enforcement-message-view-model) {
                    display: none !important;
                    visibility: hidden !important;
                    height: 0 !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                }
            `;
            (document.head || document.documentElement).appendChild(style);
        }

        // Count cosmetic blocked elements
        const adElements = document.querySelectorAll('.adsbygoogle, [id^="google_ads_"], .ad-banner, .advertisement, .ad-container, ytd-banner-promo-renderer, ytd-in-feed-ad-layout-renderer, #masthead-ad');
        if (adElements.length > totalBlockedInPage) {
            totalBlockedInPage = adElements.length;
            window.__matrioshai_blocked_count = totalBlockedInPage;
        }
    }

    // 3. YouTube Ad Handling & Skip-Button Auto-Clicker
    function handleYouTubeAds() {
        if (!location.hostname.includes('youtube.com')) return;

        // Auto-click Skip Button as soon as YouTube renders it
        const skipButtons = document.querySelectorAll('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button, .ytp-ad-skip-button-text');
        if (skipButtons.length > 0) {
            totalBlockedInPage += skipButtons.length;
            window.__matrioshai_blocked_count = totalBlockedInPage;
        }
        skipButtons.forEach(btn => {
            try { btn.click(); } catch(e) {}
        });

        // Close overlay banners
        const closeOverlayButtons = document.querySelectorAll('.ytp-ad-overlay-close-button');
        if (closeOverlayButtons.length > 0) {
            totalBlockedInPage += closeOverlayButtons.length;
            window.__matrioshai_blocked_count = totalBlockedInPage;
        }
        closeOverlayButtons.forEach(btn => {
            try { btn.click(); } catch(e) {}
        });

        // Auto-dismiss anti-adblock dialog if present
        const enforcementDialog = document.querySelector('tp-yt-paper-dialog:has(ytd-enforcement-message-view-model), ytd-enforcement-message-view-model');
        if (enforcementDialog) {
            try {
                enforcementDialog.remove();
                totalBlockedInPage += 1;
                window.__matrioshai_blocked_count = totalBlockedInPage;
                const video = document.querySelector('video');
                if (video && video.paused) {
                    video.play().catch(() => {});
                }
            } catch(e) {}
        }
    }

    // 4. Live URL Synchronization with Address Bar
    let lastKnownUrl = '';
    function syncAddressBarUrl() {
        try {
            const curUrl = window.location.href;
            if (curUrl && curUrl !== lastKnownUrl && curUrl !== 'about:blank') {
                lastKnownUrl = curUrl;
                const tid = window.__MATRIOSHAI_TAB_ID__ || '';
                const pStr = JSON.stringify({ url: curUrl, title: document.title || curUrl });
                if (window.__TAURI_INTERNALS__ && typeof window.__TAURI_INTERNALS__.invoke === 'function') {
                    window.__TAURI_INTERNALS__.invoke('receive_page_extraction', { tabId: tid, data: pStr }).catch(() => {});
                } else if (window.__TAURI__ && window.__TAURI__.core && typeof window.__TAURI__.core.invoke === 'function') {
                    window.__TAURI__.core.invoke('receive_page_extraction', { tabId: tid, data: pStr }).catch(() => {});
                }
            }
        } catch(e) {}
    }

    const originalPushState = history.pushState;
    history.pushState = function() {
        originalPushState.apply(this, arguments);
        syncAddressBarUrl();
    };

    const originalReplaceState = history.replaceState;
    history.replaceState = function() {
        originalReplaceState.apply(this, arguments);
        syncAddressBarUrl();
    };

    window.addEventListener('popstate', syncAddressBarUrl);
    window.addEventListener('load', syncAddressBarUrl);
    setInterval(syncAddressBarUrl, 1000);

    function runShieldsEngine() {
        injectScrollbarHide();
        injectCosmeticAdblock();
        handleYouTubeAds();
        syncAddressBarUrl();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', runShieldsEngine);
    } else {
        runShieldsEngine();
    }

    setInterval(handleYouTubeAds, 500);

    const observer = new MutationObserver(runShieldsEngine);
    observer.observe(document.documentElement, { childList: true, subtree: true });
})();
"#;

pub const CHROME_EXTENSION_POLYFILL: &str = r#"
(() => {
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            id: "matrioshai-ext",
            getURL: function(path) {
                if (!path) return "";
                if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("data:")) return path;
                return path;
            },
            sendMessage: function(msg, cb) {
                if (typeof cb === "function") cb({ status: "ok" });
                return Promise.resolve({ status: "ok" });
            },
            onMessage: {
                addListener: function() {},
                removeListener: function() {},
                hasListener: function() { return false; }
            },
            onConnect: {
                addListener: function() {},
                removeListener: function() {}
            },
            connect: function() {
                return {
                    onMessage: { addListener: function() {} },
                    onDisconnect: { addListener: function() {} },
                    postMessage: function() {},
                    disconnect: function() {}
                };
            }
        };
    }
    if (!window.chrome.storage) {
        window.chrome.storage = {
            local: {
                get: function(keys, cb) {
                    var res = {};
                    try {
                        if (typeof keys === "string") {
                            var item = localStorage.getItem("ext_" + keys);
                            if (item) res[keys] = JSON.parse(item);
                        } else if (Array.isArray(keys)) {
                            keys.forEach(function(k) {
                                var item = localStorage.getItem("ext_" + k);
                                if (item) res[k] = JSON.parse(item);
                            });
                        }
                    } catch(e) {}
                    if (typeof cb === "function") cb(res);
                    return Promise.resolve(res);
                },
                set: function(items, cb) {
                    try {
                        if (items && typeof items === "object") {
                            Object.keys(items).forEach(function(k) {
                                localStorage.setItem("ext_" + k, JSON.stringify(items[k]));
                            });
                        }
                    } catch(e) {}
                    if (typeof cb === "function") cb();
                    return Promise.resolve();
                },
                remove: function(keys, cb) {
                    try {
                        if (typeof keys === "string") localStorage.removeItem("ext_" + keys);
                    } catch(e) {}
                    if (typeof cb === "function") cb();
                    return Promise.resolve();
                }
            },
            sync: {
                get: function(keys, cb) { return window.chrome.storage.local.get(keys, cb); },
                set: function(items, cb) { return window.chrome.storage.local.set(items, cb); }
            }
        };
    }
    if (!window.chrome.tabs) {
        window.chrome.tabs = {
            query: function(queryInfo, cb) {
                var tabList = [{ id: 1, active: true, url: window.location.href, title: document.title }];
                if (typeof cb === "function") cb(tabList);
                return Promise.resolve(tabList);
            },
            sendMessage: function(tabId, msg, cb) {
                if (typeof cb === "function") cb({ status: "ok" });
                return Promise.resolve({ status: "ok" });
            }
        };
    }
    if (!window.chrome.i18n) {
        window.chrome.i18n = {
            getMessage: function(msgName) { return msgName; }
        };
    }
})();
"#;

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum ProfileType {
    REGULAR,
    PRIVATE,
    GUEST,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BrowserProfile {
    pub id: String,
    pub name: String,
    pub profile_type: ProfileType,
    pub storage_path: String,
    pub created_at: u64,
    pub last_used_at: u64,
    pub is_default: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum PermissionAction {
    ASK,
    ALLOW,
    DENY,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PermissionState {
    pub profile_id: String,
    pub origin: String,
    pub permission: String, // CAMERA, MICROPHONE, LOCATION, NOTIFICATIONS, CLIPBOARD
    pub state: PermissionAction,
    pub updated_at: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum ShieldLevel {
    STANDARD,
    STRICT,
    CUSTOM,
    OFF,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ShieldStats {
    pub ads_blocked: u64,
    pub trackers_blocked: u64,
    pub malicious_blocked: u64,
    pub total_evaluated: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SiteShieldSettings {
    pub origin: String,
    pub profile_id: String,
    pub level: ShieldLevel,
    pub ad_blocking_enabled: bool,
    pub tracker_blocking_enabled: bool,
    pub malware_protection_enabled: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum ActionRiskLevel {
    ReadOnly,
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
#[serde(default)]
pub struct InteractiveElement {
    pub element_id: String,
    pub role: String, // button, link, input, select, textarea
    pub name: String,
    pub tag: Option<String>,
    pub aria_label: Option<String>,
    pub title: Option<String>,
    pub href: Option<String>,
    pub input_type: Option<String>,
    pub placeholder: Option<String>,
    pub value: Option<String>,
    pub disabled: Option<bool>,
    pub visible: Option<bool>,
    pub selector: String,
    pub rect: Option<serde_json::Value>,
    pub sensitive: bool,
    pub accessible_name: Option<String>,
    pub enabled: Option<bool>,
    pub is_searchbox: Option<bool>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct SemanticPageModel {
    pub schema_version: String,
    pub page_id: String,
    pub page_version: u64,
    pub tab_id: String,
    pub url: String,
    pub origin: String,
    pub title: String,
    pub page_type: String, // ARTICLE, SEARCH, DOCUMENTATION, E_COMMERCE, LOGIN, FORM, UNKNOWN
    pub headings: Vec<String>,
    pub text_blocks: Vec<String>,
    pub interactive_elements: Vec<InteractiveElement>,
    pub forms_count: usize,
    pub tables_count: usize,
    pub links_count: usize,
    pub trust_level: String, // "untrusted" (provenance tagging)
    pub timestamp: u64,
    // Observation lifecycle fields — safety invariant tracking
    // observation_status: OBSERVATION_SUCCESS | OBSERVATION_TIMEOUT | OBSERVATION_FAILED | OBSERVATION_UNAVAILABLE
    pub observation_status: String,
    // observation_failed: true when extraction did not produce real DOM data.
    // ai_browser_execute_action MUST reject all actions when this is true.
    pub observation_failed: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
#[serde(default)]
pub struct ExtensionManifest {
    pub name: String,
    pub version: String,
    pub description: Option<String>,
    pub manifest_version: Option<u32>,
    pub permissions: Option<Vec<String>>,
    pub content_scripts: Option<Vec<ContentScriptSpec>>,
    pub action: Option<ExtensionActionSpec>,
    pub browser_action: Option<ExtensionActionSpec>,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
#[serde(default)]
pub struct ContentScriptSpec {
    pub matches: Option<Vec<String>>,
    pub js: Option<Vec<String>>,
    pub css: Option<Vec<String>>,
    pub run_at: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
#[serde(default)]
pub struct ExtensionActionSpec {
    pub default_title: Option<String>,
    pub default_popup: Option<String>,
    pub default_icon: Option<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct InstalledExtension {
    pub id: String,
    pub name: String,
    pub version: String,
    pub description: String,
    pub icon_url: Option<String>,
    pub enabled: bool,
    pub path: String,
    pub popup_path: Option<String>,
    pub content_scripts: Vec<ContentScriptSpec>,
    pub permissions: Vec<String>,
    pub installed_at: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ExtensionRuntimeState {
    pub extensions: HashMap<String, InstalledExtension>,
    pub extension_storage: HashMap<String, HashMap<String, serde_json::Value>>,
}

// Phase 8: Autonomous Agent Runtime & Task Engine Models
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum AgentTaskStatus {
    IDLE,
    UNDERSTANDING,
    PLANNING,
    WAITING_FOR_APPROVAL,
    EXECUTING,
    OBSERVING,
    VERIFYING,
    RECOVERING,
    REPLANNING,
    COMPLETED,
    FAILED,
    CANCELLED,
    BLOCKED,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PlanStep {
    pub step_id: String,
    pub description: String,
    pub tool: String,
    pub target: Option<String>,
    pub value: Option<String>,
    pub risk_level: ActionRiskLevel,
    pub status: String, // PENDING, RUNNING, SUCCESS, FAILED
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ExecutionPlan {
    pub plan_id: String,
    pub task_id: String,
    pub version: u64,
    pub objective: String,
    pub steps: Vec<PlanStep>,
    pub current_step_index: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TaskSpec {
    pub task_id: String,
    pub user_goal: String,
    pub tab_id: String,
    pub status: AgentTaskStatus,
    pub active_plan: Option<ExecutionPlan>,
    pub created_at: u64,
    pub updated_at: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BrowserContextSummary {
    pub tab_id: String,
    pub url: String,
    pub title: String,
    pub origin: String,
    pub visible_text_snippet: String,
    pub headings: Vec<String>,
    pub interactive_elements_count: usize,
    pub trust_level: String, // "untrusted" (provenance tagging)
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AIActionResult {
    pub success: bool,
    pub action: String,
    pub tab_id: String,
    pub risk_level: ActionRiskLevel,
    pub approval_required: bool,
    pub message: String,
    pub data: Option<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub enum TabStatus {
    CREATING,
    LOADING,
    READY,
    NAVIGATING,
    ERROR,
    CRASHED,
    CLOSING,
    CLOSED,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RectBounds {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TabGroup {
    pub id: String,
    pub name: String,
    pub color: String,
    pub collapsed: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BrowserTabState {
    pub id: String,
    pub webview_id: String,
    pub profile_id: String,
    pub url: String,
    pub title: String,
    pub favicon: Option<String>,
    pub loading: bool,
    pub progress: f64,
    pub can_go_back: bool,
    pub can_go_forward: bool,
    pub active: bool,
    pub visible: bool,
    pub pinned: bool,
    pub group_id: Option<String>,
    pub zoom_factor: f64,
    pub created_at: u64,
    pub last_active_at: u64,
    pub navigation_generation: u64,
    pub status: TabStatus,
    pub shield_stats: ShieldStats,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ClosedTabHistoryItem {
    pub url: String,
    pub title: String,
    pub closed_at: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BrowserNavigationEvent {
    pub event_type: String,
    pub tab_id: String,
    pub navigation_generation: u64,
    pub url: String,
    pub title: String,
    pub loading: bool,
    pub can_go_back: bool,
    pub can_go_forward: bool,
}

pub struct ShieldEngine {
    pub ad_domains: HashSet<String>,
    pub tracker_domains: HashSet<String>,
    pub malicious_domains: HashSet<String>,
    pub site_settings: HashMap<String, SiteShieldSettings>,
    pub global_level: ShieldLevel,
    pub total_stats: ShieldStats,
}

impl ShieldEngine {
    pub fn new() -> Self {
        let mut ad_domains = HashSet::new();
        let mut tracker_domains = HashSet::new();
        let mut malicious_domains = HashSet::new();

        for domain in [
            "doubleclick.net", "googlesyndication.com", "googleadservices.com",
            "adservice.google.com", "adnxs.com", "advertising.com", "taboola.com",
            "outbrain.com", "criteo.com", "moatads.com", "rubiconproject.com",
            "scorecardresearch.com", "quantserve.com", "casalemedia.com"
        ] {
            ad_domains.insert(domain.to_string());
        }

        for domain in [
            "analytics.google.com", "google-analytics.com", "hotjar.com",
            "clarity.ms", "segment.io", "mixpanel.com", "amplitude.com",
            "telemetry.microsoft.com", "facebook.net", "pixel.facebook.com"
        ] {
            tracker_domains.insert(domain.to_string());
        }

        for domain in [
            "malware-traffic.com", "phishing-test.com", "evil-tracker.info",
            "ransomware-payload.net", "crypto-stealer.biz"
        ] {
            malicious_domains.insert(domain.to_string());
        }

        Self {
            ad_domains,
            tracker_domains,
            malicious_domains,
            site_settings: HashMap::new(),
            global_level: ShieldLevel::STANDARD,
            total_stats: ShieldStats {
                ads_blocked: 0,
                trackers_blocked: 0,
                malicious_blocked: 0,
                total_evaluated: 0,
            },
        }
    }

    pub fn evaluate_url(&mut self, url_str: &str, profile_id: &str) -> (bool, Option<&'static str>) {
        self.total_stats.total_evaluated += 1;
        if let Ok(parsed) = Url::parse(url_str) {
            if let Some(host) = parsed.host_str() {
                let host_lower = host.to_lowercase();
                let key = format!("{}:{}", profile_id, host_lower);

                if let Some(setting) = self.site_settings.get(&key) {
                    if setting.level == ShieldLevel::OFF {
                        return (true, None);
                    }
                }

                if self.malicious_domains.iter().any(|d| host_lower == *d || host_lower.ends_with(&format!(".{}", d))) {
                    self.total_stats.malicious_blocked += 1;
                    return (false, Some("MALICIOUS_DOMAIN"));
                }

                if self.ad_domains.iter().any(|d| host_lower == *d || host_lower.ends_with(&format!(".{}", d))) {
                    self.total_stats.ads_blocked += 1;
                    return (false, Some("ADVERTISEMENT"));
                }

                if self.tracker_domains.iter().any(|d| host_lower == *d || host_lower.ends_with(&format!(".{}", d))) {
                    self.total_stats.trackers_blocked += 1;
                    return (false, Some("TRACKER"));
                }
            }
        }
        (true, None)
    }
}

pub struct AgentRuntimeState {
    pub tasks: HashMap<String, TaskSpec>,
    pub active_task_id: Option<String>,
}

pub struct BrowserManagerCore {
    pub profiles: HashMap<String, BrowserProfile>,
    pub active_profile_id: String,
    pub permissions: HashMap<String, PermissionState>,
    pub shield_engine: ShieldEngine,
    pub agent_runtime: AgentRuntimeState,
    pub tabs: HashMap<String, BrowserTabState>,
    pub tab_order: Vec<String>,
    pub tab_groups: HashMap<String, TabGroup>,
    pub extension_runtime: ExtensionRuntimeState,
    pub recently_closed_tabs: Vec<ClosedTabHistoryItem>,
    pub semantic_page_cache: HashMap<String, SemanticPageModel>,
    pub extraction_chunks: HashMap<String, (usize, Vec<Option<String>>)>,
    // Phase 15: latest DOM probe JSON per tab, delivered via the
    // document.title channel (see handle_title_extraction_event).
    pub probe_results: HashMap<String, String>,
    pub active_tab_id: Option<String>,
    pub current_bounds: Option<RectBounds>,
    pub generation_counter: u64,
}

fn current_timestamp() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

impl BrowserManagerCore {
    pub fn new() -> Self {
        let now = current_timestamp();
        let default_profile = BrowserProfile {
            id: "default".to_string(),
            name: "Default Profile".to_string(),
            profile_type: ProfileType::REGULAR,
            storage_path: "profiles/default".to_string(),
            created_at: now,
            last_used_at: now,
            is_default: true,
        };

        let mut profiles = HashMap::new();
        profiles.insert("default".to_string(), default_profile);

        Self {
            profiles,
            active_profile_id: "default".to_string(),
            permissions: HashMap::new(),
            shield_engine: ShieldEngine::new(),
            agent_runtime: AgentRuntimeState {
                tasks: HashMap::new(),
                active_task_id: None,
            },
            extension_runtime: ExtensionRuntimeState {
                extensions: HashMap::new(),
                extension_storage: HashMap::new(),
            },
            tabs: HashMap::new(),
            tab_order: Vec::new(),
            tab_groups: HashMap::new(),
            recently_closed_tabs: Vec::new(),
            semantic_page_cache: HashMap::new(),
            extraction_chunks: HashMap::new(),
            probe_results: HashMap::new(),
            active_tab_id: None,
            current_bounds: None,
            generation_counter: 0,
        }
    }
}

pub struct BrowserManagerState(pub Arc<Mutex<BrowserManagerCore>>);

#[derive(Debug, Deserialize)]
pub struct DynamicStepInput {
    pub step_id: String,
    pub tool: String,
    pub target: Option<String>,
    pub value: Option<String>,
    pub description: String,
    pub risk_level: Option<String>,
    pub needs_replan: Option<bool>,
}

// Phase 8: Autonomous Agent Runtime Commands
// (async): run these commands on the async runtime's thread pool instead of
// inline on the Cocoa main thread. Tauri v2 executes non-async commands
// INLINE on the main thread; any command that blocks (Condvar wait, poll
// loop) there starves the very WKWebView completion/title-KVO deliveries
// it is waiting on, because those are also dispatched on the main thread.
#[tauri::command(async)]
pub fn agent_create_task(
    state: State<'_, BrowserManagerState>,
    user_goal: String,
    tab_id: Option<String>,
    steps: Option<Vec<DynamicStepInput>>,
) -> Result<TaskSpec, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    let target_tab = tab_id.or_else(|| manager.active_tab_id.clone()).ok_or("No active browser tab found")?;
    let task_id = format!("task_{}", current_timestamp());

    let plan_steps: Vec<PlanStep> = if let Some(custom_steps) = steps {
        custom_steps.into_iter().take(15).map(|s| {
            let risk = match s.risk_level.as_deref().unwrap_or("Low") {
                "ReadOnly" => ActionRiskLevel::ReadOnly,
                "Medium" => ActionRiskLevel::Medium,
                "High" => ActionRiskLevel::High,
                "Critical" => ActionRiskLevel::Critical,
                _ => ActionRiskLevel::Low,
            };
            PlanStep {
                step_id: s.step_id,
                description: s.description,
                tool: s.tool,
                target: s.target,
                value: s.value,
                risk_level: risk,
                status: "READY".to_string(),
            }
        }).collect()
    } else {
        vec![
            PlanStep {
                step_id: "step_1".to_string(),
                description: format!("Observe page content for '{}'", user_goal),
                tool: "browser.observe_page".to_string(),
                target: None,
                value: None,
                risk_level: ActionRiskLevel::ReadOnly,
                status: "READY".to_string(),
            },
            PlanStep {
                step_id: "step_2".to_string(),
                description: "Extract verified semantic findings".to_string(),
                tool: "browser.get_semantic_page".to_string(),
                target: None,
                value: None,
                risk_level: ActionRiskLevel::ReadOnly,
                status: "PENDING".to_string(),
            },
        ]
    };

    let plan = ExecutionPlan {
        plan_id: format!("plan_{}", current_timestamp()),
        task_id: task_id.clone(),
        version: 1,
        objective: user_goal.clone(),
        steps: plan_steps,
        current_step_index: 0,
    };

    let task = TaskSpec {
        task_id: task_id.clone(),
        user_goal,
        tab_id: target_tab,
        status: AgentTaskStatus::PLANNING,
        active_plan: Some(plan),
        created_at: current_timestamp(),
        updated_at: current_timestamp(),
    };

    manager.agent_runtime.tasks.insert(task_id.clone(), task.clone());
    manager.agent_runtime.active_task_id = Some(task_id);

    Ok(task)
}

#[tauri::command(async)]
pub fn agent_execute_next_step(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    task_id: String,
) -> Result<TaskSpec, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;

    let task = manager.agent_runtime.tasks.get_mut(&task_id).ok_or("Task not found")?;
    if let Some(ref mut plan) = task.active_plan {
        // Hard Safety Cap: Max 15 steps per task
        if plan.current_step_index >= 15 {
            task.status = AgentTaskStatus::FAILED;
            return Err("Safety Cap Exceeded: Maximum 15 steps per autonomous task reached.".to_string());
        }

        if plan.current_step_index < plan.steps.len() {
            let step = &mut plan.steps[plan.current_step_index];
            step.status = "RUNNING".to_string();
            task.status = AgentTaskStatus::EXECUTING;

            // Execute step action on webview safely
            if let Some(webview) = app.get_webview(&task.tab_id) {
                if step.tool == "browser.scroll" {
                    let _ = webview.eval("window.scrollBy(0, 400);");
                }
            }

            step.status = "SUCCESS".to_string();
            plan.current_step_index += 1;

            if plan.current_step_index >= plan.steps.len() {
                task.status = AgentTaskStatus::COMPLETED;
            } else {
                plan.steps[plan.current_step_index].status = "READY".to_string();
                task.status = AgentTaskStatus::OBSERVING;
            }
        }
    }
    task.updated_at = current_timestamp();
    Ok(task.clone())
}

#[tauri::command]
pub fn agent_cancel_task(
    state: State<'_, BrowserManagerState>,
    task_id: String,
) -> Result<TaskSpec, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    let task = manager.agent_runtime.tasks.get_mut(&task_id).ok_or("Task not found")?;
    task.status = AgentTaskStatus::CANCELLED;
    task.updated_at = current_timestamp();
    Ok(task.clone())
}

pub const EXTRACT_PAGE_CONTENT_SCRIPT: &str = r#"
(() => {
    try {
        const _t0 = performance.now();
        const readyState = document.readyState;
        const currentUrl = window.location.href;
        const currentTitle = document.title || '';

        // Level 2: Computed Accessible Name per W3C Accessible Name Algorithm
        function computeAccessibleName(el) {
            // 1. aria-labelledby
            const labelledBy = el.getAttribute('aria-labelledby');
            if (labelledBy) {
                const names = labelledBy.split(/\s+/).map(id => {
                    const target = document.getElementById(id);
                    return target ? (target.innerText || target.textContent || '').trim() : '';
                }).filter(Boolean);
                if (names.length > 0) return names.join(' ');
            }
            // 2. aria-label
            const ariaLabel = el.getAttribute('aria-label');
            if (ariaLabel && ariaLabel.trim()) return ariaLabel.trim();

            // 3. placeholder (for inputs / search)
            if (el.placeholder && el.placeholder.trim()) return el.placeholder.trim();

            // 4. title attribute
            if (el.title && el.title.trim()) return el.title.trim();

            // 5. alt attribute (for images or inputs)
            if (el.alt && el.alt.trim()) return el.alt.trim();
            const childImg = el.querySelector('img[alt]');
            if (childImg && childImg.alt && childImg.alt.trim()) return childImg.alt.trim();

            // 6. Child headings / text content
            const childH = el.querySelector('h1, h2, h3, h4, h5, h6, [role="heading"], span, b, strong');
            if (childH) {
                const hText = (childH.innerText || childH.textContent || '').trim();
                if (hText) return hText;
            }

            // 7. innerText / textContent
            const text = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
            if (text) return text.slice(0, 120);

            // 8. Value for buttons / inputs
            if (el.value && typeof el.value === 'string' && el.value.trim()) {
                return el.value.trim().slice(0, 100);
            }

            return '';
        }

        // Level 2: ARIA role computation
        function computeRole(el) {
            const explicitRole = el.getAttribute('role');
            if (explicitRole) return explicitRole.toLowerCase().trim();

            const tag = el.tagName.toLowerCase();
            if (tag === 'input') {
                const type = (el.type || 'text').toLowerCase();
                if (type === 'search') return 'searchbox';
                if (['submit', 'button', 'reset', 'image'].includes(type)) return 'button';
                if (type === 'checkbox') return 'checkbox';
                if (type === 'radio') return 'radio';
                return 'textbox';
            }
            if (tag === 'textarea') return 'textbox';
            if (tag === 'select') return 'combobox';
            if (tag === 'button') return 'button';
            if (tag === 'a' && (el.href || el.getAttribute('href'))) return 'link';
            if (tag === 'form') return 'form';
            if (['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag)) return 'heading';
            if (tag === 'nav') return 'navigation';
            if (tag === 'main') return 'main';
            if (tag === 'article') return 'article';
            return tag;
        }

        // Level 3: Visibility & Geometry
        function isElementVisible(el) {
            const rect = el.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return false;
            try {
                const style = window.getComputedStyle(el);
                if (style.display === 'none') return false;
                if (style.visibility === 'hidden' || style.visibility === 'collapse') return false;
                if (parseFloat(style.opacity || '1') === 0) return false;
            } catch (e) {}
            return true;
        }

        // Level 4 & 5: Deep DOM Collector (Shadow DOM + Frames recursion)
        function collectInteractiveCandidates(rootNode, candidateList, depth = 0) {
            if (depth > 6 || !rootNode) return;

            const selectors = [
                'input:not([type="hidden"])',
                'textarea',
                'select',
                'button',
                'a[href]',
                '[role="button"]',
                '[role="link"]',
                '[role="searchbox"]',
                '[role="textbox"]',
                '[role="combobox"]',
                '[role="tab"]',
                '[role="menuitem"]',
                '[role="checkbox"]',
                '[role="radio"]',
                '[tabindex="0"]',
                '[contenteditable="true"]'
            ].join(', ');

            try {
                const matched = rootNode.querySelectorAll ? Array.from(rootNode.querySelectorAll(selectors)) : [];
                for (const el of matched) {
                    candidateList.push(el);
                }
            } catch (e) {}

            try {
                const allElements = rootNode.querySelectorAll ? Array.from(rootNode.querySelectorAll('*')) : [];
                for (const el of allElements) {
                    if (el.shadowRoot) {
                        collectInteractiveCandidates(el.shadowRoot, candidateList, depth + 1);
                    }
                    if (el.tagName && el.tagName.toLowerCase() === 'iframe') {
                        try {
                            if (el.contentDocument && el.contentDocument.body) {
                                collectInteractiveCandidates(el.contentDocument.body, candidateList, depth + 1);
                            }
                        } catch (e) {}
                    }
                }
            } catch (e) {}
        }

        // Extract Headings
        const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6, [role="heading"]'))
            .map(h => (h.innerText || h.textContent || '').trim().replace(/\s+/g, ' '))
            .filter(h => h.length > 1 && h.length < 140)
            .slice(0, 12);

        // Extract Text Blocks
        const mainEl = document.querySelector('main, [role="main"], article, [role="article"]') || document.body;
        const textElements = mainEl ? Array.from(mainEl.querySelectorAll('p, li, blockquote, article, section')) : [];
        let textBlocks = [];
        for (const el of textElements) {
            const txt = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
            if (txt.length > 20 && !textBlocks.some(b => b.startsWith(txt.slice(0, 30)))) {
                textBlocks.push(txt.slice(0, 180));
            }
            if (textBlocks.length >= 8) break;
        }

        if (textBlocks.length === 0 && document.body) {
            const bodyText = (document.body.innerText || '').slice(0, 1500);
            textBlocks = bodyText.split('\n').map(s => s.trim()).filter(s => s.length > 20).slice(0, 6);
        }

        // Collect all interactive elements via deep traversal
        const rawCandidates = [];
        collectInteractiveCandidates(document.body || document.documentElement, rawCandidates);

        // De-duplicate elements
        const seenElements = new Set();
        const interactiveElements = [];
        let index = 0;

        for (const el of rawCandidates) {
            if (seenElements.has(el)) continue;
            seenElements.add(el);

            if (!isElementVisible(el)) continue;

            const elementId = 'el_' + index;
            el.setAttribute('data-matrioshai-id', elementId);

            const role = computeRole(el);
            const accessibleName = computeAccessibleName(el);
            const isPassword = el.type === 'password';
            const val = isPassword ? '[REDACTED]' : (el.value || '');
            const rect = el.getBoundingClientRect();
            const tag = el.tagName ? el.tagName.toLowerCase() : 'div';
            const isEnabled = !el.disabled && el.getAttribute('aria-disabled') !== 'true';
            const isSearchbox = role === 'searchbox' || (role === 'textbox' && (el.name === 'q' || el.type === 'search' || (el.placeholder || '').toLowerCase().includes('search')));

            const finalName = isPassword ? 'Password Input' : (accessibleName || (tag === 'input' ? 'Input field' : tag === 'button' ? 'Button' : 'Interactive Element'));

            interactiveElements.push({
                element_id: elementId,
                tag,
                role,
                name: finalName,
                aria_label: el.getAttribute('aria-label') || undefined,
                title: el.title || undefined,
                href: (el.getAttribute('href') || el.href || '').slice(0, 200) || undefined,
                input_type: el.type || undefined,
                placeholder: el.placeholder || undefined,
                value: val || undefined,
                disabled: !isEnabled,
                visible: true,
                selector: `[data-matrioshai-id="${elementId}"]`,
                rect: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) },
                sensitive: isPassword,
                accessible_name: finalName,
                enabled: isEnabled,
                is_searchbox: isSearchbox
            });

            index++;
            if (interactiveElements.length >= 60) break;
        }

        const isBlank = currentUrl === 'about:blank' || currentUrl.startsWith('https://matrioshai.local');
        const obsStatus = interactiveElements.length > 0 ? 'OBSERVATION_SUCCESS' : (isBlank ? 'EMPTY_CONFIRMED' : 'OBSERVATION_SUCCESS');

        const payload = {
            url: currentUrl,
            title: currentTitle || 'Webpage',
            headings,
            text_blocks: textBlocks,
            links_count: document.querySelectorAll('a[href]').length,
            forms_count: document.querySelectorAll('form').length,
            tables_count: document.querySelectorAll('table').length,
            interactive_elements: interactiveElements,
            observation_status: obsStatus,
            observation_failed: false
        };

        const tid = window.__MATRIOSHAI_TAB_ID__ || '';
        const payloadStr = JSON.stringify(payload);

        if (window.__TAURI_INTERNALS__ && typeof window.__TAURI_INTERNALS__.invoke === 'function') {
            window.__TAURI_INTERNALS__.invoke('receive_page_extraction', { tabId: tid, data: payloadStr }).catch(() => {});
        } else if (window.__TAURI__ && window.__TAURI__.core && typeof window.__TAURI__.core.invoke === 'function') {
            window.__TAURI__.core.invoke('receive_page_extraction', { tabId: tid, data: payloadStr }).catch(() => {});
        }

        // Phase 15: title-channel delivery. WKWebView's evaluateJavaScript
        // completion queue is starved by the idle event loop, but document.title
        // changes are observed via KVO and reach the native side reliably.
        // Deliver the payload in chunks matching __MATRIOSHAI_CHUNK__ handling.
        try {
            if (!window.__MATRIOSHAI_TITLE_XFER_BUSY__) {
                const CHUNK = 1200;
                if (payloadStr.length <= CHUNK) {
                    const orig = document.title;
                    document.title = '__MATRIOSHAI_EXTRACTION__:' + tid + ':' + payloadStr;
                    setTimeout(() => { try { document.title = orig; } catch (e) {} }, 300);
                } else {
                    window.__MATRIOSHAI_TITLE_XFER_BUSY__ = true;
                    const nonce = Math.random().toString(36).slice(2, 8);
                    const total = Math.ceil(payloadStr.length / CHUNK);
                    let idx = 0;
                    const origTitle = document.title;
                    const pushChunk = () => {
                        if (idx >= total) {
                            window.__MATRIOSHAI_TITLE_XFER_BUSY__ = false;
                            setTimeout(() => { try { document.title = origTitle; } catch (e) {} }, 300);
                            return;
                        }
                        document.title = '__MATRIOSHAI_CHUNK__:' + idx + ':' + total + ':' + tid + ':' + payloadStr.substr(idx * CHUNK, CHUNK);
                        idx++;
                        setTimeout(pushChunk, 40);
                    };
                    pushChunk();
                    void nonce;
                }
            }
        } catch (eTitle) {}

        return payloadStr;
    } catch (e) {
        return JSON.stringify({
            error: String(e),
            observation_status: 'OBSERVATION_FAILED',
            observation_failed: true,
            interactive_elements: []
        });
    }
})();
"#;

#[derive(Debug, Deserialize)]
struct ExtractedPayload {
    url: Option<String>,
    title: Option<String>,
    headings: Option<Vec<String>>,
    text_blocks: Option<Vec<String>>,
    links_count: Option<usize>,
    forms_count: Option<usize>,
    tables_count: Option<usize>,
    interactive_elements: Option<Vec<InteractiveElement>>,
    observation_status: Option<String>,
    observation_failed: Option<bool>,
}

fn classify_page_type(url: &str) -> &'static str {
    let u = url.to_lowercase();
    if u.contains("/search") || u.contains("?q=") || u.contains("?s=") {
        "SEARCH"
    } else if u.contains("github.com") || u.contains("/docs") || u.contains("/wiki") || u.contains("/documentation") {
        "DOCUMENTATION"
    } else if u.contains("/cart") || u.contains("/checkout") || u.contains("/product") || u.contains("shop") {
        "E_COMMERCE"
    } else if u.contains("/login") || u.contains("/signin") || u.contains("/sign-in") || u.contains("/auth") {
        "LOGIN"
    } else {
        "ARTICLE"
    }
}

fn create_semantic_model_from_payload(
    tab_id: &str,
    tab_url: &str,
    tab_title: &str,
    gen: u64,
    extracted: ExtractedPayload,
) -> SemanticPageModel {
    let final_url = extracted.url.unwrap_or_else(|| tab_url.to_string());
    let final_title = extracted.title.unwrap_or_else(|| tab_title.to_string());
    let parsed_url = Url::parse(&final_url).unwrap_or_else(|_| Url::parse("https://matrioshai.local").unwrap());
    let origin = format!("{}://{}", parsed_url.scheme(), parsed_url.host_str().unwrap_or(""));
    let page_type = classify_page_type(&final_url);

    let obs_failed = extracted.observation_failed.unwrap_or(false);
    let obs_status = extracted.observation_status.unwrap_or_else(|| {
        if obs_failed { "OBSERVATION_FAILED".to_string() } else { "OBSERVATION_SUCCESS".to_string() }
    });

    SemanticPageModel {
        schema_version: "1.0".to_string(),
        page_id: format!("page_{}_{}", tab_id, gen),
        page_version: gen,
        tab_id: tab_id.to_string(),
        url: final_url,
        origin,
        title: final_title,
        page_type: page_type.to_string(),
        headings: extracted.headings.unwrap_or_default(),
        text_blocks: extracted.text_blocks.unwrap_or_default(),
        interactive_elements: extracted.interactive_elements.unwrap_or_default(),
        forms_count: extracted.forms_count.unwrap_or(0),
        tables_count: extracted.tables_count.unwrap_or(0),
        links_count: extracted.links_count.unwrap_or(0),
        trust_level: "untrusted".to_string(),
        timestamp: current_timestamp(),
        observation_status: obs_status,
        observation_failed: obs_failed,
    }
}

fn handle_title_extraction_event(
    state_handle: &Arc<Mutex<BrowserManagerCore>>,
    tab_id: &str,
    new_title: &str,
) {
    if new_title.starts_with("__MATRIOSHAI_PROBE__:") {
        // Phase 15: minimal DOM probe result delivered through document.title.
        let json = &new_title["__MATRIOSHAI_PROBE__:".len()..];
        println!(
            "[TITLE_CHANNEL/PROBE_RECEIVED] tab_id='{}' json_len={}",
            tab_id,
            json.len()
        );
        if let Ok(mut manager) = state_handle.lock() {
            manager.probe_results.insert(tab_id.to_string(), json.to_string());
        }
    } else if new_title.starts_with("__MATRIOSHAI_EXTRACTION__:") {
        let rest = &new_title["__MATRIOSHAI_EXTRACTION__:".len()..];
        let json_str = if let Some((_nonce, json)) = rest.split_once(':') {
            json
        } else {
            rest
        };
        if let Ok(extracted) = serde_json::from_str::<ExtractedPayload>(json_str) {
            if let Ok(mut manager) = state_handle.lock() {
                let (tab_url, tab_title, gen) = if let Some(tab) = manager.tabs.get(tab_id) {
                    (tab.url.clone(), tab.title.clone(), tab.navigation_generation)
                } else {
                    (String::new(), String::new(), 0)
                };
                let sem_model = create_semantic_model_from_payload(tab_id, &tab_url, &tab_title, gen, extracted);
                println!(
                    "[NATIVE_EXTRACTION_RECEIVED/WRITE] tab_id='{}' elements={} links={} text_blocks={:?}",
                    tab_id, sem_model.interactive_elements.len(), sem_model.links_count, sem_model.text_blocks
                );
                manager.semantic_page_cache.insert(tab_id.to_string(), sem_model);
                println!(
                    "[CACHE_AFTER_INSERT] total_keys={:?}",
                    manager.semantic_page_cache.keys().collect::<Vec<_>>()
                );
            }
        }
    } else if new_title.starts_with("__MATRIOSHAI_CHUNK__:") {
        let raw = &new_title["__MATRIOSHAI_CHUNK__:".len()..];
        let mut parts = raw.splitn(4, ':');
        if let (Some(idx_str), Some(total_str), Some(t_id), Some(chunk_data)) = (parts.next(), parts.next(), parts.next(), parts.next()) {
            if let (Ok(idx), Ok(total)) = (idx_str.parse::<usize>(), total_str.parse::<usize>()) {
                if let Ok(mut manager) = state_handle.lock() {
                    let entry = manager.extraction_chunks.entry(t_id.to_string()).or_insert_with(|| (total, vec![None; total]));
                    if idx < entry.1.len() {
                        entry.1[idx] = Some(chunk_data.to_string());
                    }
                    if entry.1.iter().all(|c| c.is_some()) {
                        let full_json = entry.1.iter().filter_map(|c| c.as_ref()).cloned().collect::<Vec<_>>().join("");
                        manager.extraction_chunks.remove(t_id);
                        if let Ok(extracted) = serde_json::from_str::<ExtractedPayload>(&full_json) {
                            let (tab_url, tab_title, gen) = if let Some(tab) = manager.tabs.get(t_id) {
                                (tab.url.clone(), tab.title.clone(), tab.navigation_generation)
                            } else {
                                (String::new(), String::new(), 0)
                            };
                            let sem_model = create_semantic_model_from_payload(t_id, &tab_url, &tab_title, gen, extracted);
                            println!(
                                "[NATIVE_EXTRACTION_RECEIVED/CHUNK_WRITE] tab_id='{}' elements={} links={} text_blocks={:?}",
                                t_id, sem_model.interactive_elements.len(), sem_model.links_count, sem_model.text_blocks
                            );
                            manager.semantic_page_cache.insert(t_id.to_string(), sem_model);
                        }
                    }
                }
            }
        }
    }
}

#[tauri::command]
pub fn receive_page_extraction(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: String,
    data: String,
) -> Result<(), String> {
    if let Ok(payload) = serde_json::from_str::<ExtractedPayload>(&data) {
        let mut manager = state.0.lock().map_err(|e| e.to_string())?;
        if let Some(tab) = manager.tabs.get_mut(&tab_id) {
            if let Some(ref live_url) = payload.url {
                if !live_url.is_empty() && live_url != "about:blank" && live_url != "https://matrioshai.local" {
                    tab.url = live_url.clone();
                    if let Some(ref live_title) = payload.title {
                        if !live_title.is_empty() {
                            tab.title = live_title.clone();
                        }
                    }
                    let _ = app.emit("browser://url-changed", serde_json::json!({
                        "tab_id": tab_id,
                        "url": live_url,
                        "title": tab.title
                    }));
                }
            }

            let model = create_semantic_model_from_payload(
                &tab.id,
                &tab.url,
                &tab.title,
                tab.navigation_generation,
                payload,
            );

            println!(
                "[RECEIVE_PAGE_EXTRACTION_IPC_WRITE] tab_id='{}' text_blocks={:?}",
                tab_id, model.text_blocks
            );
            manager.semantic_page_cache.insert(tab_id, model);
        }
    }
    Ok(())
}

// Phase 7: Semantic Page Intelligence & Understanding Engine
// (async): see agent_create_task note — this command Condvar-waits up to 3s
// for the WKWebView completion, which can only be delivered while the main
// thread is free.
#[tauri::command(async)]
pub fn browser_get_semantic_page(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: Option<String>,
) -> Result<SemanticPageModel, String> {
    let start_time = std::time::Instant::now();
    let req_timestamp = current_timestamp();

    let (target_id, mut url, mut title, gen) = {
        let manager = state.0.lock().map_err(|e| e.to_string())?;
        let t_id = tab_id.or_else(|| manager.active_tab_id.clone()).ok_or("No active browser tab found")?;
        let tab = manager.tabs.get(&t_id).ok_or(format!("Tab {} not found", t_id))?;
        (t_id, tab.url.clone(), tab.title.clone(), tab.navigation_generation)
    };

    let request_id = format!("{:x}", std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos());

    println!(
        "[OBSERVATION_TRACE/START] request_id='{}' tab_id='{}' url='{}'",
        request_id, target_id, url
    );

    // 1. If webview is available, query live URL and run direct JS extraction.
    //    eval_js_with_result uses Condvar (not spin-poll) so the WebKit
    //    completion handler can fire correctly.
    if let Some(webview) = app.get_webview(&target_id) {
        if let Ok(live_url_obj) = webview.url() {
            let live_str = live_url_obj.as_str().to_string();
            if !live_str.is_empty() && live_str != "about:blank" && !live_str.starts_with("https://matrioshai.local") {
                url = live_str.clone();
                if let Ok(mut manager) = state.0.lock() {
                    if let Some(tab) = manager.tabs.get_mut(&target_id) {
                        tab.url = live_str;
                    }
                }
            }
        }

        let set_tab_id_js = format!("window.__MATRIOSHAI_TAB_ID__ = '{}'", target_id);
        let _ = webview.eval(&set_tab_id_js);

        // Phase 15: fresh-cache short-circuit. Title-channel extraction
        // (on_page_load / EXTRACT_PAGE_CONTENT_SCRIPT) populates the cache
        // asynchronously; skip the synchronous completion-based eval when a
        // recent healthy model already exists.
        if let Ok(manager) = state.0.lock() {
            if let Some(page) = manager.semantic_page_cache.get(&target_id) {
                let age_secs = current_timestamp().saturating_sub(page.timestamp);
                let has_data = !page.text_blocks.is_empty()
                    || !page.headings.is_empty()
                    || !page.interactive_elements.is_empty();
                if has_data && !page.observation_failed && age_secs < 10 {
                    let elapsed_ms = start_time.elapsed().as_millis();
                    println!(
                        "[OBSERVATION_TRACE/CACHE_FRESH] request_id='{}' total_ms={} elements={} links={} age_secs={}",
                        request_id, elapsed_ms, page.interactive_elements.len(), page.links_count, age_secs
                    );
                    return Ok(page.clone());
                }
            }
        }

        let eval_start = std::time::Instant::now();
        let eval_result = eval_js_with_result(&webview, EXTRACT_PAGE_CONTENT_SCRIPT);
        let eval_duration_ms = eval_start.elapsed().as_millis();

        match &eval_result {
            Ok(json_str) => {
                println!(
                    "[OBSERVATION_TRACE/EVAL_OK] request_id='{}' eval_duration_ms={} json_len={}",
                    request_id, eval_duration_ms, json_str.len()
                );
                if let Ok(extracted) = serde_json::from_str::<ExtractedPayload>(json_str) {
                    let sem_model = create_semantic_model_from_payload(&target_id, &url, &title, gen, extracted);
                    let elapsed_ms = start_time.elapsed().as_millis();
                    println!(
                        "[OBSERVATION_TRACE/SUCCESS] request_id='{}' total_ms={} eval_ms={} elements={} links={} text_blocks={} observation_status=OBSERVATION_SUCCESS",
                        request_id, elapsed_ms, eval_duration_ms,
                        sem_model.interactive_elements.len(),
                        sem_model.links_count,
                        sem_model.text_blocks.len()
                    );
                    if let Ok(mut manager) = state.0.lock() {
                        manager.semantic_page_cache.insert(target_id.clone(), sem_model.clone());
                    }
                    return Ok(sem_model);
                } else {
                    eprintln!(
                        "[OBSERVATION_TRACE/PARSE_ERROR] request_id='{}' json_prefix='{}'",
                        request_id, &json_str[..std::cmp::min(200, json_str.len())]
                    );
                }
            }
            Err(e) => {
                eprintln!(
                    "[OBSERVATION_TRACE/EVAL_ERROR] request_id='{}' eval_duration_ms={} error='{}'",
                    request_id, eval_duration_ms, e
                );
            }
        }

        // 2. Check the cache — the EXTRACT_PAGE_CONTENT_SCRIPT also writes via
        //    receive_page_extraction IPC and document.title mutation paths which
        //    may have populated the cache concurrently during eval.
        if let Ok(manager) = state.0.lock() {
            if let Some(page) = manager.semantic_page_cache.get(&target_id) {
                if !page.text_blocks.is_empty() || !page.headings.is_empty() || !page.interactive_elements.is_empty() {
                    let elapsed_ms = start_time.elapsed().as_millis();
                    println!(
                        "[OBSERVATION_TRACE/CACHE_HIT] request_id='{}' total_ms={} elements={} links={} observation_status=OBSERVATION_SUCCESS",
                        request_id, elapsed_ms,
                        page.interactive_elements.len(),
                        page.links_count
                    );
                    return Ok(page.clone());
                }
            }
        }
    } else {
        eprintln!(
            "[OBSERVATION_TRACE/NO_WEBVIEW] request_id='{}' tab_id='{}' — webview not found",
            request_id, target_id
        );
    }

    // 3. Final cache check — handles race where extraction completed after eval timeout
    if let Ok(manager) = state.0.lock() {
        if let Some(page) = manager.semantic_page_cache.get(&target_id) {
            if !page.text_blocks.is_empty() || !page.headings.is_empty() || !page.interactive_elements.is_empty() {
                let elapsed_ms = start_time.elapsed().as_millis();
                println!(
                    "[OBSERVATION_TRACE/LATE_CACHE_HIT] request_id='{}' total_ms={} elements={}",
                    request_id, elapsed_ms, page.interactive_elements.len()
                );
                return Ok(page.clone());
            }
        }
    }

    // 4. Observation failed — return a model explicitly marked as failed.
    //    NEVER return fabricated content silently.
    //    Safety invariant: ai_browser_execute_action MUST reject actions
    //    when observation_failed = true.
    let elapsed_ms = start_time.elapsed().as_millis();
    eprintln!(
        "[OBSERVATION_TRACE/FAILED] request_id='{}' total_ms={}ms url='{}' observation_status=OBSERVATION_TIMEOUT",
        request_id, elapsed_ms, url
    );

    let parsed_url = Url::parse(&url).unwrap_or_else(|_| Url::parse("https://matrioshai.local").unwrap());
    let origin = format!("{}://{}", parsed_url.scheme(), parsed_url.host_str().unwrap_or(""));
    let page_type = classify_page_type(&url);

    let failed_model = SemanticPageModel {
        schema_version: "1.0".to_string(),
        page_id: format!("page_{}_{}", target_id, gen),
        page_version: gen,
        tab_id: target_id.clone(),
        url: url.clone(),
        origin,
        title: title.clone(),
        page_type: page_type.to_string(),
        headings: vec![],
        text_blocks: vec![],
        interactive_elements: vec![],
        forms_count: 0,
        tables_count: 0,
        links_count: 0,
        trust_level: "untrusted".to_string(),
        timestamp: current_timestamp(),
        observation_status: "OBSERVATION_TIMEOUT".to_string(),
        observation_failed: true,
    };

    // Write the failed model into cache so action engine can check observation_failed
    if let Ok(mut manager) = state.0.lock() {
        manager.semantic_page_cache.insert(target_id, failed_model.clone());
    }

    Ok(failed_model)
}

#[tauri::command(async)]
pub fn browser_inspect_page(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: Option<String>,
) -> Result<SemanticPageModel, String> {
    let page = browser_get_semantic_page(app, state, tab_id)?;
    eprintln!(
        "[NATIVE_BROWSER_INSPECT] tab={} url='{}' title='{}' elements={} links={} text_blocks={}",
        page.tab_id, page.url, page.title, page.interactive_elements.len(), page.links_count, page.text_blocks.len()
    );
    Ok(page)
}

// Phase 15: smallest possible live-DOM probe. Result is delivered through the
// document.title channel (__MATRIOSHAI_PROBE__) because WKWebView's
// evaluateJavaScript completion queue is starved by tao's idle event loop.
pub const PROBE_DOM_SCRIPT: &str = r#"
(() => {
    try {
        const orig = document.title;
        const p = {
            url: window.location.href,
            title: orig || '',
            readyState: document.readyState,
            bodyLength: (document.body && typeof document.body.innerText === 'string') ? document.body.innerText.length : -1,
            elements: document.querySelectorAll('*').length,
            links: document.querySelectorAll('a').length,
            buttons: document.querySelectorAll('button').length,
            inputs: document.querySelectorAll('input').length
        };
        document.title = '__MATRIOSHAI_PROBE__:' + JSON.stringify(p);
        setTimeout(() => { try { document.title = orig; } catch (e) {} }, 250);
    } catch (e) {
        try { document.title = '__MATRIOSHAI_PROBE__:' + JSON.stringify({ error: String(e) }); } catch (e2) {}
    }
})();
"#;

#[derive(Debug, Serialize, Deserialize)]
pub struct DomProbePayload {
    pub url: Option<String>,
    #[serde(default)]
    pub title: Option<String>,
    #[serde(rename = "readyState", default)]
    pub ready_state: Option<String>,
    #[serde(rename = "bodyLength", default)]
    pub body_length: Option<i64>,
    #[serde(default)]
    pub elements: Option<usize>,
    #[serde(default)]
    pub links: Option<usize>,
    #[serde(default)]
    pub buttons: Option<usize>,
    #[serde(default)]
    pub inputs: Option<usize>,
    #[serde(default)]
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DebugEvalResult {
    pub title: String,
    pub body_text_len: usize,
    pub elements_count: usize,
    pub custom_js_result: String,
    pub status: String,
    // Phase 15 diagnostics: identity + live DOM probe of the SAME webview
    // browser_get_semantic_page evaluates against.
    pub tab_id: String,
    pub url: String,
    pub ready_state: String,
    pub links_count: usize,
    pub buttons_count: usize,
    pub inputs_count: usize,
}

// (async): polls probe_results for up to 4s — must not occupy the main thread.
#[tauri::command(async)]
pub fn browser_debug_eval(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: Option<String>,
    custom_js: Option<String>,
) -> Result<DebugEvalResult, String> {
    let t_id = {
        let manager = state.0.lock().map_err(|e| e.to_string())?;
        tab_id.or_else(|| manager.active_tab_id.clone()).ok_or("No active browser tab found")?
    };

    if let Some(webview) = app.get_webview(&t_id) {
        // Phase 15 diagnostic probe: fire-and-forget eval + result delivery via
        // the document.title channel. evaluateJavaScript's completion queue is
        // starved by the idle event loop, so synchronous result return is not
        // usable; wry's nil-completion eval executes reliably.
        let live_url = webview.url().map(|u| u.as_str().to_string()).unwrap_or_default();

        // Drop any stale probe entry for this tab before probing.
        if let Ok(mut manager) = state.0.lock() {
            manager.probe_results.remove(&t_id);
        }

        let probe_script = match custom_js {
            Some(ref js) => format!(
                r#"(() => {{ try {{
                    const orig = document.title;
                    const v = String((function(){{ return ({js}); }})());
                    const p = {{
                        url: window.location.href,
                        title: orig || '',
                        readyState: document.readyState,
                        bodyLength: (document.body && typeof document.body.innerText === 'string') ? document.body.innerText.length : -1,
                        elements: document.querySelectorAll('*').length,
                        links: document.querySelectorAll('a').length,
                        buttons: document.querySelectorAll('button').length,
                        inputs: document.querySelectorAll('input').length,
                        custom: v.slice(0, 4000)
                    }};
                    document.title = '__MATRIOSHAI_PROBE__:' + JSON.stringify(p);
                    setTimeout(() => {{ try {{ document.title = orig; }} catch (e) {{}} }}, 250);
                }} catch (e) {{ try {{ document.title = '__MATRIOSHAI_PROBE__:' + JSON.stringify({{ error: String(e) }}); }} catch (e2) {{}} }} }})();"#,
                js = js.as_str()
            ),
            None => PROBE_DOM_SCRIPT.to_string(),
        };
        let _ = webview.eval(&probe_script);

        // Poll for the title-channel probe result (delivered via KVO).
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(4);
        let mut probe_json: Option<String> = None;
        while probe_json.is_none() && std::time::Instant::now() < deadline {
            if let Ok(manager) = state.0.lock() {
                probe_json = manager.probe_results.get(&t_id).cloned();
            }
            if probe_json.is_none() {
                std::thread::sleep(std::time::Duration::from_millis(40));
            }
        }

        let empty = DomProbePayload {
            url: None, title: None, ready_state: None, body_length: None,
            elements: None, links: None, buttons: None, inputs: None, error: None,
        };
        let payload: DomProbePayload = match probe_json {
            Some(ref json) => serde_json::from_str(json).unwrap_or(empty),
            None => {
                eprintln!("[DOM_PROBE] target_id='{}' — probe timed out waiting on title channel", t_id);
                empty
            }
        };

        let g = |v: Option<usize>| v.unwrap_or(0);
        let elem_cnt = g(payload.elements);
        let links_cnt = g(payload.links);
        let buttons_cnt = g(payload.buttons);
        let inputs_cnt = g(payload.inputs);
        let body_len = payload.body_length.unwrap_or(-1).max(0) as usize;
        let title_str = payload.title.clone().unwrap_or_default();
        let ready_str = payload.ready_state.clone().unwrap_or_default();

        println!(
            "[DOM_PROBE] target_id='{}' webview_url='{}' title='{}' ready_state='{}' elements={} links={} buttons={} inputs={} body_len={} error='{:?}'",
            t_id, live_url, title_str, ready_str,
            elem_cnt, links_cnt, buttons_cnt, inputs_cnt, body_len, payload.error
        );

        Ok(DebugEvalResult {
            title: title_str,
            body_text_len: body_len,
            elements_count: elem_cnt,
            custom_js_result: payload.error.map(|e| format!("ERROR: {}", e))
                .or_else(|| serde_json::from_str::<serde_json::Value>(
                    probe_json.as_deref().unwrap_or("{}")).ok()
                    .and_then(|v| v.get("custom").and_then(|c| c.as_str().map(String::from))))
                .unwrap_or_else(|| "N/A".to_string()),
            status: if probe_json.is_some() { "SUCCESS".to_string() } else { "TIMEOUT".to_string() },
            tab_id: t_id.clone(),
            url: live_url,
            ready_state: ready_str,
            links_count: links_cnt,
            buttons_count: buttons_cnt,
            inputs_count: inputs_cnt,
        })
    } else {
        eprintln!("[DOM_PROBE] target_id='{}' — NO WEBVIEW found for this label", t_id);
        Err(format!("Webview tab '{}' not found", t_id))
    }
}

// AI Browser Gateway & Policy API
// (async): delegates to browser_get_semantic_page (3s eval wait).
#[tauri::command(async)]
pub fn ai_browser_get_context(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: Option<String>,
) -> Result<BrowserContextSummary, String> {
    let sem_page = browser_get_semantic_page(app, state, tab_id)?;

    let snippet = if !sem_page.text_blocks.is_empty() {
        sem_page.text_blocks.join("\n")
    } else {
        format!("Webpage document at {}. Title: {}", sem_page.url, sem_page.title)
    };

    Ok(BrowserContextSummary {
        tab_id: sem_page.tab_id,
        url: sem_page.url,
        title: sem_page.title,
        origin: sem_page.origin,
        visible_text_snippet: snippet,
        headings: sem_page.headings,
        interactive_elements_count: sem_page.interactive_elements.len(),
        trust_level: sem_page.trust_level,
    })
}

// (async): runs on the async runtime's thread pool. All state access happens
// in a SCOPED lock at the top; the lock is released BEFORE any webview eval /
// wait so the main-thread title-KVO handler can never starve behind us.
#[tauri::command(async)]
pub fn ai_browser_execute_action(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: String,
    action: String,
    target: Option<String>,
    value: Option<String>,
    user_approved: Option<bool>,
) -> Result<AIActionResult, String> {
    let t_start = std::time::Instant::now();

    println!(
        "[ACTION_REQUEST] action='{}' tab_id='{}' target={:?} value={:?} approved={}",
        action, tab_id, target, value, user_approved.unwrap_or(false)
    );

    // ---- Scoped lock #1: validation, risk gate, and cached-target lookup ----
    let act_upper;
    let risk;
    let needs_approval_gate;
    let cached_target; // (name, href, selector, sensitive) when target resolves in cache

    {
        let manager = state.0.lock().map_err(|e| e.to_string())?;

        if !manager.tabs.contains_key(&tab_id) {
            return Err(format!("Tab {} not found", tab_id));
        }

        let a = action.to_uppercase();

        // SAFETY INVARIANT: OBSERVATION_FAILURE => NO_AUTONOMOUS_ACTION
        let is_write_action = matches!(a.as_str(), "CLICK" | "TYPE" | "NAVIGATE" | "SUBMIT_FORM" | "PAYMENT" | "DELETE_ACCOUNT" | "SELECT" | "PRESS_KEY");
        if is_write_action {
            if let Some(cached) = manager.semantic_page_cache.get(&tab_id) {
                if cached.observation_failed {
                    return Err(format!(
                        "OBSERVATION_FAILURE — tab '{}' observation_status='{}'. \
                         Target element cannot be verified. \
                         Re-observe the page before executing actions.",
                        tab_id, cached.observation_status
                    ));
                }
            }
        }

        let (r, approval_needed) = match a.as_str() {
            "SCROLL" => (ActionRiskLevel::Low, false),
            "CLICK" => (ActionRiskLevel::Medium, true),
            "TYPE" => (ActionRiskLevel::Medium, true),
            "NAVIGATE" => (ActionRiskLevel::Medium, true),
            "SUBMIT_FORM" => (ActionRiskLevel::High, true),
            "PAYMENT" | "DELETE_ACCOUNT" => (ActionRiskLevel::Critical, true),
            _ => (ActionRiskLevel::ReadOnly, false),
        };
        risk = r;
        needs_approval_gate = approval_needed;

        cached_target = if let Some(ref el_id) = target {
            manager.semantic_page_cache.get(&tab_id)
                .and_then(|c| c.interactive_elements.iter().find(|e| &e.element_id == el_id))
                .map(|e| (e.name.clone(), e.href.clone().unwrap_or_default(), e.selector.clone(), e.sensitive))
        } else {
            None
        };

        if needs_approval_gate && !user_approved.unwrap_or(false) {
            let desc = if let Some(ref el_id) = target {
                manager.semantic_page_cache.get(&tab_id)
                    .and_then(|c| c.interactive_elements.iter().find(|e| &e.element_id == el_id))
                    .map(|e| format!("{} '{}' ({})", e.role, e.name, el_id))
                    .unwrap_or_else(|| el_id.clone())
            } else {
                a.clone()
            };
            drop(manager);
            return Ok(AIActionResult {
                success: false,
                action: a,
                tab_id,
                risk_level: risk,
                approval_required: true,
                message: format!("User approval required to {} on {}", action, desc),
                data: Some(serde_json::json!({
                    "target": target,
                    "value": value,
                    "description": desc
                })),
            });
        }

        act_upper = a;
    }
    // ---- Lock RELEASED — no state access below this line ----

    let webview = match app.get_webview(&tab_id) {
        Some(wv) => wv,
        None => {
            println!("[ACTION_DISPATCH] FAILED — no webview for tab '{}'", tab_id);
            return Err(format!("Webview tab '{}' not found", tab_id));
        }
    };

    let url_before = webview.url().map(|u| u.as_str().to_string()).unwrap_or_default();
    println!(
        "[ACTION_TARGET] element_id={:?} cached_text='{}' cached_href='{}' selector='{}' sensitive={} url_at_execution='{}'",
        target,
        cached_target.as_ref().map(|c| c.0.as_str()).unwrap_or(""),
        cached_target.as_ref().map(|c| c.1.as_str()).unwrap_or(""),
        cached_target.as_ref().map(|c| c.2.as_str()).unwrap_or(""),
        cached_target.as_ref().map(|c| c.3).unwrap_or(false),
        url_before
    );

    // Security gate: refuse to type into sensitive (password) fields.
    if act_upper == "TYPE" {
        if let Some((_, _, _, sensitive)) = &cached_target {
            if *sensitive {
                if let Some(el_id) = target.clone() {
                    return Err(format!("Security Block: Element '{}' is marked sensitive.", el_id));
                }
            }
        }
    }

    // Build an instrumented script that RETURNS A VERDICT (JSON string) via
    // eval_js_with_result instead of fire-and-forget eval. Safe here because
    // this command runs on the async runtime pool, not the main thread.
    const CLICK_SCRIPT: &str = r#"(function(){
        try {
            var el = document.querySelector('[data-matrioshai-id="__ELID__"]') || document.getElementById('__ELID__');
            if (!el) { return JSON.stringify({ ok:false, reason:'element_not_found', selector:'[data-matrioshai-id="__ELID__"]' }); }
            el.scrollIntoView({block:'center', behavior:'instant'});
            ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(t){
                try { el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window})); } catch(e){}
            });
            try { if (typeof el.click === 'function') { el.click(); } } catch(e){}
            var href = (el.href || el.getAttribute('href') || '') + '';
            var urlBefore = window.location.href;
            if (href.indexOf('http://')===0 || href.indexOf('https://')===0) {
                setTimeout(function(){ try { if (window.location.href === urlBefore) { window.location.href = href; } } catch(e){} }, 400);
            }
            return JSON.stringify({ ok:true, clicked:true, tag:(el.tagName||'').toLowerCase(),
                text:((el.innerText||el.value||'')+'').slice(0,80), href:href.slice(0,200), urlBefore:urlBefore });
        } catch(e) { return JSON.stringify({ ok:false, reason:String(e) }); }
    })()"#;

    const TYPE_SCRIPT: &str = r#"(function(){
        try {
            var el = document.querySelector('[data-matrioshai-id="__ELID__"]') || document.getElementById('__ELID__');
            if (!el) { return JSON.stringify({ ok:false, reason:'element_not_found' }); }
            el.scrollIntoView({block:'center', behavior:'instant'});
            el.focus();
            el.value = '__TEXT__';
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            return JSON.stringify({ ok:true, typed:true, tag:(el.tagName||'').toLowerCase(),
                valueEcho:((el.value||'')+'').slice(0,120), urlBefore:window.location.href });
        } catch(e) { return JSON.stringify({ ok:false, reason:String(e) }); }
    })()"#;

    let escape_js = |s: &str| s.replace('\\', "\\\\").replace('\'', "\\'").replace('\n', " ").replace('\r', " ");

    let js_result: Option<Result<String, String>> = match act_upper.as_str() {
        "CLICK" => {
            let el_id = match target.clone() {
                Some(id) => id,
                None => return Err("Target element_id required for CLICK action".to_string()),
            };
            println!("[ACTION_JS] CLICK verdict-script dispatched");
            let script = CLICK_SCRIPT.replace("__ELID__", &escape_js(&el_id));
            Some(eval_js_with_result(&webview, &script))
        }
        "TYPE" => {
            let el_id = match target.clone() {
                Some(id) => id,
                None => return Err("Target element_id required for TYPE action".to_string()),
            };
            let text = value.clone().unwrap_or_default();
            println!("[ACTION_JS] TYPE verdict-script dispatched len={}", text.len());
            let script = TYPE_SCRIPT
                .replace("__TEXT__", &escape_js(&text))
                .replace("__ELID__", &escape_js(&el_id));
            Some(eval_js_with_result(&webview, &script))
        }
        "SCROLL" => {
            let dist = if target.as_deref() == Some("up") { -400 } else { 400 };
            println!("[ACTION_JS] SCROLL fire-and-forget dist={}", dist);
            let _ = webview.eval(&format!("window.scrollBy(0, {});", dist));
            None
        }
        "BACK" => { let _ = webview.eval("window.history.back();"); None }
        "FORWARD" => { let _ = webview.eval("window.history.forward();"); None }
        "RELOAD" => { let _ = webview.eval("window.location.reload();"); None }
        "HOVER" | "FOCUS" => {
            if let Some(el_id) = target.clone() {
                let script = format!(
                    "(function(){{ try {{ var el = document.querySelector('[data-matrioshai-id=\"{}\"]') || document.getElementById('{}'); if (el) {{ el.scrollIntoView({{block:'center'}}); el.focus(); el.dispatchEvent(new MouseEvent('mouseover',{{bubbles:true}})); }} }} catch(e){{}} }})()",
                    escape_js(&el_id), escape_js(&el_id)
                );
                let _ = webview.eval(&script);
            }
            None
        }
        "NAVIGATE" => {
            if let Some(new_url) = target.clone() {
                let is_explicit = new_url.starts_with("http://") || new_url.starts_with("https://");
                let source_label = if is_explicit && value.as_deref() == Some("USER_DIRECT") { "USER_EXPLICIT" } else { "LLM_GENERATED" };
                println!("[ACTION_NAVIGATE] requested_url='{}' source={} tab_id='{}'", new_url, source_label, tab_id);
                let active_profile = { state.0.lock().map(|m| m.active_profile_id.clone()).unwrap_or_default() };
                let allowed = { state.0.lock().map(|mut m| m.shield_engine.evaluate_url(&new_url, &active_profile).0).unwrap_or(true) };
                if allowed {
                    if let Ok(parsed) = Url::parse(&new_url) {
                        let _ = webview.navigate(parsed);
                        println!("[ACTION_NAVIGATE] dispatched");
                    } else {
                        println!("[ACTION_NAVIGATE] REJECTED — unparseable URL");
                    }
                } else {
                    println!("[ACTION_NAVIGATE] BLOCKED by shield engine");
                }
            }
            None
        }
        _ => None,
    };

    // Parse the JS verdict (what ACTUALLY happened inside the page).
    let mut js_ok: Option<bool> = None;
    let mut js_detail = String::new();
    if let Some(ref res) = js_result {
        match res {
            Ok(json_str) => {
                match serde_json::from_str::<serde_json::Value>(json_str) {
                    Ok(v) => {
                        js_ok = v.get("ok").and_then(|b| b.as_bool());
                        js_detail = json_str.clone();
                        println!(
                            "[ACTION_JS_RESULT] ok={} duration_ms={} detail='{}'",
                            js_ok.unwrap_or(false), t_start.elapsed().as_millis(),
                            &json_str[..std::cmp::min(300, json_str.len())]
                        );
                    }
                    Err(_) => {
                        println!("[ACTION_JS_RESULT] UNPARSEABLE result='{}'", &json_str[..std::cmp::min(200, json_str.len())]);
                    }
                }
            }
            Err(e) => {
                println!("[ACTION_JS_RESULT] EVAL_ERROR after_ms={} error='{}'", t_start.elapsed().as_millis(), e);
            }
        }
    }

    // Post-action verification: give navigation/DOM mutation a moment, then
    // compare live URL against pre-action state.
    std::thread::sleep(std::time::Duration::from_millis(700));
    let url_after = webview.url().map(|u| u.as_str().to_string()).unwrap_or_default();
    let url_changed = !url_after.is_empty() && url_after != url_before;
    let title_after = String::new(); // Webview has no sync title accessor; URL is the post-state signal here.
    println!(
        "[ACTION_POST_STATE] url_after='{}' title_after='{}' url_changed={} total_ms={}",
        url_after, title_after, url_changed, t_start.elapsed().as_millis()
    );

    // Truthful verification policy:
    //  - Actions with a JS verdict: verified only if the page CONFIRMED the
    //    interaction (element found AND click/type applied).
    //  - Navigation-type actions: verified if URL changed (or for RELOAD/
    //    SCROLL/WAIT where no URL change is expected, dispatch itself).
    let expects_no_url_change = matches!(act_upper.as_str(), "SCROLL" | "TYPE" | "HOVER" | "FOCUS" | "WAIT" | "SUBMIT_FORM" | "PAYMENT" | "DELETE_ACCOUNT" | "SELECT" | "PRESS_KEY");
    let verified = match js_ok {
        Some(ok) => ok,
        None => {
            if act_upper == "NAVIGATE" || act_upper == "BACK" || act_upper == "FORWARD" {
                url_changed
            } else {
                true // SCROLL / RELOAD / WAIT / HOVER: dispatch-only actions
            }
        }
    };

    println!(
        "[ACTION_VERIFY] verified={} js_ok={:?} url_changed={} expects_no_url_change={}",
        verified, js_ok, url_changed, expects_no_url_change
    );

    let message = if verified {
        match js_ok {
            Some(true) => format!(
                "{} confirmed on live DOM — url_changed={} ({}ms)",
                act_upper, url_changed, t_start.elapsed().as_millis()
            ),
            _ => format!(
                "{} dispatched — url_changed={} ({}ms)",
                act_upper, url_changed, t_start.elapsed().as_millis()
            ),
        }
    } else {
        format!(
            "{} NOT verified on live DOM — url_before='{}' url_after='{}' detail={}",
            act_upper,
            url_before,
            url_after,
            if js_detail.is_empty() { "no js verdict".to_string() } else { js_detail.chars().take(160).collect() }
        )
    };

    println!("[ACTION_FINAL] success={} verified={} action='{}'", verified, verified, act_upper);

    Ok(AIActionResult {
        success: verified,
        action: act_upper,
        tab_id,
        risk_level: risk,
        approval_required: false,
        message,
        data: Some(serde_json::json!({
            "target": target,
            "value": value,
            "verified": verified,
            "js_ok": js_ok,
            "url_before": url_before,
            "url_after": url_after,
            "url_changed": url_changed,
            "title_after": title_after
        })),
    })
}

// Shield & Privacy Commands
#[tauri::command]
pub fn browser_get_shield_stats(
    state: State<'_, BrowserManagerState>,
    tab_id: Option<String>,
) -> Result<ShieldStats, String> {
    let manager = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(t_id) = tab_id {
        if let Some(tab) = manager.tabs.get(&t_id) {
            return Ok(tab.shield_stats.clone());
        }
    }
    Ok(manager.shield_engine.total_stats.clone())
}

#[tauri::command]
pub fn browser_set_site_shield(
    state: State<'_, BrowserManagerState>,
    profile_id: String,
    origin: String,
    level: String,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    let s_level = match level.to_uppercase().as_str() {
        "STRICT" => ShieldLevel::STRICT,
        "CUSTOM" => ShieldLevel::CUSTOM,
        "OFF" => ShieldLevel::OFF,
        _ => ShieldLevel::STANDARD,
    };
    let key = format!("{}:{}", profile_id, origin.to_lowercase());
    let setting = SiteShieldSettings {
        origin: origin.clone(),
        profile_id: profile_id.clone(),
        level: s_level.clone(),
        ad_blocking_enabled: s_level != ShieldLevel::OFF,
        tracker_blocking_enabled: s_level != ShieldLevel::OFF,
        malware_protection_enabled: s_level != ShieldLevel::OFF,
    };
    manager.shield_engine.site_settings.insert(key, setting);
    Ok(())
}

// Profile Commands
#[tauri::command]
pub fn browser_create_profile(
    state: State<'_, BrowserManagerState>,
    profile_id: String,
    name: String,
    is_private: bool,
) -> Result<BrowserProfile, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    let now = current_timestamp();
    let p_type = if is_private { ProfileType::PRIVATE } else { ProfileType::REGULAR };

    let profile = BrowserProfile {
        id: profile_id.clone(),
        name,
        profile_type: p_type,
        storage_path: format!("profiles/{}", profile_id),
        created_at: now,
        last_used_at: now,
        is_default: false,
    };

    manager.profiles.insert(profile_id, profile.clone());
    Ok(profile)
}

#[tauri::command]
pub fn browser_get_profiles(
    state: State<'_, BrowserManagerState>,
) -> Result<Vec<BrowserProfile>, String> {
    let manager = state.0.lock().map_err(|e| e.to_string())?;
    Ok(manager.profiles.values().cloned().collect())
}

pub fn resolve_data_directory(
    app: &AppHandle,
    profile: &BrowserProfile,
) -> Result<std::path::PathBuf, String> {
    match profile.profile_type {
        ProfileType::REGULAR => {
            let base = app.path().app_data_dir().map_err(|e| e.to_string())?;
            let dir = base.join(&profile.storage_path);
            std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
            Ok(dir)
        }
        ProfileType::PRIVATE | ProfileType::GUEST => {
            let dir = std::env::temp_dir()
                .join(format!("matrioshai_{}_{}", 
                    if profile.profile_type == ProfileType::PRIVATE { "private" } else { "guest" },
                    profile.id
                ));
            std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
            Ok(dir)
        }
    }
}

#[tauri::command]
pub fn browser_wipe_ephemeral_profile(profile_id: String) -> Result<(), String> {
    let private_dir = std::env::temp_dir().join(format!("matrioshai_private_{}", profile_id));
    if private_dir.exists() {
        let _ = std::fs::remove_dir_all(&private_dir);
    }
    let guest_dir = std::env::temp_dir().join(format!("matrioshai_guest_{}", profile_id));
    if guest_dir.exists() {
        let _ = std::fs::remove_dir_all(&guest_dir);
    }
    Ok(())
}

pub fn sweep_leftover_ephemeral_directories() {
    if let Ok(entries) = std::fs::read_dir(std::env::temp_dir()) {
        for entry in entries.flatten() {
            if let Ok(file_name) = entry.file_name().into_string() {
                if file_name.starts_with("matrioshai_private_") || file_name.starts_with("matrioshai_guest_") {
                    let path = entry.path();
                    if path.is_dir() {
                        let _ = std::fs::remove_dir_all(&path);
                    }
                }
            }
        }
    }
}

#[tauri::command]
pub fn browser_switch_profile(
    state: State<'_, BrowserManagerState>,
    profile_id: String,
) -> Result<BrowserProfile, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    if !manager.profiles.contains_key(&profile_id) {
        return Err(format!("Profile {} does not exist", profile_id));
    }
    manager.active_profile_id = profile_id.clone();
    if let Some(p) = manager.profiles.get_mut(&profile_id) {
        p.last_used_at = current_timestamp();
    }
    Ok(manager.profiles.get(&profile_id).cloned().unwrap())
}

// Permission Commands
#[tauri::command]
pub fn browser_set_permission(
    state: State<'_, BrowserManagerState>,
    profile_id: String,
    origin: String,
    permission: String,
    action: String,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    let act = match action.to_uppercase().as_str() {
        "ALLOW" => PermissionAction::ALLOW,
        "DENY" => PermissionAction::DENY,
        _ => PermissionAction::ASK,
    };
    let key = format!("{}:{}:{}", profile_id, origin, permission.to_uppercase());
    manager.permissions.insert(key, PermissionState {
        profile_id,
        origin,
        permission: permission.to_uppercase(),
        state: act,
        updated_at: current_timestamp(),
    });
    Ok(())
}

#[tauri::command]
pub fn browser_get_permissions(
    state: State<'_, BrowserManagerState>,
    profile_id: String,
) -> Result<Vec<PermissionState>, String> {
    let manager = state.0.lock().map_err(|e| e.to_string())?;
    let prefix = format!("{}:", profile_id);
    let list = manager.permissions
        .iter()
        .filter(|(k, _)| k.starts_with(&prefix))
        .map(|(_, v)| v.clone())
        .collect();
    Ok(list)
}

#[tauri::command]
pub fn browser_clear_site_data(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    profile_id: String,
    _origin: Option<String>,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    let prefix = format!("{}:", profile_id);
    manager.permissions.retain(|k, _| !k.starts_with(&prefix));

    if let Some(ref tab_id) = manager.active_tab_id {
        if let Some(webview) = app.get_webview(tab_id) {
            let _ = webview.eval("try { localStorage.clear(); sessionStorage.clear(); } catch(e){}");
        }
    }
    Ok(())
}

// Tab Commands
#[tauri::command]
pub fn browser_create_tab(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: String,
    url: String,
    bounds: RectBounds,
    activate: bool,
    profile_id: Option<String>,
) -> Result<BrowserTabState, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;

    if manager.tabs.contains_key(&tab_id) {
        return Err(format!("Tab {} already exists", tab_id));
    }

    manager.current_bounds = Some(bounds.clone());
    manager.generation_counter += 1;
    let gen = manager.generation_counter;
    let active_profile = profile_id.unwrap_or_else(|| manager.active_profile_id.clone());

    let (allowed, block_reason) = manager.shield_engine.evaluate_url(&url, &active_profile);
    if !allowed {
        return Err(format!("Navigation blocked by Matrioshai Shield: {:?}", block_reason.unwrap_or("PRIVACY_FILTER")));
    }

    let is_internal = url == "https://matrioshai.local" || url == "about:blank" || url.is_empty();

    let now = current_timestamp();
    let tab = BrowserTabState {
        id: tab_id.clone(),
        webview_id: tab_id.clone(),
        profile_id: active_profile.clone(),
        url: url.clone(),
        title: if is_internal { "New Tab".to_string() } else { url.replace("https://", "").replace("http://", "").split('/').next().unwrap_or("New Tab").to_string() },
        favicon: None,
        loading: false,
        progress: 1.0,
        can_go_back: false,
        can_go_forward: false,
        active: activate,
        visible: activate,
        pinned: false,
        group_id: None,
        zoom_factor: 1.0,
        created_at: now,
        last_active_at: now,
        navigation_generation: gen,
        status: TabStatus::READY,
        shield_stats: ShieldStats {
            ads_blocked: 0,
            trackers_blocked: 0,
            malicious_blocked: 0,
            total_evaluated: 1,
        },
    };

    if !is_internal {
        let parsed_url: Url = url.parse().map_err(|e| format!("Invalid URL: {}", e))?;

        // Find the main window
        let main_window = app.get_window("main")
            .or_else(|| app.windows().into_values().next())
            .ok_or("Main window not found")?;

        let active_profile_obj = manager.profiles.get(&active_profile)
            .cloned()
            .unwrap_or_else(|| BrowserProfile {
                id: active_profile.clone(),
                name: "Profile".to_string(),
                profile_type: if active_profile == "private" { ProfileType::PRIVATE } else { ProfileType::REGULAR },
                storage_path: format!("profiles/{}", active_profile),
                created_at: now,
                last_used_at: now,
                is_default: active_profile == "default",
            });

        let data_dir = resolve_data_directory(&app, &active_profile_obj)?;

        let tab_id_clone = tab_id.clone();
        let tab_id_title = tab_id.clone();
        let app_handle_clone = app.clone();
        let state_handle = state.0.clone();
        let tab_init_script = format!("window.__MATRIOSHAI_TAB_ID__ = '{}';\n{}\n{}", tab_id, CHROME_EXTENSION_POLYFILL, BRAVE_ADBLOCK_AND_YOUTUBE_SCRIPT);
        let webview_builder = tauri::webview::WebviewBuilder::new(
            &tab_id,
            WebviewUrl::External(parsed_url),
        )
        .user_agent(MODERN_USER_AGENT)
        .data_directory(data_dir)
        .on_page_load(move |wv, payload| {
            if payload.event() == tauri::webview::PageLoadEvent::Finished {
                let _ = wv.eval(EXTRACT_PAGE_CONTENT_SCRIPT);
            }
        })
        .on_document_title_changed(move |_wv, new_title| {
            handle_title_extraction_event(&state_handle, &tab_id_title, &new_title);
        })
        .on_navigation(move |url| {
            let u_str = url.as_str().to_string();
            let _ = app_handle_clone.emit("browser://url-changed", serde_json::json!({
                "tab_id": tab_id_clone,
                "url": u_str,
                "title": u_str.replace("https://", "").replace("http://", "").split('/').next().unwrap_or("")
            }));
            true
        })
        .initialization_script(&tab_init_script);

        let webview = main_window.add_child(
            webview_builder,
            tauri::LogicalPosition::new(bounds.x, bounds.y),
            tauri::LogicalSize::new(bounds.width, bounds.height),
        ).map_err(|e| format!("Failed to embed native webview child: {}", e))?;

        // Inject active extension content scripts
        for ext in manager.extension_runtime.extensions.values() {
            if ext.enabled {
                for script in &ext.content_scripts {
                    if let Some(ref js_files) = script.js {
                        for js_file in js_files {
                            let js_path = std::path::Path::new(&ext.path).join(js_file);
                            if let Ok(js_content) = std::fs::read_to_string(js_path) {
                                let _ = webview.eval(&js_content);
                            }
                        }
                    }
                }
            }
        }

        if !activate {
            let _ = webview.hide();
        }
    }

    manager.tabs.insert(tab_id.clone(), tab.clone());
    manager.tab_order.push(tab_id.clone());

    if activate {
        for (id, t) in manager.tabs.iter_mut() {
            if id != &tab_id {
                t.active = false;
                t.visible = false;
                if let Some(w) = app.get_webview(id) {
                    let _ = w.hide();
                }
            }
        }
        manager.active_tab_id = Some(tab_id.clone());
    }

    Ok(tab)
}

#[tauri::command]
pub fn browser_activate_tab(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: String,
) -> Result<BrowserTabState, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;

    if !manager.tabs.contains_key(&tab_id) {
        return Err(format!("Tab {} not found", tab_id));
    }

    let bounds_opt = manager.current_bounds.clone();

    for (id, tab) in manager.tabs.iter_mut() {
        if id == &tab_id {
            tab.active = true;
            tab.visible = true;
            tab.last_active_at = current_timestamp();
            if let Some(w) = app.get_webview(id) {
                if let Some(ref b) = bounds_opt {
                    let _ = w.set_position(tauri::LogicalPosition::new(b.x, b.y));
                    let _ = w.set_size(tauri::LogicalSize::new(b.width, b.height));
                }
                let _ = w.show();
            }
        } else {
            tab.active = false;
            tab.visible = false;
            if let Some(w) = app.get_webview(id) {
                let _ = w.hide();
            }
        }
    }

    manager.active_tab_id = Some(tab_id.clone());
    let active_tab = manager.tabs.get(&tab_id).cloned().unwrap();
    Ok(active_tab)
}

#[tauri::command]
pub fn browser_close_tab(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: String,
) -> Result<Option<String>, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;

    let closed_info = manager.tabs.get(&tab_id).map(|tab| (tab.url.clone(), tab.title.clone()));
    if let Some((url, title)) = closed_info {
        if url != "https://matrioshai.local" && url != "about:blank" {
            manager.recently_closed_tabs.push(ClosedTabHistoryItem {
                url,
                title,
                closed_at: current_timestamp(),
            });
            if manager.recently_closed_tabs.len() > 30 {
                manager.recently_closed_tabs.remove(0);
            }
        }
    }

    let closed_tab_profile = manager.tabs.get(&tab_id).map(|t| t.profile_id.clone());

    if let Some(w) = app.get_webview(&tab_id) {
        let _ = w.close();
    }

    manager.tabs.remove(&tab_id);
    manager.tab_order.retain(|id| id != &tab_id);

    // If this was a PRIVATE or GUEST profile and no more tabs exist for it, wipe temp folder
    if let Some(ref prof_id) = closed_tab_profile {
        let remaining_tabs_in_profile = manager.tabs.values().any(|t| &t.profile_id == prof_id);
        if !remaining_tabs_in_profile {
            let is_ephemeral = manager.profiles.get(prof_id).map(|p| p.profile_type == ProfileType::PRIVATE || p.profile_type == ProfileType::GUEST).unwrap_or(prof_id == "private" || prof_id == "guest");
            if is_ephemeral {
                let _ = browser_wipe_ephemeral_profile(prof_id.clone());
            }
        }
    }

    let mut next_active: Option<String> = None;
    if manager.active_tab_id.as_deref() == Some(&tab_id) {
        if let Some(first_remaining) = manager.tab_order.last().cloned() {
            manager.active_tab_id = Some(first_remaining.clone());
            if let Some(tab) = manager.tabs.get_mut(&first_remaining) {
                tab.active = true;
                tab.visible = true;
                if let Some(w) = app.get_webview(&first_remaining) {
                    let _ = w.show();
                }
            }
            next_active = Some(first_remaining);
        } else {
            manager.active_tab_id = None;
        }
    }

    Ok(next_active)
}

#[tauri::command]
pub fn browser_navigate(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: String,
    url: String,
    bounds: Option<RectBounds>,
) -> Result<u64, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    let active_profile = manager.active_profile_id.clone();

    let (allowed, block_reason) = manager.shield_engine.evaluate_url(&url, &active_profile);
    if !allowed {
        return Err(format!("Blocked by Matrioshai Privacy Shield: {:?}", block_reason.unwrap_or("PRIVACY_FILTER")));
    }

    let parsed: Url = url.parse().map_err(|e| format!("Invalid URL: {}", e))?;

    manager.generation_counter += 1;
    let new_gen = manager.generation_counter;

    // If fresh bounds passed from frontend, update stored bounds
    if let Some(ref b) = bounds {
        manager.current_bounds = Some(b.clone());
    }

    if let Some(tab) = manager.tabs.get_mut(&tab_id) {
        tab.url = url.clone();
        tab.title = url.replace("https://", "").replace("http://", "").split('/').next().unwrap_or("").to_string();
        tab.loading = true;
        tab.navigation_generation = new_gen;
        tab.status = TabStatus::NAVIGATING;
    }

    if let Some(webview) = app.get_webview(&tab_id) {
        let _ = webview.show();
        let _ = webview.eval(CHROME_EXTENSION_POLYFILL);
        let _ = webview.eval(BRAVE_ADBLOCK_AND_YOUTUBE_SCRIPT);
        // Inject active extension content scripts
        for ext in manager.extension_runtime.extensions.values() {
            if ext.enabled {
                for script in &ext.content_scripts {
                    if let Some(ref js_files) = script.js {
                        for js_file in js_files {
                            let js_path = std::path::Path::new(&ext.path).join(js_file);
                            if let Ok(js_content) = std::fs::read_to_string(js_path) {
                                let _ = webview.eval(&js_content);
                            }
                        }
                    }
                }
            }
        }
        webview.navigate(parsed).map_err(|e| e.to_string())?;
    } else {
        // Tab was on internal page and now navigating to external URL — create child webview
        let nav_bounds = bounds
            .or_else(|| manager.current_bounds.clone())
            .ok_or_else(|| "No bounds available for webview creation — frontend must supply bounds".to_string())?;
        let main_window = app.get_window("main")
            .or_else(|| app.windows().into_values().next())
            .ok_or("Main window not found")?;

        let active_profile_obj = manager.profiles.get(&active_profile)
            .cloned()
            .unwrap_or_else(|| BrowserProfile {
                id: active_profile.clone(),
                name: "Profile".to_string(),
                profile_type: if active_profile == "private" { ProfileType::PRIVATE } else { ProfileType::REGULAR },
                storage_path: format!("profiles/{}", active_profile),
                created_at: current_timestamp(),
                last_used_at: current_timestamp(),
                is_default: active_profile == "default",
            });

        let data_dir = resolve_data_directory(&app, &active_profile_obj)?;

        let tab_id_clone = tab_id.clone();
        let tab_id_title = tab_id.clone();
        let app_handle_clone = app.clone();
        let state_handle = state.0.clone();
        let tab_init_script = format!("window.__MATRIOSHAI_TAB_ID__ = '{}';\n{}\n{}", tab_id, CHROME_EXTENSION_POLYFILL, BRAVE_ADBLOCK_AND_YOUTUBE_SCRIPT);
        let webview_builder = tauri::webview::WebviewBuilder::new(&tab_id, WebviewUrl::External(parsed))
            .user_agent(MODERN_USER_AGENT)
            .data_directory(data_dir)
            .on_page_load(move |wv, payload| {
                if payload.event() == tauri::webview::PageLoadEvent::Finished {
                    let _ = wv.eval(EXTRACT_PAGE_CONTENT_SCRIPT);
                }
            })
            .on_document_title_changed(move |_wv, new_title| {
                handle_title_extraction_event(&state_handle, &tab_id_title, &new_title);
            })
            .on_navigation(move |url| {
                let u_str = url.as_str().to_string();
                let _ = app_handle_clone.emit("browser://url-changed", serde_json::json!({
                    "tab_id": tab_id_clone,
                    "url": u_str,
                    "title": u_str.replace("https://", "").replace("http://", "").split('/').next().unwrap_or("")
                }));
                true
            })
            .initialization_script(&tab_init_script);
        let webview = main_window.add_child(
            webview_builder,
            tauri::LogicalPosition::new(nav_bounds.x, nav_bounds.y),
            tauri::LogicalSize::new(nav_bounds.width, nav_bounds.height),
        ).map_err(|e| format!("Failed to embed: {}", e))?;

        let _ = webview.show();
    }

    let _ = app.emit("browser://navigation-started", BrowserNavigationEvent {
        event_type: "navigation-started".to_string(),
        tab_id,
        navigation_generation: new_gen,
        url,
        title: "Loading...".to_string(),
        loading: true,
        can_go_back: false,
        can_go_forward: false,
    });

    Ok(new_gen)
}

#[tauri::command]
pub fn browser_stop_loading(app: AppHandle, tab_id: String) -> Result<(), String> {
    if let Some(webview) = app.get_webview(&tab_id) {
        let _ = webview.eval("window.stop()");
    }
    Ok(())
}

#[tauri::command]
pub fn get_content_view_offset(window: tauri::Window) -> Result<f64, String> {
    let outer = window.outer_size().map_err(|e| e.to_string())?;
    let inner = window.inner_size().map_err(|e| e.to_string())?;
    let scale = window.scale_factor().unwrap_or(1.0);
    Ok((outer.height as f64 - inner.height as f64) / scale)
}

#[tauri::command]
pub fn browser_update_bounds(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: String,
    bounds: RectBounds,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    manager.current_bounds = Some(bounds.clone());

    if let Some(webview) = app.get_webview(&tab_id) {
        let _ = webview.set_position(tauri::LogicalPosition::new(bounds.x, bounds.y));
        let _ = webview.set_size(tauri::LogicalSize::new(bounds.width, bounds.height));
        apply_rounded_corners(&webview, 14.0);
    }
    Ok(())
}

#[tauri::command]
pub fn browser_hide_all_webviews(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    for (id, tab) in manager.tabs.iter_mut() {
        tab.visible = false;
        if let Some(w) = app.get_webview(id) {
            let _ = w.hide();
        }
    }
    Ok(())
}

#[tauri::command]
pub fn browser_reorder_tabs(
    state: State<'_, BrowserManagerState>,
    new_order: Vec<String>,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    manager.tab_order = new_order;
    Ok(())
}

#[tauri::command]
pub fn browser_duplicate_tab(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    source_tab_id: String,
    new_tab_id: String,
) -> Result<BrowserTabState, String> {
    let (url, bounds) = {
        let manager = state.0.lock().map_err(|e| e.to_string())?;
        let source_tab = manager.tabs.get(&source_tab_id).ok_or("Source tab not found")?;
        let bounds = manager.current_bounds.clone().unwrap_or(RectBounds {
            x: 0.0,
            y: 0.0,
            width: 800.0,
            height: 600.0,
        });
        (source_tab.url.clone(), bounds)
    };

    browser_create_tab(app, state, new_tab_id, url, bounds, true, None)
}

#[tauri::command]
pub fn browser_go_back(app: AppHandle, tab_id: String) -> Result<(), String> {
    if let Some(webview) = app.get_webview(&tab_id) {
        let _ = webview.eval("window.history.back()");
    }
    Ok(())
}

#[tauri::command]
pub fn browser_go_forward(app: AppHandle, tab_id: String) -> Result<(), String> {
    if let Some(webview) = app.get_webview(&tab_id) {
        let _ = webview.eval("window.history.forward()");
    }
    Ok(())
}

#[tauri::command]
pub fn browser_reload(app: AppHandle, tab_id: String) -> Result<(), String> {
    if let Some(webview) = app.get_webview(&tab_id) {
        let _ = webview.eval("window.location.reload()");
    }
    Ok(())
}

#[tauri::command]
pub fn browser_hard_reload(app: AppHandle, tab_id: String) -> Result<(), String> {
    if let Some(webview) = app.get_webview(&tab_id) {
        let _ = webview.eval("window.location.reload(true)");
    }
    Ok(())
}

#[tauri::command]
pub fn browser_set_tab_pinned(
    state: State<'_, BrowserManagerState>,
    tab_id: String,
    pinned: bool,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(tab) = manager.tabs.get_mut(&tab_id) {
        tab.pinned = pinned;
    }
    Ok(())
}

#[tauri::command]
pub fn browser_set_tab_group(
    state: State<'_, BrowserManagerState>,
    tab_id: String,
    group_id: Option<String>,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(tab) = manager.tabs.get_mut(&tab_id) {
        tab.group_id = group_id;
    }
    Ok(())
}

#[tauri::command]
pub fn browser_upsert_tab_group(
    state: State<'_, BrowserManagerState>,
    group: TabGroup,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    manager.tab_groups.insert(group.id.clone(), group);
    Ok(())
}

#[tauri::command]
pub fn browser_get_tab_groups(
    state: State<'_, BrowserManagerState>,
) -> Result<Vec<TabGroup>, String> {
    let manager = state.0.lock().map_err(|e| e.to_string())?;
    Ok(manager.tab_groups.values().cloned().collect())
}

#[tauri::command]
pub fn browser_reopen_last_closed_tab(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    new_tab_id: String,
) -> Result<Option<BrowserTabState>, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(closed_item) = manager.recently_closed_tabs.pop() {
        let bounds = manager.current_bounds.clone().unwrap_or(RectBounds {
            x: 0.0,
            y: 0.0,
            width: 800.0,
            height: 600.0,
        });
        drop(manager);
        let tab = browser_create_tab(app, state, new_tab_id, closed_item.url, bounds, true, None)?;
        Ok(Some(tab))
    } else {
        Ok(None)
    }
}

#[tauri::command]
pub fn browser_set_zoom(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    tab_id: String,
    zoom_factor: f64,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(tab) = manager.tabs.get_mut(&tab_id) {
        tab.zoom_factor = zoom_factor;
    }
    if let Some(webview) = app.get_webview(&tab_id) {
        let js = format!("document.body.style.zoom = '{}'", zoom_factor);
        let _ = webview.eval(&js);
    }
    Ok(())
}

#[tauri::command]
pub fn browser_print(app: AppHandle, tab_id: String) -> Result<(), String> {
    if let Some(webview) = app.get_webview(&tab_id) {
        let _ = webview.eval("window.print()");
    }
    Ok(())
}

#[tauri::command]
pub fn browser_get_all_tabs(
    state: State<'_, BrowserManagerState>,
) -> Result<Vec<BrowserTabState>, String> {
    let manager = state.0.lock().map_err(|e| e.to_string())?;
    let mut ordered: Vec<BrowserTabState> = Vec::new();
    for id in &manager.tab_order {
        if let Some(t) = manager.tabs.get(id) {
            ordered.push(t.clone());
        }
    }
    Ok(ordered)
}

#[tauri::command]
pub fn browser_get_active_tab(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
) -> Result<Option<BrowserTabState>, String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(ref active_id) = manager.active_tab_id.clone() {
        // Read the LIVE URL directly from the native WebKit webview — no JS injection needed
        if let Some(webview) = app.get_webview(active_id) {
            if let Ok(current_url) = webview.url() {
                let url_str = current_url.to_string();
                if !url_str.is_empty() && url_str != "about:blank" && url_str != "https://matrioshai.local/" {
                    let old_url = manager.tabs.get(active_id).map(|t| t.url.clone()).unwrap_or_default();
                    if url_str != old_url {
                        // URL changed (SPA pushState or full navigation) — update state and notify frontend
                        if let Some(tab) = manager.tabs.get_mut(active_id) {
                            tab.url = url_str.clone();
                            tab.loading = false;
                        }
                        let _ = app.emit("browser://url-changed", serde_json::json!({
                            "tab_id": active_id,
                            "url": url_str,
                            "title": ""
                        }));
                    }
                }
            }
        }
        Ok(manager.tabs.get(active_id).cloned())
    } else {
        Ok(None)
    }
}

#[tauri::command]
pub fn browser_get_tab_live_url(
    app: AppHandle,
    tab_id: String,
) -> Result<String, String> {
    if let Some(webview) = app.get_webview(&tab_id) {
        match webview.url() {
            Ok(url) => Ok(url.to_string()),
            Err(e) => Err(e.to_string()),
        }
    } else {
        Err(format!("Webview not found: {}", tab_id))
    }
}

// Phase 9: Chrome WebExtension Management Commands
#[tauri::command]
pub fn browser_load_extension(
    app: AppHandle,
    state: State<'_, BrowserManagerState>,
    extension_path: String,
) -> Result<InstalledExtension, String> {
    let manifest_path = std::path::Path::new(&extension_path).join("manifest.json");
    if !manifest_path.exists() {
        return Err(format!("manifest.json not found at {}", extension_path));
    }

    let manifest_str = std::fs::read_to_string(&manifest_path)
        .map_err(|e| format!("Failed to read manifest.json: {}", e))?;

    let manifest: ExtensionManifest = serde_json::from_str(&manifest_str)
        .map_err(|e| format!("Failed to parse manifest.json: {}", e))?;

    let mut ext_name = manifest.name.clone();
    let mut ext_desc = manifest.description.clone().unwrap_or_default();

    // Resolve Chrome i18n locale __MSG_...__ messages
    let locales_dir = std::path::Path::new(&extension_path).join("_locales");
    if locales_dir.exists() {
        let locale_candidates = ["en", "en_US", "en_GB"];
        let mut locale_file = None;
        for loc in &locale_candidates {
            let cand = locales_dir.join(loc).join("messages.json");
            if cand.exists() {
                locale_file = Some(cand);
                break;
            }
        }
        if locale_file.is_none() {
            if let Ok(entries) = std::fs::read_dir(&locales_dir) {
                for entry in entries.flatten() {
                    let cand = entry.path().join("messages.json");
                    if cand.exists() {
                        locale_file = Some(cand);
                        break;
                    }
                }
            }
        }

        if let Some(lf_path) = locale_file {
            if let Ok(content) = std::fs::read_to_string(lf_path) {
                if let Ok(loc_json) = serde_json::from_str::<serde_json::Value>(&content) {
                    if ext_name.starts_with("__MSG_") && ext_name.ends_with("__") && ext_name.len() > 8 {
                        let key = &ext_name[6..ext_name.len() - 2];
                        if let Some(msg) = loc_json.get(key).and_then(|v| v.get("message")).and_then(|m| m.as_str()) {
                            ext_name = msg.to_string();
                        }
                    }
                    if ext_desc.starts_with("__MSG_") && ext_desc.ends_with("__") && ext_desc.len() > 8 {
                        let key = &ext_desc[6..ext_desc.len() - 2];
                        if let Some(msg) = loc_json.get(key).and_then(|v| v.get("message")).and_then(|m| m.as_str()) {
                            ext_desc = msg.to_string();
                        }
                    }
                }
            }
        }
    }

    let ext_id = format!("ext_{}", ext_name.to_lowercase().replace(' ', "_"));
    let now = current_timestamp();

    let popup_file = manifest.action.as_ref().and_then(|a| a.default_popup.clone())
        .or_else(|| manifest.browser_action.as_ref().and_then(|a| a.default_popup.clone()));

    let popup_path = popup_file.map(|pf| {
        std::path::Path::new(&extension_path).join(pf).to_string_lossy().to_string()
    });

    let installed = InstalledExtension {
        id: ext_id.clone(),
        name: ext_name,
        version: manifest.version,
        description: ext_desc,
        icon_url: None,
        enabled: true,
        path: extension_path,
        popup_path,
        content_scripts: manifest.content_scripts.unwrap_or_default(),
        permissions: manifest.permissions.unwrap_or_default(),
        installed_at: now,
    };

    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    manager.extension_runtime.extensions.insert(ext_id, installed.clone());

    Ok(installed)
}

#[tauri::command]
pub fn browser_get_extensions(
    state: State<'_, BrowserManagerState>,
) -> Result<Vec<InstalledExtension>, String> {
    let manager = state.0.lock().map_err(|e| e.to_string())?;
    Ok(manager.extension_runtime.extensions.values().cloned().collect())
}

#[tauri::command]
pub fn browser_toggle_extension(
    state: State<'_, BrowserManagerState>,
    extension_id: String,
    enabled: bool,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(ext) = manager.extension_runtime.extensions.get_mut(&extension_id) {
        ext.enabled = enabled;
        Ok(())
    } else {
        Err("Extension not found".to_string())
    }
}

#[tauri::command]
pub fn browser_remove_extension(
    state: State<'_, BrowserManagerState>,
    extension_id: String,
) -> Result<(), String> {
    let mut manager = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(ext) = manager.extension_runtime.extensions.remove(&extension_id) {
        if ext.path.contains(".matrioshai/extensions") {
            let _ = std::fs::remove_dir_all(&ext.path);
        }
    }
    Ok(())
}
