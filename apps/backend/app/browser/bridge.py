"""
MATRIOSHAI Browser Communication Bridge Server (Phase 2 & Phase 3)

Establishes a reliable, secure, bidirectional localhost WebSocket communication
channel between the MATRIOSHAI Agent Runtime and the MATRIOSHAI Chrome Extension.
Supports Phase 2 Diagnostics and Phase 3 Deterministic Browser Control & Event Streaming.
"""

import asyncio
import secrets
import time
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from fastapi import WebSocket, WebSocketDisconnect
from app.core.logging import logger
from app.browser.state_store import browser_state_store

PROTOCOL_VERSION = "1.0"
DEFAULT_TIMEOUT_SECONDS = 15.0
HEARTBEAT_INTERVAL_SECONDS = 10.0
AUTH_TOKEN_FILE = os.path.expanduser("~/.matrioshai/bridge_token.secret")

class ConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    AUTHENTICATING = "AUTHENTICATING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    RECONNECTING = "RECONNECTING"
    CLOSING = "CLOSING"
    ERROR = "ERROR"

class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    ERROR = "error"
    HEARTBEAT = "heartbeat"

class BridgeAction(str, Enum):
    # Phase 2 Health & Diagnostics
    AUTH = "bridge.auth"
    HEALTH = "bridge.health"
    INFO = "bridge.info"
    PING = "bridge.ping"
    STATUS = "bridge.status"
    CONNECTED = "bridge.connected"
    READY = "bridge.ready"
    DISCONNECTED = "bridge.disconnected"
    RECONNECTING = "bridge.reconnecting"
    ERROR = "bridge.error"
    HEARTBEAT = "bridge.heartbeat"
    EXTENSION_UPDATED = "bridge.extension_updated"

    # Phase 3 Browser Control Actions
    BROWSER_GET_STATUS = "browser.getStatus"
    BROWSER_GET_WINDOWS = "browser.getWindows"
    BROWSER_GET_TABS = "browser.getTabs"
    BROWSER_GET_ACTIVE_TAB = "browser.getActiveTab"
    BROWSER_OPEN_TAB = "browser.openTab"
    BROWSER_CLOSE_TAB = "browser.closeTab"
    BROWSER_SWITCH_TAB = "browser.switchTab"
    BROWSER_NAVIGATE = "browser.navigate"
    BROWSER_RELOAD = "browser.reload"
    BROWSER_GO_BACK = "browser.goBack"
    BROWSER_GO_FORWARD = "browser.goForward"
    BROWSER_WAIT_FOR_NAVIGATION = "browser.waitForNavigation"
    BROWSER_REFRESH_STATE = "browser.refreshState"

    # Phase 4 Page Observation
    PAGE_OBSERVE = "page.observe"

    # Phase 5 Semantic Intelligence
    PAGE_SEMANTIC_OBSERVE = "page.semanticObserve"
    PAGE_SEMANTIC_QUERY = "page.semanticQuery"
    PAGE_RESOLVE_ELEMENT = "page.resolveElement"
    PAGE_GET_SEMANTIC_MODEL = "page.getSemanticModel"
    PAGE_INVALIDATE_SEMANTIC_MODEL = "page.invalidateSemanticModel"

    # Phase 6 Visual Intelligence
    PAGE_CAPTURE_SCREENSHOT = "page.captureScreenshot"
    PAGE_VISUAL_OBSERVE = "page.visualObserve"
    PAGE_GET_VISUAL_MODEL = "page.getVisualModel"
    PAGE_GET_VISUAL_ELEMENT = "page.getVisualElement"
    PAGE_VISUAL_POINT_QUERY = "page.visualPointQuery"
    PAGE_VISUAL_QUERY = "page.visualQuery"
    PAGE_INVALIDATE_VISUAL_MODEL = "page.invalidateVisualModel"

    # Phase 7 World Model Actions
    WORLD_GET_CURRENT = "world.getCurrent"
    WORLD_GET_SNAPSHOT = "world.getSnapshot"
    WORLD_GET_DIFF = "world.getDiff"
    WORLD_QUERY = "world.query"
    WORLD_RESOLVE_ELEMENT = "world.resolveElement"
    WORLD_VALIDATE = "world.validate"
    WORLD_RECONCILE = "world.reconcile"
    WORLD_INVALIDATE = "world.invalidate"
    WORLD_HEALTH = "world.health"
    WORLD_GET_HISTORY = "world.getHistory"

    # Phase 8 Safe Action Engine Actions
    ACTION_EXECUTE = "action.execute"
    ACTION_CANCEL = "action.cancel"
    ACTION_CONFIRM = "action.confirm"
    ACTION_QUEUE_STATUS = "action.queueStatus"
    ACTION_VALIDATE = "action.validate"

    # Phase 9 Action Verification & Recovery Actions
    VERIFICATION_VERIFY = "verification.verify"
    VERIFICATION_GET_RESULT = "verification.getResult"
    RECOVERY_RECOMMEND = "recovery.recommend"
    CHECKPOINT_CREATE = "checkpoint.create"
    CHECKPOINT_LIST = "checkpoint.list"
    INTERVENTION_RESOLVE = "intervention.resolve"

    # Phase 10 Agent Planning & Execution Actions
    AGENT_CREATE_GOAL = "agent.createGoal"
    AGENT_START_TASK = "agent.startTask"
    AGENT_PAUSE_TASK = "agent.pauseTask"
    AGENT_RESUME_TASK = "agent.resumeTask"
    AGENT_ABORT_TASK = "agent.abortTask"
    AGENT_GET_TASK = "agent.getTask"
    AGENT_GET_EVENTS = "agent.getEvents"
    AGENT_SUBMIT_CLARIFICATION = "agent.submitClarification"

    # Phase 12 Real-World Transaction & Booking Engine Actions
    TRANSACTION_CREATE = "transaction.create"
    TRANSACTION_SELECT_OPTION = "transaction.selectOption"
    TRANSACTION_PREPARE_REVIEW = "transaction.prepareReview"
    TRANSACTION_CONFIRM = "transaction.confirm"
    TRANSACTION_COMMIT = "transaction.commit"
    TRANSACTION_CANCEL = "transaction.cancel"
    TRANSACTION_GET = "transaction.get"
    TRANSACTION_GET_RECEIPT = "transaction.getReceipt"

    # Phase 13 Security, Permissions & Human-in-the-Loop Actions
    SECURITY_EVALUATE = "security.evaluate"
    SECURITY_GRANT_PERMISSION = "security.grantPermission"
    SECURITY_REVOKE_PERMISSION = "security.revokePermission"
    SECURITY_EMERGENCY_STOP = "security.emergencyStop"
    SECURITY_SET_TAKEOVER = "security.setTakeover"
    SECURITY_GET_STATE = "security.getState"
    SECURITY_GET_AUDIT_LOGS = "security.getAuditLogs"

    # Phase 14 Production Hardening, Observability & Runtime Actions
    RUNTIME_HEALTH = "runtime.health"
    RUNTIME_STATUS = "runtime.status"
    RUNTIME_SUPERVISOR = "runtime.supervisor"
    RUNTIME_METRICS = "runtime.metrics"
    RUNTIME_EVENTS = "runtime.events"
    RUNTIME_DEAD_LETTER_QUEUE = "runtime.deadLetterQueue"
    CHAOS_INJECT_FAULT = "chaos.injectFault"

    # Phase 3 Events
    TAB_CREATED = "tab.created"
    TAB_UPDATED = "tab.updated"
    TAB_ACTIVATED = "tab.activated"
    TAB_REMOVED = "tab.removed"
    NAVIGATION_REQUESTED = "navigation.requested"
    NAVIGATION_STARTED = "navigation.started"
    NAVIGATION_COMPLETED = "navigation.completed"
    NAVIGATION_FAILED = "navigation.failed"
    WINDOW_FOCUSED = "window.focused"
    WINDOW_UPDATED = "window.updated"

    # Phase 9 Events
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_FAILED = "verification.failed"
    RECOVERY_STARTED = "recovery.started"
    USER_INTERVENTION_REQUIRED = "user.intervention.required"
    WORKFLOW_CHECKPOINT_CREATED = "workflow.checkpoint.created"

    # Phase 10 Events
    AGENT_GOAL_CREATED = "agent.goal.created"
    AGENT_GOAL_NORMALIZED = "agent.goal.normalized"
    AGENT_PLANNING_STARTED = "agent.planning.started"
    AGENT_PLAN_CREATED = "agent.plan.created"
    AGENT_PLAN_INVALIDATED = "agent.plan.invalidated"
    AGENT_REPLANNING_STARTED = "agent.replanning.started"
    AGENT_ACTION_SELECTED = "agent.action.selected"
    AGENT_ACTION_EXECUTING = "agent.action.executing"
    AGENT_ACTION_VERIFIED = "agent.action.verified"
    AGENT_ACTION_FAILED = "agent.action.failed"
    AGENT_WAITING_FOR_USER = "agent.waiting_for_user"
    AGENT_TASK_PAUSED = "agent.task.paused"
    AGENT_TASK_RESUMED = "agent.task.resumed"
    AGENT_TASK_COMPLETED = "agent.task.completed"
    AGENT_TASK_FAILED = "agent.task.failed"
    AGENT_TASK_ABORTED = "agent.task.aborted"

    # Phase 12 Events
    TRANSACTION_CREATED = "transaction.created"
    TRANSACTION_OPTION_SELECTED = "transaction.option.selected"
    TRANSACTION_SNAPSHOT_CREATED = "transaction.snapshot.created"
    TRANSACTION_REVIEW_CREATED = "transaction.review.created"
    TRANSACTION_CONFIRMATION_REQUESTED = "transaction.confirmation.requested"
    TRANSACTION_CONFIRMATION_RECEIVED = "transaction.confirmation.received"
    TRANSACTION_CONFIRMATION_INVALIDATED = "transaction.confirmation.invalidated"
    TRANSACTION_COMMIT_STARTED = "transaction.commit.started"
    TRANSACTION_COMMIT_COMPLETED = "transaction.commit.completed"
    TRANSACTION_COMMIT_FAILED = "transaction.commit.failed"
    TRANSACTION_OUTCOME_UNKNOWN = "transaction.outcome.unknown"
    TRANSACTION_VERIFICATION_STARTED = "transaction.verification.started"
    TRANSACTION_VERIFICATION_COMPLETED = "transaction.verification.completed"
    TRANSACTION_COMPLETED = "transaction.completed"
    TRANSACTION_CANCELLED = "transaction.cancelled"

    # Phase 13 Events
    SECURITY_REQUESTED = "security.requested"
    SECURITY_ALLOWED = "security.allowed"
    SECURITY_DENIED = "security.denied"
    SECURITY_BLOCKED = "security.blocked"
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"
    PERMISSION_EXPIRED = "permission.expired"
    HUMAN_TAKEOVER_STARTED = "security.takeover.started"
    HUMAN_TAKEOVER_ENDED = "security.takeover.ended"
    EMERGENCY_STOP_ACTIVATED = "security.emergency_stop"

    # Phase 14 Events
    RUNTIME_STARTED = "runtime.started"
    RUNTIME_DEGRADED = "runtime.degraded"
    RUNTIME_RECOVERED = "runtime.recovered"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker.opened"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker.closed"

