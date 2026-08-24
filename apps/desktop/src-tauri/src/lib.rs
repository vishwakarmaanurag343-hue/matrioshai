#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::{Arc, Mutex};
use browser_manager::{BrowserManagerCore, BrowserManagerState};

pub mod browser_manager;

pub fn run() {
    let browser_state = BrowserManagerState(Arc::new(Mutex::new(BrowserManagerCore::new())));

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(browser_state)
        .invoke_handler(tauri::generate_handler![
            browser_manager::browser_create_tab,
            browser_manager::browser_activate_tab,
            browser_manager::browser_close_tab,
            browser_manager::browser_navigate,
            browser_manager::browser_update_bounds,
            browser_manager::browser_reorder_tabs,
            browser_manager::browser_duplicate_tab,
            browser_manager::browser_go_back,
            browser_manager::browser_go_forward,
            browser_manager::browser_reload,
            browser_manager::browser_hard_reload,
            browser_manager::browser_set_tab_pinned,
            browser_manager::browser_set_tab_group,
            browser_manager::browser_upsert_tab_group,
            browser_manager::browser_get_tab_groups,
            browser_manager::browser_reopen_last_closed_tab,
            browser_manager::browser_set_zoom,
            browser_manager::browser_print,
            browser_manager::browser_stop_loading,
            browser_manager::browser_get_all_tabs,
            browser_manager::browser_get_active_tab,
            browser_manager::browser_create_profile,
            browser_manager::browser_get_profiles,
            browser_manager::browser_switch_profile,
            browser_manager::browser_wipe_ephemeral_profile,
            browser_manager::browser_set_permission,
            browser_manager::browser_get_permissions,
            browser_manager::browser_clear_site_data,
            browser_manager::browser_get_shield_stats,
            browser_manager::browser_set_site_shield,
            browser_manager::get_content_view_offset,
            browser_manager::browser_hide_all_webviews,
            browser_manager::ai_browser_get_context,
            browser_manager::ai_browser_execute_action,
            browser_manager::browser_get_semantic_page,
            browser_manager::browser_inspect_page,
            browser_manager::browser_debug_eval,
            browser_manager::receive_page_extraction,
            browser_manager::agent_create_task,
            browser_manager::agent_execute_next_step,
            browser_manager::agent_cancel_task,
            browser_manager::browser_load_extension,
            browser_manager::browser_get_extensions,
            browser_manager::browser_toggle_extension,
            browser_manager::browser_remove_extension,
            browser_manager::browser_get_tab_live_url,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    // Phase 15 root-cause fix: WKWebView delivers JS-eval completions and
    // document.title KVO updates onto the Cocoa main thread, but tao's idle
    // event loop does not service those queues until some UI event arrives —
    // so results queued up and drained only seconds later (or never, before
    // our deadlines expired). The event-proxy wakeup is processed promptly
    // (proven by with_webview closure dispatch), so a lightweight background
    // heartbeat keeps the loop cycling and WebKit's queues draining.
    {
        let handle = app.handle().clone();
        std::thread::spawn(move || loop {
            std::thread::sleep(std::time::Duration::from_millis(150));
            let _ = handle.run_on_main_thread(|| {});
        });
    }

    app.run(|_app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            browser_manager::sweep_leftover_ephemeral_directories();
        }
    });
}
