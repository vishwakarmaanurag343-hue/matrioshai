/**
 * MATRIOSHAI Content Script (Phases 1-5)
 *
 * Responsibilities:
 * - Safe, isolated lifecycle initialization
 * - Responds to internal diagnostic ping requests
 * - Executes Phase 4 Page Observation Engine on demand
 * - Executes Phase 5 Semantic Page & Accessibility Intelligence Analyzer on demand
 * - Executes Phase 5 Semantic Queries & Element Reference Resolutions
 * - Tracks DOM mutations for model staleness detection
 * - Notifies background service worker of content-script readiness
 */

import { EXTENSION_NAME, EXTENSION_VERSION } from '../shared/constants';
import { createScopedLogger } from '../shared/logger';
import {
  MessageAction,
  type ExtensionMessage,
  type ExtensionResponse,
  type PageObservation,
  type SemanticPageModel,
  type SemanticQuery,
  type SemanticElementRef,
  type QueryResult,
  type ResolveResult,
  type VisualPageModel,
  type VisualQuery,
  type VisualQueryResult,
  type PointQueryResult,
  type ScreenshotMetadata,
  type PrivacyMode,
  type CoordinateSystem,
  type WorldPageState,
  type FrameTree,
  type WorldElement,
  type WorldElementRef,
  type WorldElementResolution,
  type ActionIntent,
  type ActionStatus
} from '../shared/types';
import { pageObservationEngine } from './observation-engine';
import { semanticPageAnalyzer } from './semantic-analyzer';
import { semanticQueryEngine } from './semantic-query-engine';
import { visualEngine } from './visual-engine';
import { visualQueryEngine } from './visual-query-engine';
import { worldModelExtractor } from './world-model-extractor';
import { actionDomExecutor } from './action-dom-executor';
import { domMutationTracker } from './mutation-tracker';

const logger = createScopedLogger('CONTENT_SCRIPT');

// Guard against duplicate injections within the same context
const INJECTION_FLAG = '__MATRIOSHAI_CONTENT_SCRIPT_INJECTED__';

interface MatrioshaiWindow extends Window {
  [INJECTION_FLAG]?: boolean;
}

function initializeContentScript(): void {
  const customWindow = window as MatrioshaiWindow;
  if (customWindow[INJECTION_FLAG]) {
    logger.debug('Content script already injected in this frame. Skipping duplicate init.');
    return;
  }
  customWindow[INJECTION_FLAG] = true;

  logger.info(`${EXTENSION_NAME} Content Script v${EXTENSION_VERSION} initialized safely`, {
    location: window.location.origin,
    readyState: document.readyState
  });

  notifyServiceWorkerReady();
  setupMessageListener();
  domMutationTracker.start();
}

/**
 * Notify the Service Worker that this content script has loaded and is ready.
 */
function notifyServiceWorkerReady(): void {
  if (typeof chrome === 'undefined' || !chrome.runtime || !chrome.runtime.sendMessage) {
    logger.debug('Chrome runtime messaging unavailable in this context.');
    return;
  }

  const message: ExtensionMessage = {
    action: MessageAction.CONTENT_SCRIPT_READY,
    source: 'content-script',
    target: 'service-worker',
    payload: {
      url: window.location.href,
      readyState: document.readyState
    },
    timestamp: new Date().toISOString()
  };

  chrome.runtime.sendMessage(message, (response: ExtensionResponse) => {
    if (chrome.runtime.lastError) {
      logger.debug('Service Worker not yet ready to acknowledge content script', chrome.runtime.lastError.message);
    } else {
      logger.debug('Service Worker acknowledged content script readiness', response);
    }
  });
}

/**
 * Listen for internal queries from Popup or Service Worker
 */