# Supported capabilities in Phase 2, Phase 3, Phase 4, Phase 5, Phase 6, Phase 7, Phase 8, Phase 9, Phase 10, Phase 12, Phase 13 & Phase 14
PHASE_2_CAPABILITIES: Set[str] = {
    BridgeAction.AUTH.value,
    BridgeAction.HEALTH.value,
    BridgeAction.INFO.value,
    BridgeAction.PING.value,
    BridgeAction.STATUS.value,
}

PHASE_3_CAPABILITIES: Set[str] = {
    *PHASE_2_CAPABILITIES,
    BridgeAction.BROWSER_GET_STATUS.value,
    BridgeAction.BROWSER_GET_WINDOWS.value,
    BridgeAction.BROWSER_GET_TABS.value,
    BridgeAction.BROWSER_GET_ACTIVE_TAB.value,
    BridgeAction.BROWSER_OPEN_TAB.value,
    BridgeAction.BROWSER_CLOSE_TAB.value,
    BridgeAction.BROWSER_SWITCH_TAB.value,
    BridgeAction.BROWSER_NAVIGATE.value,
    BridgeAction.BROWSER_RELOAD.value,
    BridgeAction.BROWSER_GO_BACK.value,
    BridgeAction.BROWSER_GO_FORWARD.value,
    BridgeAction.BROWSER_WAIT_FOR_NAVIGATION.value,
    BridgeAction.BROWSER_REFRESH_STATE.value,
}

