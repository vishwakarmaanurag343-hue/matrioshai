/**
 * MATRIOSHAI Browser Agent Extension — Constants (Phase 1, Phase 2 & Phase 3)
 */

export const EXTENSION_NAME = 'MATRIOSHAI Browser Agent';
export const EXTENSION_VERSION = '0.1.0';
export const EXTENSION_ID_TAG = 'matrioshai-extension';
export const PROTOCOL_VERSION = '1.0';

export const BRIDGE_CONFIG = {
  WS_ENDPOINT: 'ws://127.0.0.1:8000/api/v1/browser/bridge/ws',
  HTTP_TOKEN_ENDPOINT: 'http://127.0.0.1:8000/api/v1/browser/bridge/token',
  HEARTBEAT_INTERVAL_MS: 10000,
  REQUEST_TIMEOUT_MS: 5000,
  RECONNECT_INITIAL_DELAY_MS: 1000,
  RECONNECT_MAX_DELAY_MS: 16000,
  RECONNECT_BACKOFF_FACTOR: 2
} as const;

export const PHASE_2_CAPABILITIES = [
  'bridge.auth',
  'bridge.health',
  'bridge.info',
  'bridge.ping',
  'bridge.status'
] as const;

export const PHASE_3_CAPABILITIES = [
  ...PHASE_2_CAPABILITIES,
  'browser.getStatus',
  'browser.getWindows',
  'browser.getTabs',
  'browser.getActiveTab',
  'browser.openTab',
  'browser.closeTab',
  'browser.switchTab',
  'browser.navigate',
  'browser.reload',
  'browser.goBack',
  'browser.goForward',
  'browser.waitForNavigation',
  'browser.refreshState'
] as const;

export const PHASE_4_CAPABILITIES = [
  ...PHASE_3_CAPABILITIES,
  'page.observe'
] as const;

export const PHASE_5_CAPABILITIES = [
  ...PHASE_4_CAPABILITIES,
  'page.semanticObserve',
  'page.semanticQuery',
  'page.resolveElement',
  'page.getSemanticModel',
  'page.invalidateSemanticModel'
] as const;

export const PHASE_6_CAPABILITIES = [
  ...PHASE_5_CAPABILITIES,
  'page.captureScreenshot',
  'page.visualObserve',
  'page.getVisualModel',
  'page.getVisualElement',
  'page.visualPointQuery',
  'page.visualQuery',
  'page.invalidateVisualModel'
] as const;

export const PHASE_7_CAPABILITIES = [
  ...PHASE_6_CAPABILITIES,
  'world.getCurrent',
  'world.getSnapshot',
  'world.getDiff',
  'world.query',
  'world.resolveElement',
  'world.validate',
  'world.reconcile',
  'world.invalidate',
  'world.health',
  'world.getHistory'
] as const;

export const PHASE_8_CAPABILITIES = [
  ...PHASE_7_CAPABILITIES,
  'action.execute',
  'action.cancel',
  'action.confirm',
  'action.queueStatus',
  'action.validate'
] as const;

export const PHASE_9_CAPABILITIES = [
  ...PHASE_8_CAPABILITIES,
  'verification.verify',
  'verification.getResult',
  'recovery.recommend',
  'checkpoint.create',
  'checkpoint.list',
  'intervention.resolve'
] as const;

export const PHASE_10_CAPABILITIES = [
  ...PHASE_9_CAPABILITIES,
  'agent.createGoal',
  'agent.startTask',
  'agent.pauseTask',
  'agent.resumeTask',
  'agent.abortTask',
  'agent.getTask',
  'agent.getEvents',
  'agent.submitClarification'
] as const;

export const PHASE_12_CAPABILITIES = [
  ...PHASE_10_CAPABILITIES,
  'transaction.create',
  'transaction.selectOption',
  'transaction.prepareReview',
  'transaction.confirm',
  'transaction.commit',
  'transaction.cancel',
  'transaction.get',
  'transaction.getReceipt'
] as const;

export const PHASE_13_CAPABILITIES = [
  ...PHASE_12_CAPABILITIES,
  'security.evaluate',
  'security.grantPermission',
  'security.revokePermission',
  'security.emergencyStop',
  'security.setTakeover',
  'security.getState',
  'security.getAuditLogs'
] as const;

export const PHASE_14_CAPABILITIES = [
  ...PHASE_13_CAPABILITIES,
  'runtime.health',
  'runtime.status',
  'runtime.supervisor',
  'runtime.metrics',
  'runtime.events',
  'runtime.deadLetterQueue',
  'chaos.injectFault'
] as const;

export const WORLD_MODEL_CONFIG = {
  MAX_SNAPSHOTS: 20,
  SNAPSHOT_TTL_MS: 300000,
  DEBOUNCE_MS: 200,
  MAX_NAVIGATION_HISTORY: 50
} as const;

