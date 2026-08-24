/**
 * MATRIOSHAI Background Service Worker (Phase 1, Phase 2 & Phase 3)
 *
 * Responsibilities:
 * - Extension lifecycle management (install, update, startup)
 * - Service worker health & readiness state tracking
 * - Background WebSocket Bridge client lifecycle (connect, reconnect, heartbeat)
 * - Browser Event Engine initialization for real-time Chrome event streaming
 * - Internal message routing for diagnostic queries & status synchronization
 * - Error recording and safe state persistence
 */

import { browserBridge } from '../core/browser-bridge';
import { browserController } from '../core/browser-controller';
import { browserEventEngine } from '../core/event-engine';
import { extensionState } from '../core/extension-state';
import { EXTENSION_NAME, EXTENSION_VERSION, PROTOCOL_VERSION } from '../shared/constants';
import { createScopedLogger } from '../shared/logger';
import {
  MessageAction,
  type ExtensionMessage,
  type ExtensionResponse,
  type DiagnosticSummary,
  type IHeartbeatService
} from '../shared/types';

const logger = createScopedLogger('SERVICE_WORKER');

const startTime = Date.now();

/**
 * Initialize Service Worker State & Handlers
 */
async function initializeServiceWorker(): Promise<void> {
  logger.info(`Initializing ${EXTENSION_NAME} Service Worker v${EXTENSION_VERSION}...`);

  try {
    await extensionState.initialize();
    await extensionState.updateState({
      installed: true,
      serviceWorkerReady: true,
      extensionVersion: EXTENSION_VERSION
    });

    // Initialize Phase 3 Event Engine
    browserEventEngine.initialize();

    // Sync initial browser state snapshot
    await browserController.syncStateSnapshot();

    logger.info('Service Worker initialization complete. Status: READY');

    // Establish Phase 2 & 3 Browser Bridge connection to localhost backend
    browserBridge.connect().catch((err) => {
      logger.debug('Initial bridge connection attempt deferred', err);
    });
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    logger.error('Failed to initialize Service Worker', errorMsg);
    await extensionState.recordError(errorMsg);
  }
}

// ----------------------------------------------------------------------------
// LIFECYCLE EVENT LISTENERS & MESSAGE DISPATCHER
// ----------------------------------------------------------------------------

if (typeof chrome !== 'undefined' && chrome.runtime) {
  if (chrome.runtime.onInstalled) {
    chrome.runtime.onInstalled.addListener(async (details) => {
      logger.info(`Extension lifecycle event: onInstalled (reason: ${details.reason})`);

      if (details.reason === 'install') {
        logger.info(`Fresh installation of ${EXTENSION_NAME} v${EXTENSION_VERSION}`);
        await extensionState.updateState({ installed: true });
      } else if (details.reason === 'update') {
        logger.info(`Extension updated from ${details.previousVersion} to ${EXTENSION_VERSION}`);
      }

      browserEventEngine.initialize();
      browserBridge.connect().catch(() => {});
    });
  }

  if (chrome.runtime.onStartup) {
    chrome.runtime.onStartup.addListener(async () => {
      logger.info('Extension lifecycle event: onStartup — browser launched');
      await extensionState.setServiceWorkerReady(true);
      browserEventEngine.initialize();
      browserBridge.connect().catch(() => {});
    });
  }

  if (chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((message: ExtensionMessage, sender, sendResponse) => {
      logger.debug('Received internal message', { action: message.action, source: message.source });

      handleIncomingMessage(message, sender)
        .then((response) => {
          sendResponse(response);
        })
        .catch((err) => {
          const errMsg = err instanceof Error ? err.message : String(err);
          logger.error('Error handling message', { action: message.action, error: errMsg });
          sendResponse({
            success: false,
            error: errMsg,
            timestamp: new Date().toISOString()
          } as ExtensionResponse);
        });

      return true;
    });
  }
}

/**
 * Handle incoming internal extension messages
 */