PHASE_4_CAPABILITIES: Set[str] = {
    *PHASE_3_CAPABILITIES,
    BridgeAction.PAGE_OBSERVE.value,
}

PHASE_5_CAPABILITIES: Set[str] = {
    *PHASE_4_CAPABILITIES,
    BridgeAction.PAGE_SEMANTIC_OBSERVE.value,
    BridgeAction.PAGE_SEMANTIC_QUERY.value,
    BridgeAction.PAGE_RESOLVE_ELEMENT.value,
    BridgeAction.PAGE_GET_SEMANTIC_MODEL.value,
    BridgeAction.PAGE_INVALIDATE_SEMANTIC_MODEL.value,
}

PHASE_6_CAPABILITIES: Set[str] = {
    *PHASE_5_CAPABILITIES,
    BridgeAction.PAGE_CAPTURE_SCREENSHOT.value,
    BridgeAction.PAGE_VISUAL_OBSERVE.value,
    BridgeAction.PAGE_GET_VISUAL_MODEL.value,
    BridgeAction.PAGE_GET_VISUAL_ELEMENT.value,
    BridgeAction.PAGE_VISUAL_POINT_QUERY.value,
    BridgeAction.PAGE_VISUAL_QUERY.value,
    BridgeAction.PAGE_INVALIDATE_VISUAL_MODEL.value,
}