export const VERIFICATION_CONFIG = {
  DEFAULT_INITIAL_DELAY_MS: 100,
  DEFAULT_POLL_INTERVAL_MS: 250,
  DEFAULT_MAX_TIMEOUT_MS: 5000,
  LONG_MAX_TIMEOUT_MS: 15000,
  MAX_RECOVERY_ATTEMPTS: 3
} as const;

export const AGENT_CONFIG = {
  MAX_ITERATIONS_PER_TASK: 30,
  MAX_PLANNER_CALLS: 20,
  MAX_EXPLORATION_ACTIONS: 5,
  DEFAULT_TASK_TIMEOUT_MS: 120000
} as const;

export const TRANSACTION_CONFIG = {
  DEFAULT_CONFIRMATION_TIMEOUT_MS: 300000,
  DEFAULT_PRICE_DRIFT_THRESHOLD_PERCENT: 1.0,
  MAX_TRANSACTION_OPTIONS: 50
} as const;

export const SECURITY_CONFIG = {
  DEFAULT_AUTHORIZATION_TTL_MS: 30000,
  MAX_AUDIT_LOGS: 500,
  DEFAULT_RATE_LIMIT_ACTIONS_PER_MINUTE: 60
} as const;

export const RUNTIME_CONFIG = {
  HEARTBEAT_INTERVAL_MS: 5000,
  CIRCUIT_BREAKER_FAILURE_THRESHOLD: 5,
  CIRCUIT_BREAKER_RESET_TIMEOUT_MS: 30000,
  MAX_DEAD_LETTER_ITEMS: 200
} as const;

export const ACTION_CONFIG = {
  DEFAULT_CLICK_TIMEOUT_MS: 5000,
  DEFAULT_TYPE_TIMEOUT_MS: 5000,
  DEFAULT_NAVIGATE_TIMEOUT_MS: 15000,
  DEFAULT_WAIT_TIMEOUT_MS: 10000,
  MAX_WAIT_TIMEOUT_MS: 30000,
  MAX_QUEUE_SIZE: 50,
  ALLOWED_URL_SCHEMES: ['http:', 'https:'] as const,
  ALLOWED_KEY_PRESSES: [
    'Enter',
    'Escape',
    'Tab',
    'ArrowUp',
    'ArrowDown',
    'ArrowLeft',
    'ArrowRight',
    'Backspace',
    'Delete',
    'Home',
    'End',
    'PageUp',
    'PageDown',
    'Space'
  ] as const
} as const;

export const SCREENSHOT_CONFIG = {
  MAX_SCREENSHOT_WIDTH: 1920,
  MAX_SCREENSHOT_HEIGHT: 1080,
  MAX_SCREENSHOT_BYTES: 5_000_000,
  DEFAULT_FORMAT: 'png' as const,
  DEFAULT_QUALITY: 0.9,
  DEFAULT_PRIVACY_MODE: 'STANDARD' as const
} as const;

export const STORAGE_KEYS = {
  STATE: 'matrioshai_extension_state',
  CONFIG: 'matrioshai_extension_config',
  LOGS: 'matrioshai_extension_logs',
  AUTH_TOKEN: 'matrioshai_bridge_auth_token',
  BROWSER_ID: 'matrioshai_browser_id'
} as const;

export const TIMEOUTS = {
  HEALTH_CHECK_MS: 3000,
  MESSAGE_RESPONSE_MS: 5000,
  NAVIGATION_TIMEOUT_MS: 15000,
  STATUS_REFRESH_DEBOUNCE_MS: 250
} as const;

export const DEFAULT_ENVIRONMENT: 'development' | 'production' =
  typeof process !== 'undefined' && process.env?.NODE_ENV === 'production' ? 'production' : 'development';

export const LOG_PREFIXES = {
  EXTENSION: '[MATRIOSHAI][Extension]',
  SERVICE_WORKER: '[MATRIOSHAI][ServiceWorker]',
  CONTENT_SCRIPT: '[MATRIOSHAI][ContentScript]',
  POPUP: '[MATRIOSHAI][Popup]',
  STATE: '[MATRIOSHAI][State]',
  BRIDGE: '[MATRIOSHAI][Bridge]',
  CONTROLLER: '[MATRIOSHAI][BrowserController]',
  EVENT_ENGINE: '[MATRIOSHAI][EventEngine]',
  MUTATION_TRACKER: '[MATRIOSHAI][MutationTracker]',
  SEMANTIC_ANALYZER: '[MATRIOSHAI][SemanticAnalyzer]',
  VISUAL_ENGINE: '[MATRIOSHAI][VisualEngine]',
  VISUAL_REDACTOR: '[MATRIOSHAI][VisualRedactor]',
  ACTION_EXECUTOR: '[MATRIOSHAI][ActionExecutor]'
};