async function handleIncomingMessage(
  message: ExtensionMessage,
  sender: chrome.runtime.MessageSender
): Promise<ExtensionResponse> {
  const timestamp = new Date().toISOString();

  switch (message.action) {
    case MessageAction.PING: {
      return {
        success: true,
        data: {
          pong: true,
          service: 'service-worker',
          version: EXTENSION_VERSION,
          uptimeMs: Date.now() - startTime,
          bridgeState: browserBridge.getState(),
          bridgeAuthenticated: browserBridge.isAuthenticated()
        },
        timestamp
      };
    }

    case MessageAction.CONTENT_SCRIPT_READY: {
      const tabId = sender.tab?.id ?? null;
      logger.info('Content script reported ready', { tabId, url: sender.tab?.url });
      await extensionState.setContentScriptReady(true);
      if (tabId) {
        await extensionState.updateState({ activeTabId: tabId });
      }
      return {
        success: true,
        data: { acknowledged: true },
        timestamp
      };
    }

    case MessageAction.GET_STATUS:
    case MessageAction.REFRESH_STATUS: {
      if (browserBridge.getState() === 'DISCONNECTED' || browserBridge.getState() === 'ERROR') {
        browserBridge.connect().catch(() => {});
      }

      await browserController.syncStateSnapshot();
      const summary = await buildDiagnosticSummary();
      return {
        success: true,
        data: summary,
        timestamp
      };
    }

    case MessageAction.BRIDGE_CONNECT: {
      const connected = await browserBridge.connect();
      return {
        success: connected,
        data: { state: browserBridge.getState() },
        timestamp
      };
    }

    case MessageAction.BRIDGE_DISCONNECT: {
      await browserBridge.disconnect();
      return {
        success: true,
        data: { state: browserBridge.getState() },
        timestamp
      };
    }

    case MessageAction.RECORD_ERROR: {
      const errorMsg = (message.payload as { error?: string })?.error || 'Unknown error reported';
      await extensionState.recordError(errorMsg);
      return {
        success: true,
        data: { recorded: true },
        timestamp
      };
    }

    default: {
      logger.warn('Unhandled message action', message.action);
      return {
        success: false,
        error: `Unknown action: ${message.action}`,
        timestamp
      };
    }
  }
}

/**
 * Build safe diagnostic status summary for popup/diagnostics
 */
async function buildDiagnosticSummary(): Promise<DiagnosticSummary> {
  const state = extensionState.getState();
  const activeTab = await browserController.getActiveTab();

  return {
    extensionVersion: EXTENSION_VERSION,
    environment: state.environment,
    installed: state.installed,
    serviceWorkerStatus: state.serviceWorkerReady ? 'ready' : 'initializing',
    contentScriptStatus: state.contentScriptReady ? 'ready' : 'standby',
    serviceWorkerUptimeMs: Date.now() - startTime,
    lastHealthCheck: new Date().toISOString(),
    activeTab: activeTab
      ? {
          id: activeTab.tab_id,
          url: activeTab.url,
          title: activeTab.title
        }
      : null,
    lastError: state.lastError,

    // Phase 2 Bridge Diagnostics
    bridge: {
      state: browserBridge.getState(),
      authenticated: browserBridge.isAuthenticated(),
      sessionId: browserBridge.getSessionId(),
      latencyMs: browserBridge.getLatencyMs(),
      protocolVersion: PROTOCOL_VERSION,
      lastHeartbeat: browserBridge.getLastHeartbeat(),
      capabilities: browserBridge.getAdvertisedCapabilities()
    },

    // Phase 3 Browser Control Diagnostics
    browser: {
      browserId: browserController.getBrowserId(),
      windowsCount: state.windowsCount,
      tabsCount: state.tabsCount,
      activeTabId: activeTab?.tab_id ?? null,
      activeUrl: activeTab?.url ?? null,
      navigationState: state.navigationState,
      lastCommand: state.lastCommand,
      lastResult: state.lastCommandResult
    }
  };
}

// ----------------------------------------------------------------------------
// PHASE 2+ ARCHITECTURAL PLACEHOLDERS (STRUCTURAL CONTRACTS ONLY)
// ----------------------------------------------------------------------------

export class PlaceholderHeartbeatService implements IHeartbeatService {
  start(_intervalMs: number): void {
    logger.debug('PlaceholderHeartbeatService: start');
  }
  stop(): void {
    logger.debug('PlaceholderHeartbeatService: stop');
  }
  async ping(): Promise<boolean> {
    return true;
  }
}

// Bootstrap Service Worker in Chrome runtime environment
if (typeof chrome !== 'undefined' && chrome.runtime) {
  initializeServiceWorker().catch((err) => {
    logger.error('Critical Service Worker startup error', err);
  });
}