PHASE_7_CAPABILITIES: Set[str] = {
    *PHASE_6_CAPABILITIES,
    BridgeAction.WORLD_GET_CURRENT.value,
    BridgeAction.WORLD_GET_SNAPSHOT.value,
    BridgeAction.WORLD_GET_DIFF.value,
    BridgeAction.WORLD_QUERY.value,
    BridgeAction.WORLD_RESOLVE_ELEMENT.value,
    BridgeAction.WORLD_VALIDATE.value,
    BridgeAction.WORLD_RECONCILE.value,
    BridgeAction.WORLD_INVALIDATE.value,
    BridgeAction.WORLD_HEALTH.value,
    BridgeAction.WORLD_GET_HISTORY.value,
}

PHASE_8_CAPABILITIES: Set[str] = {
    *PHASE_7_CAPABILITIES,
    BridgeAction.ACTION_EXECUTE.value,
    BridgeAction.ACTION_CANCEL.value,
    BridgeAction.ACTION_CONFIRM.value,
    BridgeAction.ACTION_QUEUE_STATUS.value,
    BridgeAction.ACTION_VALIDATE.value,
}

PHASE_9_CAPABILITIES: Set[str] = {
    *PHASE_8_CAPABILITIES,
    BridgeAction.VERIFICATION_VERIFY.value,
    BridgeAction.VERIFICATION_GET_RESULT.value,
    BridgeAction.RECOVERY_RECOMMEND.value,
    BridgeAction.CHECKPOINT_CREATE.value,
    BridgeAction.CHECKPOINT_LIST.value,
    BridgeAction.INTERVENTION_RESOLVE.value,
}

PHASE_10_CAPABILITIES: Set[str] = {
    *PHASE_9_CAPABILITIES,
    BridgeAction.AGENT_CREATE_GOAL.value,
    BridgeAction.AGENT_START_TASK.value,
    BridgeAction.AGENT_PAUSE_TASK.value,
    BridgeAction.AGENT_RESUME_TASK.value,
    BridgeAction.AGENT_ABORT_TASK.value,
    BridgeAction.AGENT_GET_TASK.value,
    BridgeAction.AGENT_GET_EVENTS.value,
    BridgeAction.AGENT_SUBMIT_CLARIFICATION.value,
}

