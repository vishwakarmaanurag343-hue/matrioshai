/**
 * MATRIOSHAI Browser Event Engine (Phase 3)
 *
 * Listens to native Chrome browser lifecycle events (tabs, windows, navigation)
 * and streams them in real time over the WebSocket Bridge to the MATRIOSHAI backend.
 */

import { createScopedLogger } from '../shared/logger';
import { BridgeAction, type TabState, type TabStatus } from '../shared/types';
import { browserBridge } from './browser-bridge';
import { browserController } from './browser-controller';

const logger = createScopedLogger('EVENT_ENGINE');

export class BrowserEventEngine {
  private initialized = false;

  public initialize(): void {
    if (this.initialized) return;
    if (typeof chrome === 'undefined' || !chrome.tabs) {
      logger.debug('Chrome tabs API not available, skipping event engine setup');
      return;
    }

    this.setupTabListeners();
    this.setupWindowListeners();
    this.initialized = true;
    logger.info('Browser Event Engine initialized successfully');
  }

  private mapTabState(tab: chrome.tabs.Tab): TabState {
    let status: TabStatus = 'UNKNOWN';
    if (tab.status === 'loading') {
      status = 'LOADING';
    } else if (tab.status === 'complete') {
      status = 'READY';
    }

    return {
      tab_id: tab.id ?? -1,
      window_id: tab.windowId,
      index: tab.index,
      active: tab.active ?? false,
      url: tab.url ?? '',
      title: tab.title ?? '',
      status,
      favIconUrl: tab.favIconUrl ?? null,
      last_updated: new Date().toISOString()
    };
  }

  private setupTabListeners(): void {
    // 1. Tab Created
    chrome.tabs.onCreated.addListener((tab) => {
      logger.debug(`[EVENT] tab.created tab_id=${tab.id} window_id=${tab.windowId}`);
      const tabState = this.mapTabState(tab);
      browserBridge.sendEvent(BridgeAction.TAB_CREATED, {
        tab: tabState,
        browser_id: browserController.getBrowserId()
      });
      browserController.syncStateSnapshot().catch(() => {});
    });

    // 2. Tab Updated (URL, Title, Loading state)
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
      logger.debug(`[EVENT] tab.updated tab_id=${tabId} status=${changeInfo.status} url=${changeInfo.url}`);
      const tabState = this.mapTabState(tab);

      // Emit tab.updated
      browserBridge.sendEvent(BridgeAction.TAB_UPDATED, {
        tab: tabState,
        change_info: changeInfo,
        browser_id: browserController.getBrowserId()
      });

      // Emit navigation lifecycle events
      if (changeInfo.status === 'loading' && changeInfo.url) {
        browserBridge.sendEvent(BridgeAction.NAVIGATION_STARTED, {
          tab_id: tabId,
          url: changeInfo.url,
          browser_id: browserController.getBrowserId()
        });
      } else if (changeInfo.status === 'complete') {
        browserBridge.sendEvent(BridgeAction.NAVIGATION_COMPLETED, {
          tab_id: tabId,
          url: tab.url,
          title: tab.title,
          browser_id: browserController.getBrowserId()
        });
      }

      browserController.syncStateSnapshot().catch(() => {});
    });

    // 3. Tab Activated (Switching active tab)
    chrome.tabs.onActivated.addListener((activeInfo) => {
      logger.debug(`[EVENT] tab.activated tab_id=${activeInfo.tabId} window_id=${activeInfo.windowId}`);
      browserBridge.sendEvent(BridgeAction.TAB_ACTIVATED, {
        tab_id: activeInfo.tabId,
        window_id: activeInfo.windowId,
        browser_id: browserController.getBrowserId()
      });
      browserController.syncStateSnapshot().catch(() => {});
    });

    // 4. Tab Removed (Closing tab)
    chrome.tabs.onRemoved.addListener((tabId, removeInfo) => {
      logger.debug(`[EVENT] tab.removed tab_id=${tabId} window_id=${removeInfo.windowId}`);
      browserBridge.sendEvent(BridgeAction.TAB_REMOVED, {
        tab_id: tabId,
        window_id: removeInfo.windowId,
        is_window_closing: removeInfo.isWindowClosing,
        browser_id: browserController.getBrowserId()
      });
      browserController.syncStateSnapshot().catch(() => {});
    });
  }

  private setupWindowListeners(): void {
    if (!chrome.windows) return;

    // Window Focus Changed
    chrome.windows.onFocusChanged.addListener((windowId) => {
      if (windowId !== chrome.windows.WINDOW_ID_NONE) {
        logger.debug(`[EVENT] window.focused window_id=${windowId}`);
        browserBridge.sendEvent(BridgeAction.WINDOW_FOCUSED, {
          window_id: windowId,
          browser_id: browserController.getBrowserId()
        });
        browserController.syncStateSnapshot().catch(() => {});
      }
    });
  }
}

export const browserEventEngine = new BrowserEventEngine();
