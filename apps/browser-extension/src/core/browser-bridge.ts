/**
 * MATRIOSHAI Browser Bridge Client (Phase 2 & Phase 3)
 *
 * Manages the persistent WebSocket connection between the Chrome Extension
 * Background Service Worker and the MATRIOSHAI Backend Bridge Server.
 * Supports Phase 2 Health/Diagnostics and Phase 3 Deterministic Browser Control.
 */

import {
  BRIDGE_CONFIG,
  EXTENSION_VERSION,
  PHASE_14_CAPABILITIES,
  PROTOCOL_VERSION,
  STORAGE_KEYS
} from '../shared/constants';
import { createScopedLogger } from '../shared/logger';
import {
  BridgeAction,
  MessageAction,
  type BridgeConnectionState,
  type BridgeEnvelope,
  type IBrowserBridge,
  type PageObservation,
  type SemanticPageModel,
  type QueryResult,
  type ResolveResult,
  type VisualPageModel,
  type VisualQueryResult,
  type PointQueryResult,
  type ScreenshotMetadata,
  type PrivacyMode,
  type WorldPageState,
  type FrameTree,
  type WorldElement,
  type WorldElementRef,
  type WorldElementResolution,
  type ActionIntent,
  type ActionStatus,
  type ExtensionResponse
} from '../shared/types';
import { browserController } from './browser-controller';
import { extensionState } from './extension-state';

const logger = createScopedLogger('BRIDGE');

interface PendingBridgeRequest {
  messageId: string;
  action: string;
  resolve: (payload: unknown) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

export class BrowserBridgeClient implements IBrowserBridge {
  private ws: WebSocket | null = null;
  private state: BridgeConnectionState = 'DISCONNECTED';
  private endpoint: string = BRIDGE_CONFIG.WS_ENDPOINT;
  private tokenEndpoint: string = BRIDGE_CONFIG.HTTP_TOKEN_ENDPOINT;
  private sessionId: string | null = null;
  private authenticated = false;
  private reconnectDelay: number = BRIDGE_CONFIG.RECONNECT_INITIAL_DELAY_MS;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pendingRequests = new Map<string, PendingBridgeRequest>();
  private stateListeners = new Set<(state: BridgeConnectionState) => void>();
  private lastLatencyMs: number | null = null;
  private lastHeartbeatAck: string | null = null;
  private intentionalClose = false;

  constructor(endpoint?: string) {
    if (endpoint) {
      this.endpoint = endpoint;
    }
  }

  public getState(): BridgeConnectionState {
    return this.state;
  }

  public isAuthenticated(): boolean {
    return this.authenticated;
  }

  public getSessionId(): string | null {
    return this.sessionId;
  }

  public getLatencyMs(): number | null {
    return this.lastLatencyMs;
  }

  public getLastHeartbeat(): string | null {
    return this.lastHeartbeatAck;
  }

  public getAdvertisedCapabilities(): string[] {
    return [...PHASE_14_CAPABILITIES];
  }

  public subscribe(listener: (state: BridgeConnectionState) => void): () => void {
    this.stateListeners.add(listener);
    return () => this.stateListeners.delete(listener);
  }

  private setState(newState: BridgeConnectionState): void {
    if (this.state !== newState) {
      logger.info(`Bridge connection state change: ${this.state} -> ${newState}`);
      this.state = newState;
      this.authenticated = newState === 'READY';

      // Synchronize with extension state manager
      extensionState.updateState({
        bridgeState: newState,
        bridgeSessionId: this.sessionId,
        bridgeAuthenticated: this.authenticated,
        bridgeLatencyMs: this.lastLatencyMs,
        lastHeartbeatAck: this.lastHeartbeatAck
      }).catch((err) => logger.debug('Error syncing extension state', err));

      for (const listener of this.stateListeners) {
        try {
          listener(newState);
        } catch (err) {
          logger.warn('Bridge state listener error', err);
        }
      }
    }
  }

  /**
   * Connect to the MATRIOSHAI Backend WebSocket Bridge
   */
  public async connect(endpoint?: string): Promise<boolean> {
    if (endpoint) {
      this.endpoint = endpoint;
    }

    if (this.state === 'CONNECTING' || this.state === 'CONNECTED' || this.state === 'READY') {
      logger.debug(`Already connected or connecting (Current State: ${this.state})`);
      return this.authenticated;
    }

    this.intentionalClose = false;
    this.clearReconnectTimer();
    this.setState('CONNECTING');

    logger.info(`Connecting to MATRIOSHAI Bridge at ${this.endpoint}...`);

    try {
      if (typeof WebSocket === 'undefined') {
        logger.warn('WebSocket API not available in current environment');
        this.setState('ERROR');
        return false;
      }

      this.ws = new WebSocket(this.endpoint);
      this.setupWebSocketListeners();
      return true;
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      logger.error('Failed to create WebSocket connection', errMsg);
      this.setState('ERROR');
      this.scheduleReconnect();
      return false;
    }
  }