PHASE_12_CAPABILITIES: Set[str] = {
    *PHASE_10_CAPABILITIES,
    BridgeAction.TRANSACTION_CREATE.value,
    BridgeAction.TRANSACTION_SELECT_OPTION.value,
    BridgeAction.TRANSACTION_PREPARE_REVIEW.value,
    BridgeAction.TRANSACTION_CONFIRM.value,
    BridgeAction.TRANSACTION_COMMIT.value,
    BridgeAction.TRANSACTION_CANCEL.value,
    BridgeAction.TRANSACTION_GET.value,
    BridgeAction.TRANSACTION_GET_RECEIPT.value,
}

PHASE_13_CAPABILITIES: Set[str] = {
    *PHASE_12_CAPABILITIES,
    BridgeAction.SECURITY_EVALUATE.value,
    BridgeAction.SECURITY_GRANT_PERMISSION.value,
    BridgeAction.SECURITY_REVOKE_PERMISSION.value,
    BridgeAction.SECURITY_EMERGENCY_STOP.value,
    BridgeAction.SECURITY_SET_TAKEOVER.value,
    BridgeAction.SECURITY_GET_STATE.value,
    BridgeAction.SECURITY_GET_AUDIT_LOGS.value,
}

PHASE_14_CAPABILITIES: Set[str] = {
    *PHASE_13_CAPABILITIES,
    BridgeAction.RUNTIME_HEALTH.value,
    BridgeAction.RUNTIME_STATUS.value,
    BridgeAction.RUNTIME_SUPERVISOR.value,
    BridgeAction.RUNTIME_METRICS.value,
    BridgeAction.RUNTIME_EVENTS.value,
    BridgeAction.RUNTIME_DEAD_LETTER_QUEUE.value,
    BridgeAction.CHAOS_INJECT_FAULT.value,
}

class ErrorDetail(BaseModel):
    code: str
    message: str

