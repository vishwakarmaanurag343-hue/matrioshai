/**
 * MATRIOSHAI Popup Diagnostic Controller (Phase 1, Phase 2 & Phase 3)
 */

import { createScopedLogger } from '../shared/logger';
import {
  MessageAction,
  type ExtensionMessage,
  type ExtensionResponse,
  type DiagnosticSummary
} from '../shared/types';

const logger = createScopedLogger('POPUP');

class PopupController {
  private btnRefresh: HTMLButtonElement | null = null;
  private valWindowsTabs: HTMLElement | null = null;
  private valNavState: HTMLElement | null = null;
  private valActiveTabId: HTMLElement | null = null;
  private dotBridge: HTMLElement | null = null;
  private valBridge: HTMLElement | null = null;
  private dotAuth: HTMLElement | null = null;
  private valAuth: HTMLElement | null = null;
  private valLatency: HTMLElement | null = null;
  private valActiveTab: HTMLElement | null = null;
  private globalIndicator: HTMLElement | null = null;
  private envBadge: HTMLElement | null = null;
  private errorBanner: HTMLElement | null = null;
  private errorText: HTMLElement | null = null;
  private lastUpdated: HTMLElement | null = null;

  constructor() {
    this.bindDOMElements();
    this.bindEvents();
  }

  private bindDOMElements(): void {
    this.btnRefresh = document.getElementById('btnRefresh') as HTMLButtonElement;
    this.valWindowsTabs = document.getElementById('valWindowsTabs');
    this.valNavState = document.getElementById('valNavState');
    this.valActiveTabId = document.getElementById('valActiveTabId');
    this.dotBridge = document.getElementById('dotBridge');
    this.valBridge = document.getElementById('valBridge');
    this.dotAuth = document.getElementById('dotAuth');
    this.valAuth = document.getElementById('valAuth');
    this.valLatency = document.getElementById('valLatency');
    this.valActiveTab = document.getElementById('valActiveTab');
    this.globalIndicator = document.getElementById('globalIndicator');
    this.envBadge = document.getElementById('envBadge');
    this.errorBanner = document.getElementById('errorBanner');
    this.errorText = document.getElementById('errorText');
    this.lastUpdated = document.getElementById('lastUpdated');
  }

  private bindEvents(): void {
    if (this.btnRefresh) {
      this.btnRefresh.addEventListener('click', () => {
        this.refreshStatus(true);
      });
    }
  }

  public async init(): Promise<void> {
    logger.info('Initializing MATRIOSHAI Popup UI');
    await this.refreshStatus(false);
  }

  public async refreshStatus(manual = false): Promise<void> {
    if (this.btnRefresh) {
      this.btnRefresh.disabled = true;
      this.btnRefresh.style.opacity = '0.7';
    }

    try {
      const summary = await this.queryServiceWorkerStatus();
      this.renderStatus(summary);

      if (this.lastUpdated) {
        const timeStr = new Date().toLocaleTimeString();
        this.lastUpdated.textContent = `Updated ${timeStr}`;
      }

      if (manual) {
        logger.debug('Manual status refresh complete');
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      logger.error('Failed to refresh popup diagnostic status', errorMsg);
      this.showError(`Connection error: ${errorMsg}`);
    } finally {
      if (this.btnRefresh) {
        this.btnRefresh.disabled = false;
        this.btnRefresh.style.opacity = '1';
      }
    }
  }

  private async queryServiceWorkerStatus(): Promise<DiagnosticSummary | null> {
    if (typeof chrome === 'undefined' || !chrome.runtime || !chrome.runtime.sendMessage) {
      return null;
    }

    const message: ExtensionMessage = {
      action: MessageAction.GET_STATUS,
      source: 'popup',
      target: 'service-worker',
      timestamp: new Date().toISOString()
    };

    return new Promise((resolve) => {
      chrome.runtime.sendMessage(message, (response: ExtensionResponse<DiagnosticSummary>) => {
        if (chrome.runtime.lastError || !response || !response.success) {
          logger.warn('Service worker not responding', chrome.runtime.lastError?.message);
          resolve(null);
        } else {
          resolve(response.data || null);
        }
      });
    });
  }

  private renderStatus(summary: DiagnosticSummary | null): void {
    const bridge = summary?.bridge;
    const browser = summary?.browser;

    // --- Phase 3 Browser Diagnostics ---
    if (browser) {
      if (this.valWindowsTabs) {
        this.valWindowsTabs.textContent = `${browser.windowsCount} W / ${browser.tabsCount} T`;
      }
      if (this.valNavState) {
        this.valNavState.textContent = browser.navigationState;
        this.valNavState.style.color = browser.navigationState === 'NAVIGATING' ? 'var(--status-pending)' : 'var(--status-ok)';
      }
      if (this.valActiveTabId) {
        this.valActiveTabId.textContent = browser.activeTabId ? `Tab #${browser.activeTabId}` : 'None';
      }
    }

    // --- Phase 2 Bridge Status ---
    if (bridge) {
      if (this.valBridge) this.valBridge.textContent = bridge.state;
      if (this.dotBridge) {
        if (bridge.state === 'READY') {
          this.dotBridge.className = 'status-dot dot-ready';
        } else if (bridge.state === 'CONNECTING' || bridge.state === 'RECONNECTING' || bridge.state === 'AUTHENTICATING') {
          this.dotBridge.className = 'status-dot dot-pending';
        } else {
          this.dotBridge.className = 'status-dot dot-error';
        }
      }

      if (this.valAuth) {
        this.valAuth.textContent = bridge.authenticated ? 'Authenticated (READY)' : (bridge.state === 'AUTHENTICATING' ? 'Authenticating...' : 'Unauthenticated');
      }
      if (this.dotAuth) {
        this.dotAuth.className = bridge.authenticated ? 'status-dot dot-ready' : 'status-dot dot-pending';
      }

      if (this.valLatency) {
        this.valLatency.textContent = bridge.latencyMs !== null ? `${bridge.latencyMs} ms` : '-- ms';
      }

      if (this.globalIndicator) {
        this.globalIndicator.className = bridge.state === 'READY' ? 'pulse-indicator active' : (bridge.state === 'ERROR' ? 'pulse-indicator error' : 'pulse-indicator');
      }
    }

    // Environment
    if (this.envBadge && summary?.environment) {
      this.envBadge.textContent = summary.environment === 'production' ? 'PROD' : 'DEV';
    }

    // Active Tab Display
    if (this.valActiveTab) {
      if (summary?.activeTab?.url) {
        this.valActiveTab.textContent = summary.activeTab.url;
      } else {
        this.valActiveTab.textContent = 'No active web tab';
      }
    }

    // Error handling
    if (summary?.lastError) {
      this.showError(summary.lastError);
    } else {
      this.hideError();
    }
  }

  private showError(msg: string): void {
    if (this.errorBanner && this.errorText) {
      this.errorText.textContent = msg;
      this.errorBanner.style.display = 'flex';
    }
  }

  private hideError(): void {
    if (this.errorBanner) {
      this.errorBanner.style.display = 'none';
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const controller = new PopupController();
  controller.init().catch((err) => {
    logger.error('Unhandled popup init error', err);
  });
});