  /**
   * Disconnect the bridge cleanly
   */
  public async disconnect(): Promise<void> {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    this.setState('CLOSING');

    if (this.ws) {
      try {
        this.ws.close(1000, 'Clean extension disconnect');
      } catch (err) {
        logger.debug('Error closing WebSocket', err);
      }
      this.ws = null;
    }

    this.cleanupPendingRequests('Bridge disconnected');
    this.sessionId = null;
    this.setState('DISCONNECTED');
    logger.info('Bridge disconnected cleanly');
  }

  private setupWebSocketListeners(): void {
    if (!this.ws) return;

    this.ws.onopen = async () => {
      logger.info('WebSocket connection open. Starting authentication handshake...');
      this.setState('CONNECTED');
      this.reconnectDelay = BRIDGE_CONFIG.RECONNECT_INITIAL_DELAY_MS; // Reset backoff on open
      await this.authenticate();
    };

    this.ws.onmessage = async (event: MessageEvent) => {
      try {
        const rawData = JSON.parse(event.data);
        await this.handleIncomingMessage(rawData);
      } catch (err) {
        logger.warn('Failed to parse incoming WebSocket message', err);
      }
    };

    this.ws.onerror = (event: Event) => {
      logger.warn('WebSocket error encountered', event);
      if (this.state !== 'CLOSING') {
        this.setState('DEGRADED');
      }
    };

    this.ws.onclose = (event: CloseEvent) => {
      logger.info(`WebSocket closed (code: ${event.code}, reason: ${event.reason || 'None'})`);
      this.ws = null;
      this.sessionId = null;
      this.cleanupPendingRequests('WebSocket closed');

      if (!this.intentionalClose) {
        this.setState('RECONNECTING');
        this.scheduleReconnect();
      } else {
        this.setState('DISCONNECTED');
      }
    };
  }