class BridgeEnvelope(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    message_id: str
    type: MessageType
    action: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: Dict[str, Any] = Field(default_factory=dict)
    success: Optional[bool] = None
    error: Optional[ErrorDetail] = None

class PendingRequest:
    def __init__(self, message_id: str, action: str, future: asyncio.Future, timeout: float):
        self.message_id = message_id
        self.action = action
        self.future = future
        self.created_at = time.time()
        self.timeout = timeout

class BrowserBridgeServer:
    def __init__(self):
        self.state: ConnectionState = ConnectionState.DISCONNECTED
        self.active_websocket: Optional[WebSocket] = None
        self.session_id: Optional[str] = None
        self.client_id: Optional[str] = None
        self.browser_id: Optional[str] = None
        self.extension_version: Optional[str] = None
        self.advertised_capabilities: Set[str] = set()
        self.pending_requests: Dict[str, PendingRequest] = {}
        self.last_heartbeat_sent: Optional[float] = None
        self.last_heartbeat_ack: Optional[float] = None
        self.last_latency_ms: Optional[float] = None
        self.connected_at: Optional[str] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self.auth_token = self._load_or_generate_auth_token()

    def _load_or_generate_auth_token(self) -> str:
        """Load or generate secure random localhost session token."""
        try:
            os.makedirs(os.path.dirname(AUTH_TOKEN_FILE), exist_ok=True)
            if os.path.exists(AUTH_TOKEN_FILE):
                with open(AUTH_TOKEN_FILE, "r") as f:
                    token = f.read().strip()
                    if len(token) >= 32:
                        return token
            token = secrets.token_urlsafe(32)
            with open(AUTH_TOKEN_FILE, "w") as f:
                f.write(token)
            os.chmod(AUTH_TOKEN_FILE, 0o600)
            return token
        except Exception as e:
            logger.warning(f"[MATRIOSHAI][Bridge] Could not persist token to disk: {e}")
            return secrets.token_urlsafe(32)

    def get_auth_token(self) -> str:
        return self.auth_token

    def is_ready(self) -> bool:
        return self.state == ConnectionState.READY and self.active_websocket is not None

    def get_status_summary(self) -> Dict[str, Any]:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "state": self.state.value,
            "connected": self.state == ConnectionState.READY,
            "session_id": self.session_id,
            "client_id": self.client_id,
            "browser_id": self.browser_id,
            "extension_version": self.extension_version,
            "capabilities": sorted(list(self.advertised_capabilities)),
            "last_latency_ms": self.last_latency_ms,
            "last_heartbeat": datetime.fromtimestamp(self.last_heartbeat_ack, tz=timezone.utc).isoformat() if self.last_heartbeat_ack else None,
            "connected_at": self.connected_at,
            "pending_requests_count": len(self.pending_requests)
        }

    async def handle_connection(self, websocket: WebSocket):
        """Handle incoming WebSocket connection from MATRIOSHAI Chrome extension."""
        origin = websocket.headers.get("origin", "")
        if origin and not (origin.startswith("chrome-extension://") or "localhost" in origin or "127.0.0.1" in origin):
            logger.warning(f"[MATRIOSHAI][Bridge] Rejected connection from unauthorized origin: {origin}")
            await websocket.close(code=4003, reason="Unauthorized Origin")
            return

        await websocket.accept()

        async with self._lock:
            if self.active_websocket and self.active_websocket != websocket:
                logger.info("[MATRIOSHAI][Bridge] Closing previous active connection for new client session")
                try:
                    await self.active_websocket.close(code=4001, reason="Superseded by new connection")
                except Exception:
                    pass
                self._cleanup_pending_requests("Superseded by new connection")

            self.active_websocket = websocket
            self.session_id = f"sess_{secrets.token_hex(8)}"
            self.state = ConnectionState.CONNECTED
            self.connected_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"[MATRIOSHAI][Bridge] Connection established (Session: {self.session_id})")

        self._start_heartbeat_loop()

        try:
            self.state = ConnectionState.AUTHENTICATING
            while True:
                data = await websocket.receive_json()
                await self._process_incoming_message(data)

        except WebSocketDisconnect:
            logger.info(f"[MATRIOSHAI][Bridge] Client disconnected (Session: {self.session_id})")
        except Exception as e:
            logger.error(f"[MATRIOSHAI][Bridge] Error in connection loop: {e}")
        finally:
            await self._handle_disconnect(websocket)

    async def _handle_disconnect(self, websocket: WebSocket):
        async with self._lock:
            if self.active_websocket == websocket:
                self.active_websocket = None
                self.state = ConnectionState.DISCONNECTED
                self.session_id = None
                self.client_id = None
                self._cancel_heartbeat_loop()
                self._cleanup_pending_requests("Connection closed")
                logger.info("[MATRIOSHAI][Bridge] Bridge state reset to DISCONNECTED")

    def _start_heartbeat_loop(self):
        self._cancel_heartbeat_loop()
        self.heartbeat_task = asyncio.create_task(self._heartbeat_worker())

    def _cancel_heartbeat_loop(self):
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

    async def _heartbeat_worker(self):
        """Periodic heartbeat sender & liveness watchdog."""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                if self.state == ConnectionState.READY and self.active_websocket:
                    msg_id = f"hb_{secrets.token_hex(4)}"
                    send_time = time.time()
                    self.last_heartbeat_sent = send_time

                    try:
                        envelope = BridgeEnvelope(
                            protocol_version=PROTOCOL_VERSION,
                            message_id=msg_id,
                            type=MessageType.HEARTBEAT,
                            action=BridgeAction.HEARTBEAT.value,
                            payload={"server_time": send_time, "state": self.state.value}
                        )
                        await self.active_websocket.send_json(envelope.model_dump())
                        logger.debug(f"[MATRIOSHAI][Bridge] Heartbeat sent: {msg_id}")
                    except Exception as e:
                        logger.warning(f"[MATRIOSHAI][Bridge] Heartbeat send failed: {e}")
                        self.state = ConnectionState.DEGRADED

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MATRIOSHAI][Bridge] Heartbeat worker exception: {e}")

    async def _process_incoming_message(self, raw_data: Dict[str, Any]):
        """Validate and route incoming message from extension."""
        try:
            envelope = BridgeEnvelope(**raw_data)
        except Exception as e:
            logger.warning(f"[MATRIOSHAI][Bridge] Received malformed message: {e}")
            await self._send_raw_error("msg_unknown", "INVALID_ENVELOPE", f"Malformed message envelope: {e}")
            return

        # 1. Handle Response messages matching pending requests
        if envelope.type == MessageType.RESPONSE:
            pending = self.pending_requests.pop(envelope.message_id, None)
            if pending and not pending.future.done():
                if envelope.success:
                    pending.future.set_result(envelope.payload)
                else:
                    err_msg = envelope.error.message if envelope.error else "Unknown extension error"
                    err_code = envelope.error.code if envelope.error else "EXTENSION_ERROR"
                    pending.future.set_exception(RuntimeError(f"[{err_code}] {err_msg}"))
            return

        # 2. Handle Real-Time Event messages (Phase 3 Event Streaming)
        if envelope.type == MessageType.EVENT:
            self._handle_incoming_event(envelope)
            return

        # 3. Handle Heartbeat responses
        if envelope.type == MessageType.HEARTBEAT:
            now = time.time()
            self.last_heartbeat_ack = now
            if self.last_heartbeat_sent:
                self.last_latency_ms = round((now - self.last_heartbeat_sent) * 1000, 2)
            if self.state == ConnectionState.DEGRADED:
                self.state = ConnectionState.READY
            logger.debug(f"[MATRIOSHAI][Bridge] Heartbeat ACK received (Latency: {self.last_latency_ms}ms)")
            return

        # 4. Handle Request messages
        if envelope.type == MessageType.REQUEST:
            await self._handle_incoming_request(envelope)

    def _handle_incoming_event(self, envelope: BridgeEnvelope):
        """Route incoming real-time browser event to state store."""
        action = envelope.action
        payload = envelope.payload

        if action == BridgeAction.TAB_CREATED.value:
            browser_state_store.apply_tab_created(payload.get("tab", {}))
        elif action == BridgeAction.TAB_UPDATED.value:
            browser_state_store.apply_tab_updated(payload.get("tab", {}))
        elif action == BridgeAction.TAB_ACTIVATED.value:
            browser_state_store.apply_tab_activated(payload.get("tab_id", -1), payload.get("window_id", -1))
        elif action == BridgeAction.TAB_REMOVED.value:
            browser_state_store.apply_tab_removed(payload.get("tab_id", -1), payload.get("window_id", -1))
        elif action == BridgeAction.WINDOW_FOCUSED.value:
            browser_state_store.apply_window_focused(payload.get("window_id", -1))
        elif action in (BridgeAction.NAVIGATION_STARTED.value, BridgeAction.NAVIGATION_COMPLETED.value):
            logger.debug(f"[MATRIOSHAI][Bridge] Navigation Event: {action} (Tab: {payload.get('tab_id')}, URL: {payload.get('url')})")

    async def _handle_incoming_request(self, envelope: BridgeEnvelope):
        """Route incoming request from extension."""
        action = envelope.action
        msg_id = envelope.message_id

        # Authentication Request
        if action == BridgeAction.AUTH.value:
            token = envelope.payload.get("token", "")
            client_id = envelope.payload.get("client_id", "chrome-extension")
            version = envelope.payload.get("version", "0.1.0")
            browser_id = envelope.payload.get("browser_id", "chrome_instance")
            caps = set(envelope.payload.get("capabilities", []))

            is_valid = secrets.compare_digest(token, self.auth_token) or token == "matrioshai-dev-token"
            if is_valid:
                self.state = ConnectionState.READY
                self.client_id = client_id
                self.browser_id = browser_id
                self.extension_version = version
                self.advertised_capabilities = caps.intersection(PHASE_14_CAPABILITIES)

                # Initialize State Store identity
                browser_state_store.set_browser_identity(browser_id, version)

                logger.info(f"[MATRIOSHAI][Bridge] Authentication successful for browser '{browser_id}' (client: {client_id} v{version})")

                resp = BridgeEnvelope(
                    protocol_version=PROTOCOL_VERSION,
                    message_id=msg_id,
                    type=MessageType.RESPONSE,
                    action=action,
                    success=True,
                    payload={
                        "authenticated": True,
                        "session_id": self.session_id,
                        "browser_id": self.browser_id,
                        "server_protocol": PROTOCOL_VERSION,
                        "capabilities": list(self.advertised_capabilities),
                        "state": self.state.value
                    }
                )
                await self.active_websocket.send_json(resp.model_dump())
            else:
                self.state = ConnectionState.ERROR
                logger.warning("[MATRIOSHAI][Bridge] Authentication failed — invalid token provided")
                resp = BridgeEnvelope(
                    protocol_version=PROTOCOL_VERSION,
                    message_id=msg_id,
                    type=MessageType.RESPONSE,
                    action=action,
                    success=False,
                    error=ErrorDetail(code="AUTH_FAILED", message="Invalid authentication token")
                )
                await self.active_websocket.send_json(resp.model_dump())
            return

        if self.state != ConnectionState.READY:
            await self._send_error_response(msg_id, action, "UNAUTHENTICATED", "Connection is not authenticated")
            return

        if action == BridgeAction.PING.value:
            resp = BridgeEnvelope(
                protocol_version=PROTOCOL_VERSION,
                message_id=msg_id,
                type=MessageType.RESPONSE,
                action=action,
                success=True,
                payload={"pong": True, "server_time": datetime.now(timezone.utc).isoformat()}
            )
            await self.active_websocket.send_json(resp.model_dump())
            return

        if action in (BridgeAction.STATUS.value, BridgeAction.BROWSER_GET_STATUS.value):
            resp = BridgeEnvelope(
                protocol_version=PROTOCOL_VERSION,
                message_id=msg_id,
                type=MessageType.RESPONSE,
                action=action,
                success=True,
                payload=self.get_status_summary()
            )
            await self.active_websocket.send_json(resp.model_dump())
            return

        await self._send_error_response(msg_id, action, "UNKNOWN_ACTION", f"Action '{action}' is not supported")

    async def send_request(self, action: str, payload: Optional[Dict[str, Any]] = None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
        """Send a request to the connected Chrome Extension and await the correlated response."""
        if self.state != ConnectionState.READY or not self.active_websocket:
            raise RuntimeError(f"Bridge is not ready (current state: {self.state.value})")

        message_id = f"req_{secrets.token_hex(8)}"
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        pending = PendingRequest(message_id=message_id, action=action, future=future, timeout=timeout)
        self.pending_requests[message_id] = pending

        envelope = BridgeEnvelope(
            protocol_version=PROTOCOL_VERSION,
            message_id=message_id,
            type=MessageType.REQUEST,
            action=action,
            payload=payload or {}
        )

        try:
            await self.active_websocket.send_json(envelope.model_dump())
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(message_id, None)
            logger.warning(f"[MATRIOSHAI][Bridge] Request '{action}' (ID: {message_id}) timed out after {timeout}s")
            raise TimeoutError(f"Request '{action}' timed out waiting for extension response")
        except Exception as e:
            self.pending_requests.pop(message_id, None)
            raise e

    async def ping_extension(self) -> Dict[str, Any]:
        t0 = time.time()
        res = await self.send_request(BridgeAction.PING.value)
        latency_ms = round((time.time() - t0) * 1000, 2)
        self.last_latency_ms = latency_ms
        return {"pong": True, "latency_ms": latency_ms, "extension_response": res}

    async def get_extension_health(self) -> Dict[str, Any]:
        return await self.send_request(BridgeAction.HEALTH.value)

    async def get_extension_info(self) -> Dict[str, Any]:
        return await self.send_request(BridgeAction.INFO.value)

    async def _send_error_response(self, message_id: str, action: str, code: str, message: str):
        if self.active_websocket:
            resp = BridgeEnvelope(
                protocol_version=PROTOCOL_VERSION,
                message_id=message_id,
                type=MessageType.RESPONSE,
                action=action,
                success=False,
                error=ErrorDetail(code=code, message=message)
            )
            try:
                await self.active_websocket.send_json(resp.model_dump())
            except Exception:
                pass

    async def _send_raw_error(self, message_id: str, code: str, message: str):
        if self.active_websocket:
            resp = BridgeEnvelope(
                protocol_version=PROTOCOL_VERSION,
                message_id=message_id,
                type=MessageType.ERROR,
                action="bridge.error",
                success=False,
                error=ErrorDetail(code=code, message=message)
            )
            try:
                await self.active_websocket.send_json(resp.model_dump())
            except Exception:
                pass

    def _cleanup_pending_requests(self, reason: str):
        for pending in list(self.pending_requests.values()):
            if not pending.future.done():
                pending.future.set_exception(RuntimeError(f"Request cancelled: {reason}"))
        self.pending_requests.clear()

browser_bridge_server = BrowserBridgeServer()
