/**
 * MATRIOSHAI Browser Controller (Phase 3)
 *
 * Direct execution interface for Chrome browser window, tab, and navigation control.
 * Uses chrome.tabs and chrome.windows Manifest V3 APIs with strict URL validation,
 * deterministic lifecycle tracking, and audit logging.
 */

import { TIMEOUTS, STORAGE_KEYS } from '../shared/constants';
import { createScopedLogger } from '../shared/logger';
import {
  type WindowState,
  type TabState,
  type TabStatus,
  type NavigationResult,
  type BrowserAuditLog
} from '../shared/types';
import { extensionState } from './extension-state';

const logger = createScopedLogger('CONTROLLER');

export class BrowserController {
  private browserId: string = '';
  private auditLogs: BrowserAuditLog[] = [];

  constructor() {
    this.initBrowserId();
  }

  private async initBrowserId(): Promise<void> {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      try {
        const stored = await chrome.storage.local.get(STORAGE_KEYS.BROWSER_ID);
        if (stored && stored[STORAGE_KEYS.BROWSER_ID]) {
          this.browserId = stored[STORAGE_KEYS.BROWSER_ID] as string;
        } else {
          this.browserId = `chrome_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
          await chrome.storage.local.set({ [STORAGE_KEYS.BROWSER_ID]: this.browserId });
        }
      } catch {
        this.browserId = `chrome_fallback_${Date.now()}`;
      }
    } else {
      this.browserId = `chrome_dev_${Date.now()}`;
    }
  }

  public getBrowserId(): string {
    return this.browserId;
  }

  /**
   * Validate and sanitize URL for navigation.
   * Rejects javascript:, data:, file:, etc.
   */
  public validateUrl(url: string): { valid: boolean; normalizedUrl?: string; error?: string } {
    if (!url || typeof url !== 'string') {
      return { valid: false, error: 'URL is required and must be a string' };
    }

    const trimmed = url.trim();
    const lower = trimmed.toLowerCase();

    // Reject dangerous schemes
    if (
      lower.startsWith('javascript:') ||
      lower.startsWith('data:') ||
      lower.startsWith('file:') ||
      lower.startsWith('vbscript:')
    ) {
      return { valid: false, error: `Dangerous or unsupported URL scheme in: '${url}'` };
    }

    // Add protocol if missing (e.g. "example.com" -> "https://example.com")
    let normalized = trimmed;
    if (!lower.startsWith('http://') && !lower.startsWith('https://') && !lower.startsWith('chrome://') && !lower.startsWith('about:')) {
      normalized = `https://${trimmed}`;
    }

    try {
      new URL(normalized);
      return { valid: true, normalizedUrl: normalized };
    } catch {
      return { valid: false, error: `Malformed URL: '${url}'` };
    }
  }

  /**
   * Map Chrome Tab object to Phase 3 TabState model
   */
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

  /**
   * Map Chrome Window object to Phase 3 WindowState model
   */
  private mapWindowState(win: chrome.windows.Window): WindowState {
    const tabIds = win.tabs ? win.tabs.map((t) => t.id!).filter((id) => id !== undefined) : [];
    const activeTab = win.tabs ? win.tabs.find((t) => t.active) : null;

    return {
      window_id: win.id ?? -1,
      type: win.type ?? 'normal',
      focused: win.focused ?? false,
      state: win.state ?? 'normal',
      tab_ids: tabIds,
      active_tab_id: activeTab?.id ?? null
    };
  }

  /**
   * Discover all open browser windows
   */
  public async getWindows(): Promise<WindowState[]> {
    if (typeof chrome === 'undefined' || !chrome.windows) {
      return [];
    }

    const windows = await chrome.windows.getAll({ populate: true });
    return windows.map((w) => this.mapWindowState(w));
  }

  /**
   * Discover all open tabs
   */
  public async getTabs(): Promise<TabState[]> {
    if (typeof chrome === 'undefined' || !chrome.tabs) {
      return [];
    }

    const tabs = await chrome.tabs.query({});
    return tabs.map((t) => this.mapTabState(t));
  }

  /**
   * Get tab by ID
   */
  public async getTab(tabId: number): Promise<TabState | null> {
    if (typeof chrome === 'undefined' || !chrome.tabs) {
      return null;
    }
    try {
      const tab = await chrome.tabs.get(tabId);
      return tab ? this.mapTabState(tab) : null;
    } catch {
      return null;
    }
  }

  /**
   * Get the current active tab
   */
  public async getActiveTab(): Promise<TabState | null> {
    if (typeof chrome === 'undefined' || !chrome.tabs) {
      return null;
    }

    const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (tabs.length > 0 && tabs[0]) {
      return this.mapTabState(tabs[0]);
    }

    // Fallback: active tab in any window
    const anyActive = await chrome.tabs.query({ active: true });
    if (anyActive.length > 0 && anyActive[0]) {
      return this.mapTabState(anyActive[0]);
    }

    return null;
  }

  /**
   * Open a new browser tab
   */
  public async openTab(url?: string): Promise<TabState> {
    const actionId = `act_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    let targetUrl: string | undefined = undefined;

    if (url) {
      const validation = this.validateUrl(url);
      if (!validation.valid) {
        this.recordAuditLog(actionId, 'browser.openTab', null, url, 'failed', validation.error);
        throw new Error(`INVALID_URL: ${validation.error}`);
      }
      targetUrl = validation.normalizedUrl;
    }

    logger.info(`Opening new tab with URL: ${targetUrl || 'about:blank'}`);

    if (typeof chrome === 'undefined' || !chrome.tabs) {
      throw new Error('Chrome tabs API not available');
    }

    try {
      const newTab = await chrome.tabs.create({ url: targetUrl, active: true });
      const tabState = this.mapTabState(newTab);
      this.recordAuditLog(actionId, 'browser.openTab', newTab.id ?? null, targetUrl, 'success');
      await this.syncStateSnapshot();
      return tabState;
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      this.recordAuditLog(actionId, 'browser.openTab', null, targetUrl, 'failed', errMsg);
      throw err;
    }
  }

  /**
   * Switch active tab
   */
  public async switchTab(tabId: number): Promise<TabState> {
    const actionId = `act_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    logger.info(`Switching to tab ID: ${tabId}`);

    if (typeof chrome === 'undefined' || !chrome.tabs) {
      throw new Error('Chrome tabs API not available');
    }

    try {
      // 1. Validate tab exists
      const existingTab = await chrome.tabs.get(tabId);
      if (!existingTab) {
        throw new Error(`TAB_NOT_FOUND: Tab ID ${tabId} does not exist`);
      }

      // 2. Activate tab
      const updatedTab = await chrome.tabs.update(tabId, { active: true });

      // 3. Focus window if necessary
      if (updatedTab.windowId && chrome.windows) {
        await chrome.windows.update(updatedTab.windowId, { focused: true }).catch(() => {});
      }

      const tabState = this.mapTabState(updatedTab);
      this.recordAuditLog(actionId, 'browser.switchTab', tabId, null, 'success');
      await this.syncStateSnapshot();
      return tabState;
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      this.recordAuditLog(actionId, 'browser.switchTab', tabId, null, 'failed', errMsg);
      if (errMsg.includes('No tab with id')) {
        throw new Error(`TAB_NOT_FOUND: Tab with ID ${tabId} does not exist`);
      }
      throw err;
    }
  }

  /**
   * Close a browser tab
   */
  public async closeTab(tabId: number): Promise<{ success: boolean; closed_tab_id: number }> {
    const actionId = `act_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    logger.info(`Closing tab ID: ${tabId}`);

    if (typeof chrome === 'undefined' || !chrome.tabs) {
      throw new Error('Chrome tabs API not available');
    }

    try {
      // Validate tab exists
      const existing = await chrome.tabs.get(tabId);
      if (!existing) {
        throw new Error(`TAB_NOT_FOUND: Tab ID ${tabId} does not exist`);
      }

      await chrome.tabs.remove(tabId);
      this.recordAuditLog(actionId, 'browser.closeTab', tabId, null, 'success');
      await this.syncStateSnapshot();
      return { success: true, closed_tab_id: tabId };
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      this.recordAuditLog(actionId, 'browser.closeTab', tabId, null, 'failed', errMsg);
      if (errMsg.includes('No tab with id')) {
        throw new Error(`TAB_NOT_FOUND: Tab with ID ${tabId} does not exist`);
      }
      throw err;
    }
  }

  /**
   * Navigate a tab to a specified URL and await completion
   */
  public async navigate(tabId: number, url: string, timeoutMs: number = TIMEOUTS.NAVIGATION_TIMEOUT_MS): Promise<NavigationResult> {
    const navigationId = `nav_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const actionId = `act_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

    // 1. Validate URL
    const validation = this.validateUrl(url);
    if (!validation.valid || !validation.normalizedUrl) {
      this.recordAuditLog(actionId, 'browser.navigate', tabId, url, 'failed', validation.error);
      return {
        navigation_id: navigationId,
        tab_id: tabId,
        requested_url: url,
        status: 'FAILED',
        timestamp: new Date().toISOString(),
        error: { code: 'INVALID_URL', message: validation.error || 'Invalid URL' }
      };
    }

    const targetUrl = validation.normalizedUrl;

    if (typeof chrome === 'undefined' || !chrome.tabs) {
      return {
        navigation_id: navigationId,
        tab_id: tabId,
        requested_url: targetUrl,
        status: 'FAILED',
        timestamp: new Date().toISOString(),
        error: { code: 'BROWSER_UNAVAILABLE', message: 'Chrome tabs API not available' }
      };
    }

    try {
      // 2. Validate tab exists
      const existingTab = await chrome.tabs.get(tabId);
      if (!existingTab) {
        return {
          navigation_id: navigationId,
          tab_id: tabId,
          requested_url: targetUrl,
          status: 'FAILED',
          timestamp: new Date().toISOString(),
          error: { code: 'TAB_NOT_FOUND', message: `Tab ${tabId} does not exist` }
        };
      }

      logger.info(`[NAVIGATION_REQUEST] tab=${tabId} from='${existingTab.url}' to='${targetUrl}' (NavID: ${navigationId})`);

      // Update extension state to NAVIGATING
      await extensionState.updateState({
        navigationState: 'NAVIGATING',
        lastCommand: `browser.navigate(${tabId}, ${targetUrl})`
      });

      // 3. Initiate Chrome tab update
      await chrome.tabs.update(tabId, { url: targetUrl });

      // 4. Wait for navigation to complete
      const finalTab = await this.waitForNavigation(tabId, timeoutMs);

      logger.info(`[NAVIGATION_COMPLETED] tab=${tabId} final_url='${finalTab.url}' status=COMPLETED`);

      this.recordAuditLog(actionId, 'browser.navigate', tabId, targetUrl, 'success');
      await extensionState.updateState({
        navigationState: 'IDLE',
        activeTabId: tabId,
        activeTabUrl: finalTab.url,
        lastCommandResult: 'SUCCESS'
      });

      return {
        navigation_id: navigationId,
        tab_id: tabId,
        requested_url: targetUrl,
        final_url: finalTab.url,
        status: 'COMPLETED',
        timestamp: new Date().toISOString()
      };
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      logger.warn(`[NAVIGATION_FAILED] tab=${tabId} error='${errMsg}'`);

      this.recordAuditLog(actionId, 'browser.navigate', tabId, targetUrl, 'failed', errMsg);
      await extensionState.updateState({
        navigationState: 'IDLE',
        lastCommandResult: 'FAILED'
      });

      const errorCode = errMsg.includes('TIMEOUT') ? 'NAVIGATION_TIMEOUT' : (errMsg.includes('TAB_NOT_FOUND') ? 'TAB_NOT_FOUND' : 'NAVIGATION_FAILED');

      return {
        navigation_id: navigationId,
        tab_id: tabId,
        requested_url: targetUrl,
        status: 'FAILED',
        timestamp: new Date().toISOString(),
        error: { code: errorCode, message: errMsg }
      };
    }
  }

  /**
   * Reload an existing tab
   */
  public async reload(tabId: number, timeoutMs: number = TIMEOUTS.NAVIGATION_TIMEOUT_MS): Promise<NavigationResult> {
    const navId = `reload_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const actionId = `act_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

    if (typeof chrome === 'undefined' || !chrome.tabs) {
      throw new Error('Chrome tabs API not available');
    }

    try {
      const existing = await chrome.tabs.get(tabId);
      if (!existing) {
        throw new Error(`TAB_NOT_FOUND: Tab ID ${tabId} does not exist`);
      }

      logger.info(`Reloading tab ID: ${tabId}`);
      await chrome.tabs.reload(tabId);

      const finalTab = await this.waitForNavigation(tabId, timeoutMs);
      this.recordAuditLog(actionId, 'browser.reload', tabId, existing.url ?? '', 'success');

      return {
        navigation_id: navId,
        tab_id: tabId,
        requested_url: existing.url ?? '',
        final_url: finalTab.url,
        status: 'COMPLETED',
        timestamp: new Date().toISOString()
      };
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      this.recordAuditLog(actionId, 'browser.reload', tabId, null, 'failed', errMsg);
      throw err;
    }
  }

  /**
   * Go back in browser history for a tab
   */
  public async goBack(tabId: number, timeoutMs: number = TIMEOUTS.NAVIGATION_TIMEOUT_MS): Promise<NavigationResult> {
    const navId = `back_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const actionId = `act_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

    if (typeof chrome === 'undefined' || !chrome.tabs) {
      throw new Error('Chrome tabs API not available');
    }

    try {
      const existing = await chrome.tabs.get(tabId);
      if (!existing) {
        throw new Error(`TAB_NOT_FOUND: Tab ID ${tabId} does not exist`);
      }

      await chrome.tabs.goBack(tabId);
      const finalTab = await this.waitForNavigation(tabId, timeoutMs);
      this.recordAuditLog(actionId, 'browser.goBack', tabId, finalTab.url, 'success');

      return {
        navigation_id: navId,
        tab_id: tabId,
        requested_url: 'history.back',
        final_url: finalTab.url,
        status: 'COMPLETED',
        timestamp: new Date().toISOString()
      };
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      this.recordAuditLog(actionId, 'browser.goBack', tabId, null, 'failed', errMsg);
      throw err;
    }
  }

  /**
   * Go forward in browser history for a tab
   */
  public async goForward(tabId: number, timeoutMs: number = TIMEOUTS.NAVIGATION_TIMEOUT_MS): Promise<NavigationResult> {
    const navId = `fwd_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const actionId = `act_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

    if (typeof chrome === 'undefined' || !chrome.tabs) {
      throw new Error('Chrome tabs API not available');
    }

    try {
      const existing = await chrome.tabs.get(tabId);
      if (!existing) {
        throw new Error(`TAB_NOT_FOUND: Tab ID ${tabId} does not exist`);
      }

      await chrome.tabs.goForward(tabId);
      const finalTab = await this.waitForNavigation(tabId, timeoutMs);
      this.recordAuditLog(actionId, 'browser.goForward', tabId, finalTab.url, 'success');

      return {
        navigation_id: navId,
        tab_id: tabId,
        requested_url: 'history.forward',
        final_url: finalTab.url,
        status: 'COMPLETED',
        timestamp: new Date().toISOString()
      };
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      this.recordAuditLog(actionId, 'browser.goForward', tabId, null, 'failed', errMsg);
      throw err;
    }
  }

  /**
   * Deterministically wait for a tab to finish loading/navigation.
   * Listens for chrome.tabs.onUpdated until status is 'complete' or timeout occurs.
   */
  public async waitForNavigation(tabId: number, timeoutMs: number = TIMEOUTS.NAVIGATION_TIMEOUT_MS): Promise<TabState> {
    if (typeof chrome === 'undefined' || !chrome.tabs) {
      throw new Error('Chrome tabs API not available');
    }

    // 1. Check if tab is already complete
    try {
      const initialTab = await chrome.tabs.get(tabId);
      if (initialTab.status === 'complete') {
        return this.mapTabState(initialTab);
      }
    } catch {
      throw new Error(`TAB_NOT_FOUND: Tab ${tabId} does not exist`);
    }

    // 2. Await tab update event
    return new Promise<TabState>((resolve, reject) => {
      let resolved = false;

      const timer = setTimeout(() => {
        if (!resolved) {
          resolved = true;
          chrome.tabs.onUpdated.removeListener(listener);
          chrome.tabs.onRemoved.removeListener(removeListener);
          reject(new Error(`NAVIGATION_TIMEOUT: Tab ${tabId} did not complete navigation within ${timeoutMs}ms`));
        }
      }, timeoutMs);

      const listener = (updatedTabId: number, changeInfo: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab) => {
        if (updatedTabId === tabId && changeInfo.status === 'complete') {
          if (!resolved) {
            resolved = true;
            clearTimeout(timer);
            chrome.tabs.onUpdated.removeListener(listener);
            chrome.tabs.onRemoved.removeListener(removeListener);
            resolve(this.mapTabState(tab));
          }
        }
      };

      const removeListener = (removedTabId: number) => {
        if (removedTabId === tabId) {
          if (!resolved) {
            resolved = true;
            clearTimeout(timer);
            chrome.tabs.onUpdated.removeListener(listener);
            chrome.tabs.onRemoved.removeListener(removeListener);
            reject(new Error(`TAB_CLOSED: Tab ${tabId} was closed before navigation finished`));
          }
        }
      };

      chrome.tabs.onUpdated.addListener(listener);
      chrome.tabs.onRemoved.addListener(removeListener);
    });
  }

  /**
   * Synchronize state metrics into extensionState
   */
  public async syncStateSnapshot(): Promise<void> {
    try {
      const [windows, tabs, activeTab] = await Promise.all([
        this.getWindows(),
        this.getTabs(),
        this.getActiveTab()
      ]);

      await extensionState.updateState({
        browserId: this.browserId,
        windowsCount: windows.length,
        tabsCount: tabs.length,
        activeTabId: activeTab?.tab_id ?? null,
        activeTabUrl: activeTab?.url ?? null
      });
    } catch (err) {
      logger.debug('Error synchronizing browser state snapshot', err);
    }
  }

  /**
   * Capture visible viewport screenshot for a specific tab/window (Phase 6)
   */
  public async captureScreenshot(
    tabId?: number,
    options?: { format?: 'png' | 'jpeg'; quality?: number }
  ): Promise<{ dataUrl: string; width: number; height: number; scaled: boolean }> {
    const actionId = `act_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    let targetWindowId: number | undefined;

    if (tabId && tabId > 0) {
      const tab = await this.getTab(tabId);
      if (tab) {
        targetWindowId = tab.window_id;
      }
    }

    if (!targetWindowId) {
      const activeTab = await this.getActiveTab();
      if (activeTab) {
        targetWindowId = activeTab.window_id;
      }
    }

    const format = options?.format === 'jpeg' ? 'jpeg' : 'png';
    const quality = options?.quality ?? 90;

    return new Promise((resolve, reject) => {
      if (typeof chrome === 'undefined' || !chrome.tabs || !chrome.tabs.captureVisibleTab) {
        // Fallback transparent 1x1 png data URI for mock/test environments
        const fallbackDataUrl = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
        this.recordAuditLog(actionId, 'page.captureScreenshot', tabId ?? null, null, 'success');
        resolve({ dataUrl: fallbackDataUrl, width: 1280, height: 800, scaled: false });
        return;
      }

      chrome.tabs.captureVisibleTab(
        targetWindowId ?? chrome.windows.WINDOW_ID_CURRENT,
        { format, quality },
        (dataUrl) => {
          if (chrome.runtime.lastError || !dataUrl) {
            const err = chrome.runtime.lastError?.message || 'Failed to capture visible tab';
            this.recordAuditLog(actionId, 'page.captureScreenshot', tabId ?? null, null, 'failed', err);
            reject(new Error(err));
          } else {
            this.recordAuditLog(actionId, 'page.captureScreenshot', tabId ?? null, null, 'success');
            resolve({ dataUrl, width: 1280, height: 800, scaled: false });
          }
        }
      );
    });
  }

  private recordAuditLog(
    actionId: string,
    type: string,
    tabId: number | null,
    requestedUrl: string | null | undefined,
    result: 'success' | 'failed',
    error?: string | null
  ): void {
    const entry: BrowserAuditLog = {
      action_id: actionId,
      type,
      browser_id: this.browserId,
      tab_id: tabId,
      requested_url: requestedUrl ?? null,
      timestamp: new Date().toISOString(),
      result,
      error: error ?? null
    };
    this.auditLogs.push(entry);
    if (this.auditLogs.length > 200) {
      this.auditLogs.shift();
    }
  }
}

// Global Singleton Instance
export const browserController = new BrowserController();