  /**
   * Perform secure authentication handshake with backend
   */
  private async authenticate(): Promise<void> {
    this.setState('AUTHENTICATING');

    const token = await this.getAuthToken();
    const messageId = `auth_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

    const authPayload: BridgeEnvelope = {
      protocol_version: PROTOCOL_VERSION,
      message_id: messageId,
      type: 'request',
      action: BridgeAction.AUTH,
      timestamp: new Date().toISOString(),
      payload: {
        token,
        client_id: 'matrioshai-chrome-extension',
        version: EXTENSION_VERSION,
        browser_id: browserController.getBrowserId(),
        capabilities: [...PHASE_14_CAPABILITIES]
      }
    };

    logger.debug('Sending bridge authentication request...');
    this.sendRaw(authPayload);
  }

  /**
   * Retrieve localhost authentication token (from storage or backend token endpoint)
   */
  private async getAuthToken(): Promise<string> {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      try {
        const res = await chrome.storage.local.get(STORAGE_KEYS.AUTH_TOKEN);
        if (res && res[STORAGE_KEYS.AUTH_TOKEN]) {
          return res[STORAGE_KEYS.AUTH_TOKEN] as string;
        }
      } catch (err) {
        logger.debug('Storage lookup for auth token failed', err);
      }
    }

    try {
      if (typeof fetch !== 'undefined') {
        const resp = await fetch(this.tokenEndpoint);
        if (resp.ok) {
          const data = await resp.json();
          if (data && data.token) {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
              await chrome.storage.local.set({ [STORAGE_KEYS.AUTH_TOKEN]: data.token });
            }
            return data.token;
          }
        }
      }
    } catch (err) {
      logger.debug('Could not fetch token from localhost API', err);
    }

    return 'matrioshai-dev-token';
  }

  /**
   * Route incoming message from backend
   */
  private async handleIncomingMessage(msg: BridgeEnvelope): Promise<void> {
    if (!msg || typeof msg !== 'object') return;

    logger.debug(`Received message [${msg.type}] action: ${msg.action} id: ${msg.message_id}`);

    // 1. Handle Response messages matching pending requests
    if (msg.type === 'response') {
      if (msg.action === BridgeAction.AUTH) {
        if (msg.success) {
          this.sessionId = (msg.payload as { session_id?: string })?.session_id || null;
          this.setState('READY');
          logger.info(`Bridge authentication successful! Session: ${this.sessionId}`);
          browserController.syncStateSnapshot().catch(() => {});
        } else {
          this.setState('ERROR');
          logger.error('Bridge authentication rejected by server', msg.error?.message || 'Unknown error');
        }
        return;
      }

      const pending = this.pendingRequests.get(msg.message_id);
      if (pending) {
        clearTimeout(pending.timer);
        this.pendingRequests.delete(msg.message_id);
        if (msg.success) {
          pending.resolve(msg.payload);
        } else {
          pending.reject(new Error(msg.error?.message || 'Request failed'));
        }
      }
      return;
    }

    // 2. Handle Heartbeat
    if (msg.type === 'heartbeat' || msg.action === BridgeAction.HEARTBEAT) {
      const sendTime = (msg.payload as { server_time?: number })?.server_time;
      if (sendTime) {
        this.lastLatencyMs = Math.round((Date.now() / 1000 - sendTime) * 1000);
      }
      this.lastHeartbeatAck = new Date().toISOString();

      const hbAck: BridgeEnvelope = {
        protocol_version: PROTOCOL_VERSION,
        message_id: msg.message_id,
        type: 'heartbeat',
        action: BridgeAction.HEARTBEAT,
        timestamp: new Date().toISOString(),
        payload: {
          client_time: Date.now(),
          state: this.state
        }
      };
      this.sendRaw(hbAck);
      return;
    }

    // 3. Handle incoming Requests from Backend
    if (msg.type === 'request') {
      await this.dispatchIncomingRequest(msg);
    }
  }

  /**
   * Dispatch and respond to incoming requests from backend
   */
  private async dispatchIncomingRequest(msg: BridgeEnvelope): Promise<void> {
    const action = msg.action;
    const messageId = msg.message_id;
    const payload = msg.payload as Record<string, unknown>;

    try {
      switch (action) {
        // --- Phase 2 Actions ---
        case BridgeAction.PING: {
          await this.sendResponse(messageId, action, true, {
            pong: true,
            timestamp: new Date().toISOString(),
            service: 'chrome-extension'
          });
          break;
        }

        case BridgeAction.HEALTH: {
          const stateSnapshot = extensionState.getState();
          await this.sendResponse(messageId, action, true, {
            healthy: this.state === 'READY',
            extension: {
              installed: stateSnapshot.installed,
              version: EXTENSION_VERSION,
              service_worker: stateSnapshot.serviceWorkerReady ? 'ready' : 'initializing',
              content_script: stateSnapshot.contentScriptReady ? 'ready' : 'standby'
            },
            bridge: {
              state: this.state,
              session_id: this.sessionId,
              authenticated: this.authenticated,
              latency_ms: this.lastLatencyMs
            },
            browser: {
              browser_id: browserController.getBrowserId(),
              windows: stateSnapshot.windowsCount,
              tabs: stateSnapshot.tabsCount,
              active_tab_id: stateSnapshot.activeTabId
            }
          });
          break;
        }

        case BridgeAction.INFO: {
          const stateSnapshot = extensionState.getState();
          await this.sendResponse(messageId, action, true, {
            protocol_version: PROTOCOL_VERSION,
            extension_version: EXTENSION_VERSION,
            bridge_version: '0.1.0',
            browser_id: browserController.getBrowserId(),
            environment: stateSnapshot.environment,
            capabilities: [...PHASE_14_CAPABILITIES],
            timestamp: new Date().toISOString()
          });
          break;
        }

        case BridgeAction.STATUS:
        case BridgeAction.BROWSER_GET_STATUS: {
          const [windows, tabs, activeTab] = await Promise.all([
            browserController.getWindows(),
            browserController.getTabs(),
            browserController.getActiveTab()
          ]);
          await this.sendResponse(messageId, action, true, {
            browser_id: browserController.getBrowserId(),
            state: this.state,
            authenticated: this.authenticated,
            session_id: this.sessionId,
            latency_ms: this.lastLatencyMs,
            last_heartbeat: this.lastHeartbeatAck,
            windows_count: windows.length,
            tabs_count: tabs.length,
            active_tab: activeTab,
            capabilities: [...PHASE_14_CAPABILITIES]
          });
          break;
        }

        // --- Phase 3 Browser Control Actions ---
        case BridgeAction.BROWSER_GET_WINDOWS: {
          const windows = await browserController.getWindows();
          await this.sendResponse(messageId, action, true, { windows });
          break;
        }

        case BridgeAction.BROWSER_GET_TABS: {
          const tabs = await browserController.getTabs();
          await this.sendResponse(messageId, action, true, { tabs });
          break;
        }

        case BridgeAction.BROWSER_GET_ACTIVE_TAB: {
          const activeTab = await browserController.getActiveTab();
          await this.sendResponse(messageId, action, true, { tab: activeTab });
          break;
        }

        case BridgeAction.BROWSER_OPEN_TAB: {
          const url = payload.url as string | undefined;
          const tab = await browserController.openTab(url);
          await this.sendResponse(messageId, action, true, { tab });
          break;
        }

        case BridgeAction.BROWSER_SWITCH_TAB: {
          const tabId = Number(payload.tab_id);
          const tab = await browserController.switchTab(tabId);
          await this.sendResponse(messageId, action, true, { tab });
          break;
        }

        case BridgeAction.BROWSER_CLOSE_TAB: {
          const tabId = Number(payload.tab_id);
          const result = await browserController.closeTab(tabId);
          await this.sendResponse(messageId, action, true, result);
          break;
        }

        case BridgeAction.BROWSER_NAVIGATE: {
          const tabId = Number(payload.tab_id);
          const url = String(payload.url);
          const timeoutMs = Number(payload.timeout_ms) || undefined;
          const result = await browserController.navigate(tabId, url, timeoutMs);
          await this.sendResponse(messageId, action, result.status === 'COMPLETED', { navigation: result });
          break;
        }

        case BridgeAction.BROWSER_RELOAD: {
          const tabId = Number(payload.tab_id);
          const timeoutMs = Number(payload.timeout_ms) || undefined;
          const result = await browserController.reload(tabId, timeoutMs);
          await this.sendResponse(messageId, action, true, { navigation: result });
          break;
        }

        case BridgeAction.BROWSER_GO_BACK: {
          const tabId = Number(payload.tab_id);
          const timeoutMs = Number(payload.timeout_ms) || undefined;
          const result = await browserController.goBack(tabId, timeoutMs);
          await this.sendResponse(messageId, action, true, { navigation: result });
          break;
        }

        case BridgeAction.BROWSER_GO_FORWARD: {
          const tabId = Number(payload.tab_id);
          const timeoutMs = Number(payload.timeout_ms) || undefined;
          const result = await browserController.goForward(tabId, timeoutMs);
          await this.sendResponse(messageId, action, true, { navigation: result });
          break;
        }

        case BridgeAction.BROWSER_WAIT_FOR_NAVIGATION: {
          const tabId = Number(payload.tab_id);
          const timeoutMs = Number(payload.timeout_ms) || undefined;
          const tab = await browserController.waitForNavigation(tabId, timeoutMs);
          await this.sendResponse(messageId, action, true, { tab, status: 'COMPLETED' });
          break;
        }

        case BridgeAction.BROWSER_REFRESH_STATE: {
          await browserController.syncStateSnapshot();
          const [windows, tabs, activeTab] = await Promise.all([
            browserController.getWindows(),
            browserController.getTabs(),
            browserController.getActiveTab()
          ]);
          await this.sendResponse(messageId, action, true, {
            browser_id: browserController.getBrowserId(),
            windows,
            tabs,
            active_tab: activeTab
          });
          break;
        }

        case BridgeAction.PAGE_OBSERVE: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available to observe');
            }
          }

          if (typeof chrome === 'undefined' || !chrome.tabs) {
            throw new Error('Chrome tabs API not available');
          }

          // Request observation from Content Script
          const observation = await new Promise<PageObservation>((resolve, reject) => {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_OBSERVE,
                source: 'service-worker',
                target: 'content-script',
                payload: { tab_id: targetTabId },
                timestamp: new Date().toISOString()
              },
              (response: ExtensionResponse<PageObservation>) => {
                if (chrome.runtime.lastError) {
                  reject(new Error(`CONTENT_SCRIPT_UNAVAILABLE: ${chrome.runtime.lastError.message}`));
                } else if (!response || !response.success || !response.data) {
                  reject(new Error(response?.error || 'Failed to extract page observation'));
                } else {
                  resolve(response.data);
                }
              }
            );
          });

          await this.sendResponse(messageId, action, true, { observation });
          break;
        }

        // --- Phase 5 Semantic Intelligence Actions ---
        case BridgeAction.PAGE_SEMANTIC_OBSERVE: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available for semantic observation');
            }
          }

          if (typeof chrome === 'undefined' || !chrome.tabs) {
            throw new Error('Chrome tabs API not available');
          }

          const semanticModel = await new Promise<SemanticPageModel>((resolve, reject) => {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_SEMANTIC_OBSERVE,
                source: 'service-worker',
                target: 'content-script',
                payload: { tab_id: targetTabId, observation_id: payload.observation_id },
                timestamp: new Date().toISOString()
              },
              (response: ExtensionResponse<SemanticPageModel>) => {
                if (chrome.runtime.lastError) {
                  reject(new Error(`CONTENT_SCRIPT_UNAVAILABLE: ${chrome.runtime.lastError.message}`));
                } else if (!response || !response.success || !response.data) {
                  reject(new Error(response?.error || 'Failed to extract semantic model'));
                } else {
                  resolve(response.data);
                }
              }
            );
          });

          await this.sendResponse(messageId, action, true, { semantic_model: semanticModel });
          break;
        }

        case BridgeAction.PAGE_SEMANTIC_QUERY: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available for semantic query');
            }
          }

          if (typeof chrome === 'undefined' || !chrome.tabs) {
            throw new Error('Chrome tabs API not available');
          }

          const queryResult = await new Promise<QueryResult>((resolve, reject) => {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_SEMANTIC_QUERY,
                source: 'service-worker',
                target: 'content-script',
                payload: { tab_id: targetTabId, query: payload.query },
                timestamp: new Date().toISOString()
              },
              (response: ExtensionResponse<QueryResult>) => {
                if (chrome.runtime.lastError) {
                  reject(new Error(`CONTENT_SCRIPT_UNAVAILABLE: ${chrome.runtime.lastError.message}`));
                } else if (!response || !response.success || !response.data) {
                  reject(new Error(response?.error || 'Failed to execute semantic query'));
                } else {
                  resolve(response.data);
                }
              }
            );
          });

          await this.sendResponse(messageId, action, true, { result: queryResult });
          break;
        }

        case BridgeAction.PAGE_RESOLVE_ELEMENT: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available for element resolution');
            }
          }

          if (typeof chrome === 'undefined' || !chrome.tabs) {
            throw new Error('Chrome tabs API not available');
          }

          const resolveResult = await new Promise<ResolveResult>((resolve, reject) => {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_RESOLVE_ELEMENT,
                source: 'service-worker',
                target: 'content-script',
                payload: { tab_id: targetTabId, reference: payload.reference },
                timestamp: new Date().toISOString()
              },
              (response: ExtensionResponse<ResolveResult>) => {
                if (chrome.runtime.lastError) {
                  reject(new Error(`CONTENT_SCRIPT_UNAVAILABLE: ${chrome.runtime.lastError.message}`));
                } else if (!response || !response.success || !response.data) {
                  reject(new Error(response?.error || 'Failed to resolve element reference'));
                } else {
                  resolve(response.data);
                }
              }
            );
          });

          await this.sendResponse(messageId, action, true, { result: resolveResult });
          break;
        }

        case BridgeAction.PAGE_INVALIDATE_SEMANTIC_MODEL: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            targetTabId = active ? active.tab_id : 0;
          }

          if (targetTabId > 0 && typeof chrome !== 'undefined' && chrome.tabs) {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_INVALIDATE_SEMANTIC_MODEL,
                source: 'service-worker',
                target: 'content-script',
                timestamp: new Date().toISOString()
              },
              () => {}
            );
          }

          await this.sendResponse(messageId, action, true, { invalidated: true });
          break;
        }

        // --- Phase 6 Visual Page Intelligence Actions ---
        case BridgeAction.PAGE_CAPTURE_SCREENSHOT: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available for screenshot capture');
            }
          }

          const format = payload.format === 'jpeg' ? 'jpeg' : 'png';
          const privacyMode = (payload.privacy_mode || 'STANDARD') as PrivacyMode;
          const { dataUrl, width, height, scaled } = await browserController.captureScreenshot(targetTabId, {
            format,
            quality: 90
          });

          const screenshotMeta: ScreenshotMetadata = {
            id: `screen_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
            tab_id: targetTabId,
            url: (await browserController.getTab(targetTabId))?.url || '',
            width,
            height,
            device_pixel_ratio: 1.0,
            scroll_x: 0,
            scroll_y: 0,
            timestamp: new Date().toISOString(),
            viewport_only: true,
            scaled,
            original_width: width,
            original_height: height,
            format,
            bytes: dataUrl.length,
            privacy_mode: privacyMode,
            redacted_regions_count: 0,
            visual_version: 1
          };