function setupMessageListener(): void {
  if (typeof chrome === 'undefined' || !chrome.runtime || !chrome.runtime.onMessage) {
    return;
  }

  chrome.runtime.onMessage.addListener((message: ExtensionMessage, _sender, sendResponse) => {
    // 1. Health Ping
    if (message.action === MessageAction.PING) {
      const response: ExtensionResponse = {
        success: true,
        data: {
          pong: true,
          service: 'content-script',
          version: EXTENSION_VERSION,
          readyState: document.readyState,
          origin: window.location.origin
        },
        timestamp: new Date().toISOString()
      };
      sendResponse(response);
      return false;
    }

    // 2. Phase 4 Page Observation
    if (message.action === MessageAction.PAGE_OBSERVE) {
      try {
        const tabId = (message.payload as { tab_id?: number })?.tab_id ?? 0;
        const observation = pageObservationEngine.extractPageObservation(tabId);
        const response: ExtensionResponse<PageObservation> = {
          success: true,
          data: observation,
          timestamp: new Date().toISOString()
        };
        sendResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        sendResponse({ success: false, error: errMsg, timestamp: new Date().toISOString() });
      }
      return false;
    }

    // 3. Phase 5 Semantic Page Observation
    if (message.action === MessageAction.PAGE_SEMANTIC_OBSERVE) {
      try {
        const p = message.payload as { tab_id?: number; observation_id?: string };
        const tabId = p?.tab_id ?? 0;
        const obsId = p?.observation_id;
        const semanticModel = semanticPageAnalyzer.analyzePage(tabId, obsId);
        const response: ExtensionResponse<SemanticPageModel> = {
          success: true,
          data: semanticModel,
          timestamp: new Date().toISOString()
        };
        sendResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        sendResponse({ success: false, error: errMsg, timestamp: new Date().toISOString() });
      }
      return false;
    }

    // 4. Phase 5 Semantic Query
    if (message.action === MessageAction.PAGE_SEMANTIC_QUERY) {
      try {
        const p = message.payload as { tab_id?: number; query: SemanticQuery };
        let model = semanticPageAnalyzer.getLastModel();
        if (!model || model.is_stale) {
          model = semanticPageAnalyzer.analyzePage(p?.tab_id ?? 0);
        }
        const queryResult: QueryResult = semanticQueryEngine.query(model, p.query);
        const response: ExtensionResponse<QueryResult> = {
          success: true,
          data: queryResult,
          timestamp: new Date().toISOString()
        };
        sendResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        sendResponse({ success: false, error: errMsg, timestamp: new Date().toISOString() });
      }
      return false;
    }

    // 5. Phase 5 Element Reference Resolution
    if (message.action === MessageAction.PAGE_RESOLVE_ELEMENT) {
      try {
        const p = message.payload as { tab_id?: number; reference: SemanticElementRef };
        let model = semanticPageAnalyzer.getLastModel();
        if (!model || model.is_stale) {
          model = semanticPageAnalyzer.analyzePage(p?.tab_id ?? 0);
        }
        const resolveResult: ResolveResult = semanticQueryEngine.resolveElement(model, p.reference);
        const response: ExtensionResponse<ResolveResult> = {
          success: true,
          data: resolveResult,
          timestamp: new Date().toISOString()
        };
        sendResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        sendResponse({ success: false, error: errMsg, timestamp: new Date().toISOString() });
      }
      return false;
    }

    // 6. Phase 5 Invalidate Model
    if (message.action === MessageAction.PAGE_INVALIDATE_SEMANTIC_MODEL) {
      semanticPageAnalyzer.invalidateModel();
      sendResponse({ success: true, data: { invalidated: true }, timestamp: new Date().toISOString() });
      return false;
    }

    // 7. Phase 6 Visual Page Observation
    if (message.action === MessageAction.PAGE_VISUAL_OBSERVE || message.action === MessageAction.PAGE_GET_VISUAL_MODEL) {
      try {
        const p = message.payload as {
          tab_id?: number;
          screenshot?: Partial<ScreenshotMetadata>;
          privacy_mode?: PrivacyMode;
        };
        const tabId = p?.tab_id ?? 0;
        const privacyMode = p?.privacy_mode || 'STANDARD';
        const visualModel = visualEngine.generateVisualModel(tabId, p?.screenshot, privacyMode);
        const response: ExtensionResponse<VisualPageModel> = {
          success: true,
          data: visualModel,
          timestamp: new Date().toISOString()
        };
        sendResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        sendResponse({ success: false, error: errMsg, timestamp: new Date().toISOString() });
      }
      return false;
    }

    // 8. Phase 6 Visual Point Query
    if (message.action === MessageAction.PAGE_VISUAL_POINT_QUERY) {
      try {
        const p = message.payload as {
          tab_id?: number;
          x: number;
          y: number;
          coordinate_system?: CoordinateSystem;
          privacy_mode?: PrivacyMode;
        };
        let model = visualEngine.getLastModel();
        if (!model || model.is_stale) {
          model = visualEngine.generateVisualModel(p?.tab_id ?? 0, undefined, p?.privacy_mode || 'STANDARD');
        }
        const pointResult: PointQueryResult = visualQueryEngine.queryPoint(
          model,
          p.x,
          p.y,
          p.coordinate_system || 'DOM_VIEWPORT'
        );
        const response: ExtensionResponse<PointQueryResult> = {
          success: true,
          data: pointResult,
          timestamp: new Date().toISOString()
        };
        sendResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        sendResponse({ success: false, error: errMsg, timestamp: new Date().toISOString() });
      }
      return false;
    }

    // 9. Phase 6 Visual Query
    if (message.action === MessageAction.PAGE_VISUAL_QUERY) {
      try {
        const p = message.payload as {
          tab_id?: number;
          query: VisualQuery;
          privacy_mode?: PrivacyMode;
        };
        let model = visualEngine.getLastModel();
        if (!model || model.is_stale) {
          model = visualEngine.generateVisualModel(p?.tab_id ?? 0, undefined, p?.privacy_mode || 'STANDARD');
        }
        const queryResult: VisualQueryResult = visualQueryEngine.query(model, p.query);
        const response: ExtensionResponse<VisualQueryResult> = {
          success: true,
          data: queryResult,
          timestamp: new Date().toISOString()
        };
        sendResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        sendResponse({ success: false, error: errMsg, timestamp: new Date().toISOString() });
      }
      return false;
    }

    // 10. Phase 6 Invalidate Visual Model
    if (message.action === MessageAction.PAGE_INVALIDATE_VISUAL_MODEL) {
      visualEngine.invalidateModel();
      sendResponse({ success: true, data: { invalidated: true }, timestamp: new Date().toISOString() });
      return false;
    }

    // 11. Phase 7 Get World Page State & Frame Tree
    if (message.action === MessageAction.PAGE_GET_WORLD_PAGE_STATE) {
      try {
        const p = message.payload as { tab_id?: number };
        const tabId = p?.tab_id ?? 0;

        const observation = pageObservationEngine.extractPageObservation(tabId);
        let semanticModel = semanticPageAnalyzer.getLastModel();
        if (!semanticModel || semanticModel.is_stale) {
          semanticModel = semanticPageAnalyzer.analyzePage(tabId, observation.observation_id);
        }

        let visualModel = visualEngine.getLastModel();
        if (!visualModel || visualModel.is_stale) {
          visualModel = visualEngine.generateVisualModel(tabId, undefined, 'STANDARD');
        }

        const pageState: WorldPageState = worldModelExtractor.extractWorldPageState(
          tabId,
          observation,
          semanticModel,
          visualModel
        );

        const frameTree: FrameTree = worldModelExtractor.extractFrameTree(tabId);
        const worldElements: WorldElement[] = worldModelExtractor.synthesizeWorldElements(
          semanticModel,
          visualModel
        );

        const response: ExtensionResponse<{
          page_state: WorldPageState;
          frame_tree: FrameTree;
          world_elements: WorldElement[];
          observation: PageObservation;
          semantic_model: SemanticPageModel;
          visual_model: VisualPageModel;
        }> = {
          success: true,
          data: {
            page_state: pageState,
            frame_tree: frameTree,
            world_elements: worldElements,
            observation,
            semantic_model: semanticModel,
            visual_model: visualModel
          },
          timestamp: new Date().toISOString()
        };
        sendResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        sendResponse({ success: false, error: errMsg, timestamp: new Date().toISOString() });
      }
      return false;
    }

    // 12. Phase 7 Resolve World Element
    if (message.action === MessageAction.PAGE_RESOLVE_WORLD_ELEMENT) {
      try {
        const p = message.payload as { tab_id?: number; reference: WorldElementRef };
        const tabId = p?.tab_id ?? 0;

        let semanticModel = semanticPageAnalyzer.getLastModel();
        if (!semanticModel || semanticModel.is_stale) {
          semanticModel = semanticPageAnalyzer.analyzePage(tabId);
        }

        const visualModel = visualEngine.getLastModel();
        const worldElements = worldModelExtractor.synthesizeWorldElements(semanticModel, visualModel);
        const resolution = worldModelExtractor.resolveWorldElement(p.reference, worldElements);

        const response: ExtensionResponse<WorldElementResolution> = {
          success: true,
          data: resolution,
          timestamp: new Date().toISOString()
        };
        sendResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        sendResponse({ success: false, error: errMsg, timestamp: new Date().toISOString() });
      }
      return false;
    }

    // 13. Phase 8 Execute Safe DOM Action
    if (message.action === MessageAction.ACTION_EXECUTE_DOM) {
      try {
        const p = message.payload as { intent: ActionIntent };
        const result = actionDomExecutor.executeAction(p.intent);

        const response: ExtensionResponse<{ status: ActionStatus; message?: string }> = {
          success: result.status === 'SUCCESS' || result.status === 'NO_OP' || result.status === 'WOULD_EXECUTE',
          data: result,
          error: result.status !== 'SUCCESS' && result.status !== 'NO_OP' && result.status !== 'WOULD_EXECUTE' ? result.message : undefined,
          timestamp: new Date().toISOString()
        };
        sendResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : String(err);
        sendResponse({ success: false, error: errMsg, timestamp: new Date().toISOString() });
      }
      return false;
    }

    return false;
  });
}

try {
  initializeContentScript();
} catch (err) {
  logger.error('Content script initialization error', err);
}
