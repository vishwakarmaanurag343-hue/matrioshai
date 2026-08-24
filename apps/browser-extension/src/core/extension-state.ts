/**
 * MATRIOSHAI Extension State Manager (Phase 1)
 */

import { EXTENSION_VERSION, STORAGE_KEYS, DEFAULT_ENVIRONMENT } from '../shared/constants';
import { createScopedLogger } from '../shared/logger';
import type { ExtensionState } from '../shared/types';

const logger = createScopedLogger('STATE');

export class ExtensionStateManager {
  private state: ExtensionState;
  private listeners: Set<(state: ExtensionState) => void> = new Set();

  constructor(initialState?: Partial<ExtensionState>) {
    this.state = {
      installed: false,
      initialized: false,
      serviceWorkerReady: false,
      contentScriptReady: false,
      extensionVersion: EXTENSION_VERSION,
      lastError: null,
      environment: DEFAULT_ENVIRONMENT,
      timestamp: new Date().toISOString(),
      bridgeState: 'DISCONNECTED',
      bridgeSessionId: null,
      bridgeAuthenticated: false,
      bridgeLatencyMs: null,
      lastHeartbeatAck: null,
      browserId: 'chrome_instance_' + Math.random().toString(36).slice(2, 8),
      windowsCount: 0,
      tabsCount: 0,
      activeTabId: null,
      activeTabUrl: null,
      navigationState: 'IDLE',
      lastCommand: null,
      lastCommandResult: null,
      activeWindowId: null,
      observationState: 'idle',
      agentState: 'idle',
      ...initialState
    };
  }

  public getState(): Readonly<ExtensionState> {
    return { ...this.state };
  }

  public async initialize(): Promise<ExtensionState> {
    logger.debug('Initializing extension state manager...');
    try {
      const persisted = await this.loadFromStorage();
      if (persisted) {
        this.state = {
          ...this.state,
          ...persisted,
          initialized: true,
          timestamp: new Date().toISOString()
        };
      } else {
        this.state.initialized = true;
        this.state.timestamp = new Date().toISOString();
      }
      await this.persistToStorage();
      logger.info('Extension state initialized successfully', { version: this.state.extensionVersion });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      this.state.lastError = errMsg;
      logger.error('Failed to initialize state manager', errMsg);
    }
    this.notifyListeners();
    return this.getState();
  }

  public async updateState(patch: Partial<ExtensionState>): Promise<ExtensionState> {
    this.state = {
      ...this.state,
      ...patch,
      timestamp: new Date().toISOString()
    };
    await this.persistToStorage();
    this.notifyListeners();
    return this.getState();
  }

  public async setServiceWorkerReady(ready: boolean): Promise<void> {
    await this.updateState({ serviceWorkerReady: ready });
  }

  public async setContentScriptReady(ready: boolean): Promise<void> {
    await this.updateState({ contentScriptReady: ready });
  }

  public async recordError(error: string | Error): Promise<void> {
    const errorString = error instanceof Error ? error.message : String(error);
    logger.error('Extension error recorded', errorString);
    await this.updateState({ lastError: errorString });
  }

  public async clearError(): Promise<void> {
    await this.updateState({ lastError: null });
  }

  public subscribe(listener: (state: ExtensionState) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notifyListeners(): void {
    const snapshot = this.getState();
    for (const listener of this.listeners) {
      try {
        listener(snapshot);
      } catch (err) {
        logger.warn('State listener error', err);
      }
    }
  }

  private async persistToStorage(): Promise<void> {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      try {
        await chrome.storage.local.set({ [STORAGE_KEYS.STATE]: this.state });
      } catch (err) {
        logger.debug('Storage persist not available or failed', err);
      }
    }
  }

  private async loadFromStorage(): Promise<Partial<ExtensionState> | null> {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      try {
        const result = await chrome.storage.local.get(STORAGE_KEYS.STATE);
        return (result[STORAGE_KEYS.STATE] as Partial<ExtensionState>) || null;
      } catch (err) {
        logger.debug('Storage retrieval not available or failed', err);
      }
    }
    return null;
  }
}

// Global Singleton Instance
export const extensionState = new ExtensionStateManager();