          await this.sendResponse(messageId, action, true, {
            screenshot: screenshotMeta,
            data_url: dataUrl
          });
          break;
        }

        case BridgeAction.PAGE_VISUAL_OBSERVE:
        case BridgeAction.PAGE_GET_VISUAL_MODEL: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available for visual observation');
            }
          }

          const privacyMode = (payload.privacy_mode || 'STANDARD') as PrivacyMode;
          const { dataUrl, width, height, scaled } = await browserController.captureScreenshot(targetTabId, {
            format: 'png'
          });

          const screenshotMeta: Partial<ScreenshotMetadata> = {
            width,
            height,
            scaled,
            original_width: width,
            original_height: height,
            bytes: dataUrl.length
          };

          if (typeof chrome === 'undefined' || !chrome.tabs) {
            throw new Error('Chrome tabs API not available');
          }

          const visualModel = await new Promise<VisualPageModel>((resolve, reject) => {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_VISUAL_OBSERVE,
                source: 'service-worker',
                target: 'content-script',
                payload: {
                  tab_id: targetTabId,
                  screenshot: screenshotMeta,
                  privacy_mode: privacyMode
                },
                timestamp: new Date().toISOString()
              },
              (response: ExtensionResponse<VisualPageModel>) => {
                if (chrome.runtime.lastError) {
                  reject(new Error(`CONTENT_SCRIPT_UNAVAILABLE: ${chrome.runtime.lastError.message}`));
                } else if (!response || !response.success || !response.data) {
                  reject(new Error(response?.error || 'Failed to extract visual model'));
                } else {
                  resolve(response.data);
                }
              }
            );
          });

          await this.sendResponse(messageId, action, true, {
            visual_model: visualModel,
            screenshot_data_url: dataUrl
          });
          break;
        }

        case BridgeAction.PAGE_VISUAL_POINT_QUERY: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available for visual point query');
            }
          }

          if (typeof chrome === 'undefined' || !chrome.tabs) {
            throw new Error('Chrome tabs API not available');
          }

          const pointResult = await new Promise<PointQueryResult>((resolve, reject) => {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_VISUAL_POINT_QUERY,
                source: 'service-worker',
                target: 'content-script',
                payload: {
                  tab_id: targetTabId,
                  x: Number(payload.x),
                  y: Number(payload.y),
                  coordinate_system: payload.coordinate_system
                },
                timestamp: new Date().toISOString()
              },
              (response: ExtensionResponse<PointQueryResult>) => {
                if (chrome.runtime.lastError) {
                  reject(new Error(`CONTENT_SCRIPT_UNAVAILABLE: ${chrome.runtime.lastError.message}`));
                } else if (!response || !response.success || !response.data) {
                  reject(new Error(response?.error || 'Failed to execute visual point query'));
                } else {
                  resolve(response.data);
                }
              }
            );
          });

          await this.sendResponse(messageId, action, true, { result: pointResult });
          break;
        }

        case BridgeAction.PAGE_VISUAL_QUERY: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available for visual query');
            }
          }

          if (typeof chrome === 'undefined' || !chrome.tabs) {
            throw new Error('Chrome tabs API not available');
          }

          const queryResult = await new Promise<VisualQueryResult>((resolve, reject) => {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_VISUAL_QUERY,
                source: 'service-worker',
                target: 'content-script',
                payload: { tab_id: targetTabId, query: payload.query },
                timestamp: new Date().toISOString()
              },
              (response: ExtensionResponse<VisualQueryResult>) => {
                if (chrome.runtime.lastError) {
                  reject(new Error(`CONTENT_SCRIPT_UNAVAILABLE: ${chrome.runtime.lastError.message}`));
                } else if (!response || !response.success || !response.data) {
                  reject(new Error(response?.error || 'Failed to execute visual query'));
                } else {
                  resolve(response.data);
                }
              }
            );
          });

          await this.sendResponse(messageId, action, true, { result: queryResult });
          break;
        }

        case BridgeAction.PAGE_INVALIDATE_VISUAL_MODEL: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            targetTabId = active ? active.tab_id : 0;
          }

          if (targetTabId > 0 && typeof chrome !== 'undefined' && chrome.tabs) {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_INVALIDATE_VISUAL_MODEL,
                source: 'service-worker',
                target: 'content-script',
                timestamp: new Date().toISOString()
              },
              () => {}
            );
          }

          await this.sendResponse(messageId, action, true, { invalidated: true });
          break;
        }

        // --- Phase 7 Unified Browser World Model Actions ---
        case 'page.getWorldPageState':
        case BridgeAction.WORLD_GET_CURRENT: {
          let targetTabId = Number(payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available for world page state');
            }
          }

          if (typeof chrome === 'undefined' || !chrome.tabs) {
            throw new Error('Chrome tabs API not available');
          }

          const pageData = await new Promise<{
            page_state: WorldPageState;
            frame_tree: FrameTree;
            world_elements: WorldElement[];
            observation: PageObservation;
            semantic_model: SemanticPageModel;
            visual_model: VisualPageModel;
          }>((resolve, reject) => {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_GET_WORLD_PAGE_STATE,
                source: 'service-worker',
                target: 'content-script',
                payload: { tab_id: targetTabId },
                timestamp: new Date().toISOString()
              },
              (response: ExtensionResponse<{
                page_state: WorldPageState;
                frame_tree: FrameTree;
                world_elements: WorldElement[];
                observation: PageObservation;
                semantic_model: SemanticPageModel;
                visual_model: VisualPageModel;
              }>) => {
                if (chrome.runtime.lastError) {
                  reject(new Error(`CONTENT_SCRIPT_UNAVAILABLE: ${chrome.runtime.lastError.message}`));
                } else if (!response || !response.success || !response.data) {
                  reject(new Error(response?.error || 'Failed to extract world page state'));
                } else {
                  resolve(response.data);
                }
              }
            );
          });

          await this.sendResponse(messageId, action, true, pageData);
          break;
        }

        case BridgeAction.WORLD_RESOLVE_ELEMENT: {
          let targetTabId = Number(payload.tab_id);
          const ref = payload.reference as WorldElementRef;

          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available for world element resolution');
            }
          }

          if (typeof chrome === 'undefined' || !chrome.tabs) {
            throw new Error('Chrome tabs API not available');
          }

          const resolution = await new Promise<WorldElementResolution>((resolve, reject) => {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.PAGE_RESOLVE_WORLD_ELEMENT,
                source: 'service-worker',
                target: 'content-script',
                payload: { tab_id: targetTabId, reference: ref },
                timestamp: new Date().toISOString()
              },
              (response: ExtensionResponse<WorldElementResolution>) => {
                if (chrome.runtime.lastError) {
                  reject(new Error(`CONTENT_SCRIPT_UNAVAILABLE: ${chrome.runtime.lastError.message}`));
                } else if (!response || !response.success || !response.data) {
                  reject(new Error(response?.error || 'Failed to resolve world element'));
                } else {
                  resolve(response.data);
                }
              }
            );
          });

          await this.sendResponse(messageId, action, true, { resolution });
          break;
        }

        // --- Phase 8 Safe Browser Action Engine Actions ---
        case BridgeAction.ACTION_EXECUTE: {
          const intent = payload.intent as ActionIntent;
          if (!intent) {
            throw new Error('INVALID_ACTION: Missing action intent payload');
          }

          let targetTabId = Number(intent.tab_id || payload.tab_id);
          if (!targetTabId || targetTabId <= 0) {
            const active = await browserController.getActiveTab();
            if (active && active.tab_id > 0) {
              targetTabId = active.tab_id;
            } else {
              throw new Error('NO_ACTIVE_TAB: No active tab available for action execution');
            }
          }

          // If action is NAVIGATE, execute directly through BrowserController
          if (intent.type === 'NAVIGATE') {
            const targetUrl = String(intent.parameters?.url || intent.target?.url || '');
            const navResult = await browserController.navigate(targetTabId, targetUrl);
            await this.sendResponse(messageId, action, true, {
              status: navResult.status === 'COMPLETED' ? 'SUCCESS' : 'FAILED',
              message: `Navigated tab ${targetTabId} to ${targetUrl}`,
              navigation_result: navResult
            });
            break;
          }

          // If action is WAIT, execute timeout
          if (intent.type === 'WAIT') {
            const durationMs = Math.min(Math.max(Number(intent.parameters?.duration_ms ?? 1000), 50), 30000);
            await new Promise((res) => setTimeout(res, durationMs));
            await this.sendResponse(messageId, action, true, {
              status: 'SUCCESS',
              message: `Waited for ${durationMs}ms`
            });
            break;
          }

          // Otherwise dispatch to Content Script via MessageAction.ACTION_EXECUTE_DOM
          if (typeof chrome === 'undefined' || !chrome.tabs) {
            throw new Error('Chrome tabs API not available');
          }

          const actionExecResult = await new Promise<{ status: ActionStatus; message?: string }>((resolve, reject) => {
            chrome.tabs.sendMessage(
              targetTabId,
              {
                action: MessageAction.ACTION_EXECUTE_DOM,
                source: 'service-worker',
                target: 'content-script',
                payload: { intent },
                timestamp: new Date().toISOString()
              },
              (response: ExtensionResponse<{ status: ActionStatus; message?: string }>) => {
                if (chrome.runtime.lastError) {
                  reject(new Error(`CONTENT_SCRIPT_UNAVAILABLE: ${chrome.runtime.lastError.message}`));
                } else if (!response || !response.success || !response.data) {
                  reject(new Error(response?.error || 'Failed to execute DOM action'));
                } else {
                  resolve(response.data);
                }
              }
            );
          });

          await this.sendResponse(messageId, action, true, actionExecResult);
          break;
        }

        default: {
          logger.warn(`Unsupported request action: ${action}`);
          await this.sendResponse(messageId, action, false, {}, {
            code: 'UNSUPPORTED_ACTION',
            message: `Action '${action}' is not supported`
          });
          break;
        }
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      const errCode = errMsg.includes('TAB_NOT_FOUND') ? 'TAB_NOT_FOUND' : (errMsg.includes('INVALID_URL') ? 'INVALID_URL' : 'EXECUTION_ERROR');
      await this.sendResponse(messageId, action, false, {}, {
        code: errCode,
        message: errMsg
      });
    }
  }

  /**
   * Stream a real-time browser event over the WebSocket bridge to MATRIOSHAI
   */
  public sendEvent<TEvent>(action: string, payload: TEvent): void {
    if (this.state !== 'READY' || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const eventEnvelope: BridgeEnvelope<TEvent> = {
      protocol_version: PROTOCOL_VERSION,
      message_id: `evt_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      type: 'event',
      action,
      timestamp: new Date().toISOString(),
      payload
    };

    this.sendRaw(eventEnvelope);
  }

  /**
   * Send a response envelope back to the server
   */
  public async sendResponse<TRes = Record<string, unknown>>(
    messageId: string,
    action: string,
    success: boolean,
    payload: TRes,
    error?: { code: string; message: string }
  ): Promise<void> {
    const envelope: BridgeEnvelope<TRes> = {
      protocol_version: PROTOCOL_VERSION,
      message_id: messageId,
      type: 'response',
      action,
      timestamp: new Date().toISOString(),
      success,
      payload,
      error
    };
    this.sendRaw(envelope);
  }

  /**
   * Send a request envelope from extension to server and await correlated response
   */
  public async sendRequest<TReq, TRes>(
    action: string,
    payload: TReq,
    timeoutMs: number = BRIDGE_CONFIG.REQUEST_TIMEOUT_MS
  ): Promise<TRes> {
    if (this.state !== 'READY' || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error(`Bridge is not ready (State: ${this.state})`);
    }

    const messageId = `ext_req_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

    return new Promise<TRes>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(messageId);
        logger.warn(`Request '${action}' (${messageId}) timed out after ${timeoutMs}ms`);
        reject(new Error(`REQUEST_TIMEOUT: Action '${action}' timed out waiting for server response`));
      }, timeoutMs);

      this.pendingRequests.set(messageId, {
        messageId,
        action,
        resolve: resolve as (val: unknown) => void,
        reject,
        timer
      });

      const envelope: BridgeEnvelope<TReq> = {
        protocol_version: PROTOCOL_VERSION,
        message_id: messageId,
        type: 'request',
        action,
        timestamp: new Date().toISOString(),
        payload
      };

      this.sendRaw(envelope);
    });
  }

  private sendRaw(data: BridgeEnvelope<unknown>): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(data));
      } catch (err) {
        logger.error('Failed to send WebSocket payload', err);
      }
    } else {
      logger.debug('Cannot send payload: WebSocket is not open', { state: this.state });
    }
  }

  /**
   * Exponential Backoff Reconnection Scheduler
   */
  private scheduleReconnect(): void {
    this.clearReconnectTimer();

    logger.info(`Scheduling bridge reconnect in ${this.reconnectDelay}ms...`);

    this.reconnectTimer = setTimeout(() => {
      if (!this.intentionalClose && this.state !== 'READY' && this.state !== 'CONNECTING') {
        this.connect().catch((err) => {
          logger.warn('Reconnect attempt error', err);
        });
      }
    }, this.reconnectDelay);

    // Apply exponential backoff with ceiling
    this.reconnectDelay = Math.min(
      this.reconnectDelay * BRIDGE_CONFIG.RECONNECT_BACKOFF_FACTOR,
      BRIDGE_CONFIG.RECONNECT_MAX_DELAY_MS
    );
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private cleanupPendingRequests(reason: string): void {
    for (const pending of this.pendingRequests.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error(`Bridge request cancelled: ${reason}`));
    }
    this.pendingRequests.clear();
  }
}

// Global Singleton Bridge Client Instance
export const browserBridge = new BrowserBridgeClient();
