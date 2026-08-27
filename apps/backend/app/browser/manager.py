"""
MATRIOSHAI Browser Manager (Phase 3)

Unified Browser Control Layer abstraction for the MATRIOSHAI Agent Runtime.
Provides deterministic, audit-logged, and concurrency-safe control of Chrome
windows, tabs, and navigation lifecycle via the WebSocket Bridge.
"""

import time
import secrets
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Tuple
from app.core.logging import logger
from app.browser.bridge import browser_bridge_server, BridgeAction
from app.browser.state_store import (
    browser_state_store,
    WindowState,
    TabState,
    NavigationResult,
    NavigationStatus,
    BrowserAuditLog,
    PageObservation,
    SemanticPageModel,
    SemanticQuery,
    QueryResult,
    ResolveResult,
    SemanticElementRef,
    VisualPageModel,
    ScreenshotMetadata,
    PointQueryResult,
    VisualQueryResult,
    VisualQuery,
    VisualBoundingBox,
    CandidateElement,
    BrowserWorldModel,
    BrowserWorldSnapshot,
    WorldStateDiff,
    WorldElement,
    WorldElementRef,
    WorldElementResolution,
    WorldPageState,
    FrameTree,
    WorldHealth,
    WorldQuery,
    WorldQueryResult,
    ActionIntent,
    ActionType,
    ActionTarget,
    ActionResult,
    ActionTrace,
    ActionConfirmationRequest,
    ActionConfirmationResponse,
    ActionQueueStatus,
    VerificationResult,
    VerificationStatus,
    VerificationWaitPolicy,
    UserInterventionRequest,
    WorkflowCheckpoint,
    AgentTask,
    AgentGoal,
    AgentResult,
    AgentEvent,
    TaskPriority,
    Transaction,
    TransactionOption,
    TransactionReview,
    TransactionConfirmation,
    CommitAuthorization,
    TransactionReceipt,
    TransactionState,
    SecurityDecision,
    SecurityActor,
    PermissionCategory,
    PermissionScope,
    DomainTrustLevel,
    DomainPermission,
    SecurityRequest,
    ActionAuthorization,
    TakeoverState,
    AutonomyLevel,
    SecurityAuditEvent,
    RuntimeState,
    HealthState,
    ComponentHealth,
    DeadLetterItem
)
from app.browser.world_model import world_model_engine
from app.browser.action_engine import action_engine
from app.browser.verification_engine import verification_engine
from app.browser.transaction_engine import transaction_engine
from app.browser.security_engine import security_engine
from app.browser.runtime import matrioshai_runtime
from app.browser.observability import observability_manager
from app.browser.resilience import dead_letter_queue
from app.browser.chaos import fault_injection

class BrowserManager:
    """
    High-level Browser Manager interface for MATRIOSHAI.
    Agents and runtime interact exclusively with BrowserManager, never directly with raw Chrome APIs.
    """

    def __init__(self):
        self.state_store = browser_state_store
        self.bridge = browser_bridge_server

    def is_connected(self) -> bool:
        return self.bridge.is_ready()

    def get_status(self) -> Dict[str, Any]:
        """Get complete status of the Browser Control Layer."""
        bridge_status = self.bridge.get_status_summary()
        state_summary = self.state_store.get_summary()
        return {
            "browser_layer_ready": self.is_connected(),
            "bridge": bridge_status,
            "browser": state_summary
        }

    # ------------------------------------------------------------------------
    # URL VALIDATION & SECURITY
    # ------------------------------------------------------------------------

    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate and normalize web URLs before issuing navigation commands.
        Rejects dangerous schemes (javascript:, data:, file:, vbscript:).
        """
        if not url or not isinstance(url, str):
            return False, None, "URL is required and must be a non-empty string"

        trimmed = url.strip()
        lower = trimmed.lower()

        # Reject dangerous schemes
        for dangerous in ("javascript:", "data:", "file:", "vbscript:"):
            if lower.startswith(dangerous):
                return False, None, f"Dangerous or unsupported URL scheme rejected: '{url}'"

        normalized = trimmed
        if not (lower.startswith("http://") or lower.startswith("https://") or lower.startswith("chrome://") or lower.startswith("about:")):
            normalized = f"https://{trimmed}"

        try:
            parsed = urlparse(normalized)
            if not parsed.scheme or not parsed.netloc:
                return False, None, f"Malformed URL: '{url}'"
            return True, normalized, None
        except Exception as e:
            return False, None, f"URL parse error: {e}"

    # ------------------------------------------------------------------------
    # WINDOW OPERATIONS
    # ------------------------------------------------------------------------

    async def get_windows(self) -> List[WindowState]:
        """Discover all open browser windows."""
        if not self.is_connected():
            return self.state_store.get_windows()

        try:
            resp = await self.bridge.send_request(BridgeAction.BROWSER_GET_WINDOWS.value)
            windows_data = resp.get("windows", [])
            # Update state store
            for wd in windows_data:
                try:
                    w = WindowState(**wd)
                    self.state_store.windows[w.window_id] = w
                except Exception:
                    pass
            return self.state_store.get_windows()
        except Exception as e:
            logger.warning(f"[MATRIOSHAI][BrowserManager] Error querying windows: {e}")
            return self.state_store.get_windows()

    # ------------------------------------------------------------------------
    # TAB OPERATIONS
    # ------------------------------------------------------------------------

    async def get_tabs(self) -> List[TabState]:
        """Discover all open tabs across all browser windows."""
        if not self.is_connected():
            return self.state_store.get_tabs()

        try:
            resp = await self.bridge.send_request(BridgeAction.BROWSER_GET_TABS.value)
            tabs_data = resp.get("tabs", [])
            for td in tabs_data:
                try:
                    t = TabState(**td)
                    self.state_store.tabs[t.tab_id] = t
                except Exception:
                    pass
            return self.state_store.get_tabs()
        except Exception as e:
            logger.warning(f"[MATRIOSHAI][BrowserManager] Error querying tabs: {e}")
            return self.state_store.get_tabs()

    async def get_active_tab(self) -> Optional[TabState]:
        """Identify the currently active tab."""
        if not self.is_connected():
            return self.state_store.get_active_tab()

        try:
            resp = await self.bridge.send_request(BridgeAction.BROWSER_GET_ACTIVE_TAB.value)
            tab_data = resp.get("tab")
            if tab_data:
                tab = TabState(**tab_data)
                self.state_store.tabs[tab.tab_id] = tab
                self.state_store.active_tab_id = tab.tab_id
                return tab
            return self.state_store.get_active_tab()
        except Exception as e:
            logger.warning(f"[MATRIOSHAI][BrowserManager] Error querying active tab: {e}")
            return self.state_store.get_active_tab()

    async def open_tab(self, url: Optional[str] = None) -> TabState:
        """Open a new browser tab (optionally navigating to a URL)."""
        action_id = f"act_{secrets.token_hex(4)}"
        valid_url = None

        if url:
            valid, normalized, err = self.validate_url(url)
            if not valid:
                self.state_store.record_audit_log(action_id, "browser.openTab", None, url, "failed", err)
                raise ValueError(f"INVALID_URL: {err}")
            valid_url = normalized

        if not self.is_connected():
            raise RuntimeError("Browser Bridge is not connected")

        try:
            resp = await self.bridge.send_request(BridgeAction.BROWSER_OPEN_TAB.value, {"url": valid_url})
            tab_data = resp.get("tab")
            if not tab_data:
                raise RuntimeError("Failed to open tab — no tab data returned")

            tab = TabState(**tab_data)
            self.state_store.tabs[tab.tab_id] = tab
            self.state_store.active_tab_id = tab.tab_id
            self.state_store.record_audit_log(action_id, "browser.openTab", tab.tab_id, valid_url, "success")
            logger.info(f"[MATRIOSHAI][BrowserManager] Opened new tab ID={tab.tab_id} url='{tab.url}'")
            return tab
        except Exception as e:
            self.state_store.record_audit_log(action_id, "browser.openTab", None, valid_url, "failed", str(e))
            raise e

    async def switch_tab(self, tab_id: int) -> TabState:
        """Switch active tab in Chrome."""
        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            raise RuntimeError("Browser Bridge is not connected")

        try:
            resp = await self.bridge.send_request(BridgeAction.BROWSER_SWITCH_TAB.value, {"tab_id": tab_id})
            tab_data = resp.get("tab")
            if not tab_data:
                raise RuntimeError(f"TAB_NOT_FOUND: Tab {tab_id} does not exist")

            tab = TabState(**tab_data)
            self.state_store.tabs[tab.tab_id] = tab
            self.state_store.active_tab_id = tab.tab_id
            self.state_store.record_audit_log(action_id, "browser.switchTab", tab_id, None, "success")
            logger.info(f"[MATRIOSHAI][BrowserManager] Switched to tab ID={tab_id}")
            return tab
        except Exception as e:
            self.state_store.record_audit_log(action_id, "browser.switchTab", tab_id, None, "failed", str(e))
            raise e

    async def close_tab(self, tab_id: int) -> Dict[str, Any]:
        """Close an existing tab."""
        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            raise RuntimeError("Browser Bridge is not connected")

        try:
            resp = await self.bridge.send_request(BridgeAction.BROWSER_CLOSE_TAB.value, {"tab_id": tab_id})
            self.state_store.tabs.pop(tab_id, None)
            if self.state_store.active_tab_id == tab_id:
                self.state_store.active_tab_id = None
            self.state_store.record_audit_log(action_id, "browser.closeTab", tab_id, None, "success")
            logger.info(f"[MATRIOSHAI][BrowserManager] Closed tab ID={tab_id}")
            return resp
        except Exception as e:
            self.state_store.record_audit_log(action_id, "browser.closeTab", tab_id, None, "failed", str(e))
            raise e

    # ------------------------------------------------------------------------
    # NAVIGATION LIFECYCLE OPERATIONS
    # ------------------------------------------------------------------------

    async def navigate(self, tab_id: int, url: str, timeout_seconds: float = 15.0) -> NavigationResult:
        """
        Navigate a real Chrome tab to a target URL and await completion.
        Validates URL, monitors lifecycle events, and records audit logs.
        """
        action_id = f"act_{secrets.token_hex(4)}"
        valid, normalized_url, err = self.validate_url(url)
        if not valid or not normalized_url:
            self.state_store.record_audit_log(action_id, "browser.navigate", tab_id, url, "failed", err)
            return NavigationResult(
                navigation_id=f"nav_err_{secrets.token_hex(4)}",
                tab_id=tab_id,
                requested_url=url,
                status=NavigationStatus.FAILED,
                error={"code": "INVALID_URL", "message": err or "Invalid URL"}
            )

        if not self.is_connected():
            return NavigationResult(
                navigation_id=f"nav_err_{secrets.token_hex(4)}",
                tab_id=tab_id,
                requested_url=normalized_url,
                status=NavigationStatus.FAILED,
                error={"code": "BRIDGE_DISCONNECTED", "message": "Browser Bridge is not connected"}
            )

        logger.info(f"[MATRIOSHAI][Navigation] REQUEST: browser.navigate | TAB: {tab_id} | TO: '{normalized_url}'")
        t0 = time.time()

        try:
            resp = await self.bridge.send_request(
                BridgeAction.BROWSER_NAVIGATE.value,
                {"tab_id": tab_id, "url": normalized_url, "timeout_ms": int(timeout_seconds * 1000)},
                timeout=timeout_seconds + 2.0
            )
            nav_data = resp.get("navigation", {})
            nav_result = NavigationResult(**nav_data)
            duration_ms = round((time.time() - t0) * 1000, 2)

            if nav_result.status == NavigationStatus.COMPLETED:
                logger.info(f"[MATRIOSHAI][Navigation] RESULT: SUCCESS | TAB: {tab_id} | FINAL_URL: '{nav_result.final_url}' | TOOK: {duration_ms}ms")
                self.state_store.record_audit_log(action_id, "browser.navigate", tab_id, normalized_url, "success")
            else:
                err_msg = nav_result.error.get("message") if nav_result.error else "Navigation did not complete"
                logger.warning(f"[MATRIOSHAI][Navigation] RESULT: FAILED | TAB: {tab_id} | REASON: '{err_msg}'")
                self.state_store.record_audit_log(action_id, "browser.navigate", tab_id, normalized_url, "failed", err_msg)

            return nav_result

        except Exception as e:
            duration_ms = round((time.time() - t0) * 1000, 2)
            err_str = str(e)
            logger.error(f"[MATRIOSHAI][Navigation] RESULT: EXCEPTION | TAB: {tab_id} | ERROR: {err_str} (Took: {duration_ms}ms)")
            self.state_store.record_audit_log(action_id, "browser.navigate", tab_id, normalized_url, "failed", err_str)
            code = "NAVIGATION_TIMEOUT" if "timed out" in err_str.lower() else "NAVIGATION_FAILED"
            return NavigationResult(
                navigation_id=f"nav_exc_{secrets.token_hex(4)}",
                tab_id=tab_id,
                requested_url=normalized_url,
                status=NavigationStatus.FAILED,
                error={"code": code, "message": err_str}
            )

    async def reload(self, tab_id: int, timeout_seconds: float = 15.0) -> NavigationResult:
        """Reload an existing tab."""
        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            raise RuntimeError("Browser Bridge is not connected")

        resp = await self.bridge.send_request(
            BridgeAction.BROWSER_RELOAD.value,
            {"tab_id": tab_id, "timeout_ms": int(timeout_seconds * 1000)},
            timeout=timeout_seconds + 2.0
        )
        nav_data = resp.get("navigation", {})
        res = NavigationResult(**nav_data)
        self.state_store.record_audit_log(action_id, "browser.reload", tab_id, None, "success" if res.status == NavigationStatus.COMPLETED else "failed")
        return res

    async def go_back(self, tab_id: int, timeout_seconds: float = 15.0) -> NavigationResult:
        """Go backward in history."""
        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            raise RuntimeError("Browser Bridge is not connected")

        resp = await self.bridge.send_request(
            BridgeAction.BROWSER_GO_BACK.value,
            {"tab_id": tab_id, "timeout_ms": int(timeout_seconds * 1000)},
            timeout=timeout_seconds + 2.0
        )
        nav_data = resp.get("navigation", {})
        res = NavigationResult(**nav_data)
        self.state_store.record_audit_log(action_id, "browser.goBack", tab_id, None, "success" if res.status == NavigationStatus.COMPLETED else "failed")
        return res

    async def go_forward(self, tab_id: int, timeout_seconds: float = 15.0) -> NavigationResult:
        """Go forward in history."""
        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            raise RuntimeError("Browser Bridge is not connected")

        resp = await self.bridge.send_request(
            BridgeAction.BROWSER_GO_FORWARD.value,
            {"tab_id": tab_id, "timeout_ms": int(timeout_seconds * 1000)},
            timeout=timeout_seconds + 2.0
        )
        nav_data = resp.get("navigation", {})
        res = NavigationResult(**nav_data)
        self.state_store.record_audit_log(action_id, "browser.goForward", tab_id, None, "success" if res.status == NavigationStatus.COMPLETED else "failed")
        return res

    async def wait_for_navigation(self, tab_id: int, timeout_seconds: float = 15.0) -> TabState:
        """Wait for a tab to reach 'complete' loading state."""
        if not self.is_connected():
            raise RuntimeError("Browser Bridge is not connected")

        resp = await self.bridge.send_request(
            BridgeAction.BROWSER_WAIT_FOR_NAVIGATION.value,
            {"tab_id": tab_id, "timeout_ms": int(timeout_seconds * 1000)},
            timeout=timeout_seconds + 2.0
        )
        tab_data = resp.get("tab")
        if not tab_data:
            raise RuntimeError(f"Failed to wait for navigation on tab {tab_id}")
        tab = TabState(**tab_data)
        self.state_store.tabs[tab.tab_id] = tab
        return tab

    # ------------------------------------------------------------------------
    # PAGE OBSERVATION (PHASE 4)
    # ------------------------------------------------------------------------

    async def observe_page(self, tab_id: int, timeout_seconds: float = 10.0) -> PageObservation:
        """
        Request structured PageObservation for a specific Chrome tab.
        Extracts viewport, clean text blocks, semantic headings/landmarks,
        interactive elements with bounding boxes and visibility states, and frame hierarchies.
        """
        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            # If cached observation exists, return it; otherwise raise
            cached = self.state_store.get_observation(tab_id)
            if cached:
                return cached
            raise RuntimeError("Browser Bridge is not connected")

        t0 = time.time()
        logger.info(f"[MATRIOSHAI][Observation] REQUEST: page.observe | TAB: {tab_id}")

        try:
            resp = await self.bridge.send_request(
                BridgeAction.PAGE_OBSERVE.value,
                {"tab_id": tab_id},
                timeout=timeout_seconds
            )
            obs_data = resp.get("observation")
            if not obs_data:
                raise RuntimeError("Observation extraction returned empty data")

            observation = PageObservation(**obs_data)
            duration_ms = round((time.time() - t0) * 1000, 2)

            self.state_store.store_observation(observation)
            self.state_store.record_audit_log(action_id, "page.observe", tab_id, observation.url, "success")

            logger.info(
                f"[MATRIOSHAI][Observation] RESULT: SUCCESS | TAB: {tab_id} | "
                f"URL: '{observation.url}' | "
                f"HEADINGS: {len(observation.headings)} | "
                f"ELEMENTS: {len(observation.interactive_elements)} | "
                f"TEXT_BLOCKS: {len(observation.visible_text)} | "
                f"TOOK: {duration_ms}ms"
            )
            return observation

        except Exception as e:
            duration_ms = round((time.time() - t0) * 1000, 2)
            err_str = str(e)
            logger.error(f"[MATRIOSHAI][Observation] RESULT: FAILED | TAB: {tab_id} | ERROR: {err_str} (Took: {duration_ms}ms)")
            self.state_store.record_audit_log(action_id, "page.observe", tab_id, None, "failed", err_str)
            raise e

    # ------------------------------------------------------------------------
    # SEMANTIC PAGE INTELLIGENCE (PHASE 5)
    # ------------------------------------------------------------------------

    async def get_semantic_page(self, tab_id: int, timeout_seconds: float = 10.0) -> SemanticPageModel:
        """
        Request complete SemanticPageModel with computed accessibility roles,
        accessible names, label relationships, and component groupings for a Chrome tab.
        """
        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            cached = self.state_store.get_semantic_model(tab_id)
            if cached:
                return cached
            raise RuntimeError("Browser Bridge is not connected")

        t0 = time.time()
        logger.info(f"[MATRIOSHAI][Semantic] REQUEST: page.semanticObserve | TAB: {tab_id}")

        try:
            resp = await self.bridge.send_request(
                BridgeAction.PAGE_SEMANTIC_OBSERVE.value,
                {"tab_id": tab_id},
                timeout=timeout_seconds
            )
            model_data = resp.get("semantic_model")
            if not model_data:
                raise RuntimeError("Semantic model extraction returned empty data")

            model = SemanticPageModel(**model_data)
            duration_ms = round((time.time() - t0) * 1000, 2)

            self.state_store.store_semantic_model(model)
            self.state_store.record_audit_log(action_id, "page.semanticObserve", tab_id, model.page.url, "success")

            logger.info(
                f"[MATRIOSHAI][Semantic] RESULT: SUCCESS | TAB: {tab_id} | "
                f"MODEL_ID: {model.semantic_model_id} (v{model.model_version}) | "
                f"ELEMENTS: {len(model.interactive_elements)} | "
                f"FORMS: {len(model.forms)} | "
                f"TOOK: {duration_ms}ms"
            )
            return model

        except Exception as e:
            duration_ms = round((time.time() - t0) * 1000, 2)
            err_str = str(e)
            logger.error(f"[MATRIOSHAI][Semantic] RESULT: FAILED | TAB: {tab_id} | ERROR: {err_str} (Took: {duration_ms}ms)")
            self.state_store.record_audit_log(action_id, "page.semanticObserve", tab_id, None, "failed", err_str)
            raise e

    async def query_page(self, tab_id: int, query_spec: Dict[str, Any], timeout_seconds: float = 10.0) -> QueryResult:
        """
        Execute deterministic semantic search against the active SemanticPageModel.
        Returns FOUND, NOT_FOUND, or AMBIGUOUS (with candidate matches). Never silently guesses.
        """
        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            # If we have a cached model, execute local query against it
            cached_model = self.state_store.get_semantic_model(tab_id)
            if cached_model:
                return self._local_query(cached_model, query_spec)
            raise RuntimeError("Browser Bridge is not connected")

        t0 = time.time()
        try:
            resp = await self.bridge.send_request(
                BridgeAction.PAGE_SEMANTIC_QUERY.value,
                {"tab_id": tab_id, "query": query_spec},
                timeout=timeout_seconds
            )
            res_data = resp.get("result", {})
            result = QueryResult(**res_data)
            duration_ms = round((time.time() - t0) * 1000, 2)
            logger.info(f"[MATRIOSHAI][SemanticQuery] STATUS: {result.status} | MATCHES: {len(result.matches)} | TOOK: {duration_ms}ms")
            return result
        except Exception as e:
            logger.error(f"[MATRIOSHAI][SemanticQuery] FAILED: {e}")
            raise e

    async def resolve_element(self, tab_id: int, reference_spec: Dict[str, Any], timeout_seconds: float = 10.0) -> ResolveResult:
        """
        Verify if a SemanticElementRef still exists in the live page model.
        Returns FOUND, NOT_FOUND, AMBIGUOUS, or STALE.
        """
        if not self.is_connected():
            raise RuntimeError("Browser Bridge is not connected")

        t0 = time.time()
        try:
            resp = await self.bridge.send_request(
                BridgeAction.PAGE_RESOLVE_ELEMENT.value,
                {"tab_id": tab_id, "reference": reference_spec},
                timeout=timeout_seconds
            )
            res_data = resp.get("result", {})
            result = ResolveResult(**res_data)
            duration_ms = round((time.time() - t0) * 1000, 2)
            logger.info(f"[MATRIOSHAI][ResolveElement] STATUS: {result.status} | TOOK: {duration_ms}ms")
            return result
        except Exception as e:
            logger.error(f"[MATRIOSHAI][ResolveElement] FAILED: {e}")
            raise e

    async def invalidate_semantic_model(self, tab_id: int):
        """Invalidate the cached SemanticPageModel for a tab."""
        self.state_store.invalidate_semantic_model(tab_id)
        if self.is_connected():
            try:
                await self.bridge.send_request(BridgeAction.PAGE_INVALIDATE_SEMANTIC_MODEL.value, {"tab_id": tab_id})
            except Exception:
                pass

    def _local_query(self, model: SemanticPageModel, query_spec: Dict[str, Any]) -> QueryResult:
        """Execute local query evaluation against a cached SemanticPageModel."""
        q = SemanticQuery(**query_spec)
        candidates = []
        for el in model.interactive_elements:
            match = True
            if q.role and el.role.lower() != q.role.lower():
                match = False
            if q.name and el.name.lower() != q.name.lower():
                match = False
            if q.label and el.name.lower() != q.label.lower() and (not el.relationships.labelled_by or el.relationships.labelled_by.lower() != q.label.lower()):
                match = False
            if q.id and el.attributes.get("id") != q.id and el.element_id != q.id:
                match = False
            if match:
                candidates.append(el)

        refs = [
            SemanticElementRef(
                semantic_model_id=model.semantic_model_id,
                observation_id=model.observation_id,
                element_id=el.element_id,
                role=el.role,
                name=el.name,
                tag_name=el.tag_name,
                stable_id=el.attributes.get("id"),
                attributes=el.attributes
            )
            for el in candidates
        ]

        if len(candidates) == 0:
            return QueryResult(status="NOT_FOUND", matches=[], query=q, message="No element found matching query")
        if len(candidates) == 1:
            return QueryResult(status="FOUND", element=candidates[0], matches=refs, query=q, message="Found unique element")
        return QueryResult(status="AMBIGUOUS", matches=refs, query=q, message=f"Matched {len(refs)} elements. Ambiguity detected.")

    # ------------------------------------------------------------------------
    # PHASE 6: VISUAL PAGE INTELLIGENCE METHODS
    # ------------------------------------------------------------------------

    async def capture_screenshot(
        self,
        tab_id: Optional[int] = None,
        format: str = "png",
        privacy_mode: str = "STANDARD",
        timeout_seconds: float = 10.0
    ) -> Dict[str, Any]:
        """
        Capture visible viewport screenshot for a specific tab.
        """
        target_tab_id = tab_id
        if not target_tab_id:
            active_tab = self.get_active_tab()
            if active_tab:
                target_tab_id = active_tab.tab_id
            else:
                raise RuntimeError("No active tab available for screenshot capture")

        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            self.state_store.record_audit_log(
                action_id, "page.captureScreenshot", target_tab_id, None, "failed", "Extension bridge is not connected"
            )
            raise ConnectionError("Browser extension bridge is not connected")

        try:
            resp = await self.bridge.send_request(
                BridgeAction.PAGE_CAPTURE_SCREENSHOT.value,
                {
                    "tab_id": target_tab_id,
                    "format": format,
                    "privacy_mode": privacy_mode
                },
                timeout_seconds=timeout_seconds
            )

            screenshot_dict = resp.get("screenshot", {})
            data_url = resp.get("data_url", "")

            screenshot_meta = ScreenshotMetadata(**screenshot_dict)
            self.state_store.latest_screenshots[target_tab_id] = data_url

            self.state_store.record_audit_log(
                action_id, "page.captureScreenshot", target_tab_id, None, "success"
            )
            return {
                "screenshot": screenshot_meta,
                "data_url": data_url
            }
        except Exception as e:
            self.state_store.record_audit_log(
                action_id, "page.captureScreenshot", target_tab_id, None, "failed", str(e)
            )
            raise

    async def get_visual_page(
        self,
        tab_id: Optional[int] = None,
        privacy_mode: str = "STANDARD",
        force_refresh: bool = False,
        timeout_seconds: float = 10.0
    ) -> VisualPageModel:
        """
        Produce a full VisualPageModel combining DOM observation, SemanticPageModel,
        screenshot capture, coordinate spaces, and visual regions.
        """
        target_tab_id = tab_id
        if not target_tab_id:
            active_tab = self.get_active_tab()
            if active_tab:
                target_tab_id = active_tab.tab_id
            else:
                raise RuntimeError("No active tab available for visual page observation")

        # Return cached model if valid
        if not force_refresh:
            cached = self.state_store.get_visual_model(target_tab_id)
            if cached and not cached.is_stale:
                return cached

        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            self.state_store.record_audit_log(
                action_id, "page.visualObserve", target_tab_id, None, "failed", "Extension bridge is not connected"
            )
            raise ConnectionError("Browser extension bridge is not connected")

        try:
            resp = await self.bridge.send_request(
                BridgeAction.PAGE_VISUAL_OBSERVE.value,
                {
                    "tab_id": target_tab_id,
                    "privacy_mode": privacy_mode
                },
                timeout_seconds=timeout_seconds
            )

            raw_model = resp.get("visual_model", {})
            screenshot_data_url = resp.get("screenshot_data_url")

            model = VisualPageModel(**raw_model)
            self.state_store.store_visual_model(model, screenshot_data_url)

            self.state_store.record_audit_log(
                action_id, "page.visualObserve", target_tab_id, None, "success"
            )
            return model
        except Exception as e:
            self.state_store.record_audit_log(
                action_id, "page.visualObserve", target_tab_id, None, "failed", str(e)
            )
            raise

    async def query_visual_point(
        self,
        tab_id: Optional[int] = None,
        x: int = 0,
        y: int = 0,
        coordinate_system: str = "DOM_VIEWPORT",
        privacy_mode: str = "STANDARD",
        timeout_seconds: float = 10.0
    ) -> PointQueryResult:
        """
        Find visual elements at specified coordinates (x, y) with z-order stack ranking.
        Does NOT click or execute any actions.
        """
        target_tab_id = tab_id
        if not target_tab_id:
            active_tab = self.get_active_tab()
            if active_tab:
                target_tab_id = active_tab.tab_id
            else:
                raise RuntimeError("No active tab available for point query")

        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            self.state_store.record_audit_log(
                action_id, "page.visualPointQuery", target_tab_id, None, "failed", "Extension bridge is not connected"
            )
            raise ConnectionError("Browser extension bridge is not connected")

        try:
            resp = await self.bridge.send_request(
                BridgeAction.PAGE_VISUAL_POINT_QUERY.value,
                {
                    "tab_id": target_tab_id,
                    "x": x,
                    "y": y,
                    "coordinate_system": coordinate_system,
                    "privacy_mode": privacy_mode
                },
                timeout_seconds=timeout_seconds
            )

            raw_result = resp.get("result", {})
            point_result = PointQueryResult(**raw_result)

            self.state_store.record_audit_log(
                action_id, "page.visualPointQuery", target_tab_id, None, "success"
            )
            return point_result
        except Exception as e:
            self.state_store.record_audit_log(
                action_id, "page.visualPointQuery", target_tab_id, None, "failed", str(e)
            )
            raise

    async def query_visual_page(
        self,
        tab_id: Optional[int] = None,
        query: Optional[Dict[str, Any]] = None,
        privacy_mode: str = "STANDARD",
        timeout_seconds: float = 10.0
    ) -> VisualQueryResult:
        """
        Query visual elements by type, region, interactive flag, or confidence.
        """
        target_tab_id = tab_id
        if not target_tab_id:
            active_tab = self.get_active_tab()
            if active_tab:
                target_tab_id = active_tab.tab_id
            else:
                raise RuntimeError("No active tab available for visual query")

        query_payload = query or {}
        action_id = f"act_{secrets.token_hex(4)}"
        if not self.is_connected():
            self.state_store.record_audit_log(
                action_id, "page.visualQuery", target_tab_id, None, "failed", "Extension bridge is not connected"
            )
            raise ConnectionError("Browser extension bridge is not connected")

        try:
            resp = await self.bridge.send_request(
                BridgeAction.PAGE_VISUAL_QUERY.value,
                {
                    "tab_id": target_tab_id,
                    "query": query_payload,
                    "privacy_mode": privacy_mode
                },
                timeout_seconds=timeout_seconds
            )

            raw_result = resp.get("result", {})
            query_result = VisualQueryResult(**raw_result)

            self.state_store.record_audit_log(
                action_id, "page.visualQuery", target_tab_id, None, "success"
            )
            return query_result
        except Exception as e:
            self.state_store.record_audit_log(
                action_id, "page.visualQuery", target_tab_id, None, "failed", str(e)
            )
            raise

    def invalidate_visual_model(self, tab_id: int):
        """Invalidate cached visual model for a tab."""
        self.state_store.invalidate_visual_model(tab_id)

    # ------------------------------------------------------------------------
    # PHASE 7: UNIFIED BROWSER WORLD MODEL METHODS
    # ------------------------------------------------------------------------

    async def get_world_model(
        self,
        force_refresh: bool = False,
        timeout_seconds: float = 10.0
    ) -> BrowserWorldModel:
        """
        Produce the canonical BrowserWorldModel synthesized across all windows,
        tabs, active page states, frame trees, observations, and temporal transitions.
        """
        action_id = f"act_{secrets.token_hex(4)}"
        active_tab = self.get_active_tab()

        if self.is_connected() and active_tab and force_refresh:
            try:
                resp = await self.bridge.send_request(
                    "page.getWorldPageState",
                    {"tab_id": active_tab.tab_id},
                    timeout_seconds=timeout_seconds
                )

                if "page_state" in resp:
                    page_state = WorldPageState(**resp["page_state"])
                    self.state_store.page_states[active_tab.tab_id] = page_state

                if "frame_tree" in resp:
                    frame_tree = FrameTree(**resp["frame_tree"])
                    self.state_store.frame_trees[active_tab.tab_id] = frame_tree

                if "world_elements" in resp:
                    elements = [WorldElement(**el) for el in resp["world_elements"]]
                    self.state_store.world_elements[active_tab.tab_id] = elements

                if "observation" in resp:
                    self.state_store.store_observation(PageObservation(**resp["observation"]))

                if "semantic_model" in resp:
                    self.state_store.store_semantic_model(SemanticPageModel(**resp["semantic_model"]))

                if "visual_model" in resp:
                    self.state_store.store_visual_model(VisualPageModel(**resp["visual_model"]))

                self.state_store.record_audit_log(
                    action_id, "world.getCurrent", active_tab.tab_id, None, "success"
                )
            except Exception as e:
                logger.warning(f"[MATRIOSHAI][BrowserManager] Error extracting live world page state: {e}")

        world_model = world_model_engine.build_current_world(
            bridge_connected=self.is_connected(),
            session_id=self.bridge.session_id if hasattr(self.bridge, "session_id") else None
        )
        return world_model

    async def create_world_snapshot(
        self,
        reason: Optional[str] = None
    ) -> BrowserWorldSnapshot:
        """
        Create an immutable snapshot of the browser world model at this exact instant.
        """
        snapshot = world_model_engine.create_snapshot(
            reason=reason,
            bridge_connected=self.is_connected()
        )
        return snapshot

    def diff_world(
        self,
        source_snapshot_id: str,
        target_snapshot_id: str
    ) -> WorldStateDiff:
        """
        Compute deterministic diff between two historical immutable snapshots.
        """
        snap_a = self.state_store.get_world_snapshot(source_snapshot_id)
        snap_b = self.state_store.get_world_snapshot(target_snapshot_id)

        if not snap_a:
            raise ValueError(f"Source snapshot '{source_snapshot_id}' not found in history.")
        if not snap_b:
            raise ValueError(f"Target snapshot '{target_snapshot_id}' not found in history.")

        return world_model_engine.diff_world(snap_a, snap_b)

    def query_world(
        self,
        query_spec: Dict[str, Any]
    ) -> WorldQueryResult:
        """
        Execute structured query against the Browser World Model.
        """
        q = WorldQuery(**query_spec)
        return world_model_engine.query_world(q)

    async def resolve_world_element(
        self,
        reference: Dict[str, Any],
        tab_id: Optional[int] = None,
        timeout_seconds: float = 10.0
    ) -> WorldElementResolution:
        """
        Canonical resolution of a WorldElementRef across page identity, versioning,
        and current DOM/semantic state.
        """
        ref = WorldElementRef(**reference)
        target_tab = tab_id or self.state_store.active_tab_id

        # First resolve locally from WorldModelEngine
        local_res = world_model_engine.resolve_world_element(ref, target_tab)
        if local_res.status in ["PAGE_CHANGED", "TAB_CLOSED", "STALE"]:
            return local_res

        # If bridge is available, query content script directly for live verification
        if self.is_connected() and target_tab:
            try:
                resp = await self.bridge.send_request(
                    BridgeAction.WORLD_RESOLVE_ELEMENT.value,
                    {"tab_id": target_tab, "reference": ref.model_dump()},
                    timeout_seconds=timeout_seconds
                )
                if "resolution" in resp:
                    return WorldElementResolution(**resp["resolution"])
            except Exception as e:
                logger.debug(f"[MATRIOSHAI][BrowserManager] Content script element resolution fallback: {e}")

        return local_res

    def validate_world(self) -> Dict[str, Any]:
        """
        Validate internal consistency of the current World Model.
        """
        world = world_model_engine.build_current_world(self.is_connected())
        return world_model_engine.validate_world(world)

    async def reconcile_world(self) -> BrowserWorldModel:
        """
        Force active browser reconciliation and resynchronization.
        """
        await self.refresh_browser_state()
        return await self.get_world_model(force_refresh=True)

    def check_world_health(self) -> WorldHealth:
        """
        Check health status of the Browser World Model.
        """
        return world_model_engine.check_health(self.is_connected())

    def get_world_history(self) -> List[BrowserWorldSnapshot]:
        """
        Retrieve historical immutable snapshots.
        """
        return self.state_store.get_world_snapshots()

    def invalidate_world_model(self):
        """
        Increment world model version and invalidate cached artifacts.
        """
        self.state_store.world_model_version += 1

    # ------------------------------------------------------------------------
    # PHASE 8: SAFE BROWSER ACTION ENGINE METHODS
    # ------------------------------------------------------------------------

    async def execute_action(
        self,
        intent: ActionIntent,
        confirmed: bool = False
    ) -> ActionResult:
        """
        Safely validate, resolve, and execute a deterministic browser action intent.
        """
        action_engine.bridge_server = self.bridge
        result = await action_engine.execute_action(intent, confirmed=confirmed)

        # Record action in audit logs
        self.state_store.record_audit_log(
            action_id=intent.action_id,
            action_type=f"action.{intent.type.value.lower()}",
            tab_id=intent.tab_id,
            requested_url=intent.parameters.get("url") if intent.parameters else None,
            result=result.status.value,
            error=result.error.message if result.error else None
        )

        return result

    async def validate_action(
        self,
        intent: ActionIntent
    ) -> ActionResult:
        """
        Dry-run validation of an action intent without performing DOM mutations.
        """
        dry_intent = intent.model_copy(deep=True)
        if not dry_intent.parameters:
            dry_intent.parameters = {}
        dry_intent.parameters["dry_run"] = True

        return await self.execute_action(dry_intent)

    async def confirm_action(
        self,
        confirmation_id: str,
        approved: bool,
        user_note: Optional[str] = None
    ) -> ActionResult:
        """
        Approve or reject a pending high-impact action confirmation request.
        """
        conf = self.state_store.pending_confirmations.get(confirmation_id)
        if not conf:
            raise ValueError(f"Confirmation request '{confirmation_id}' not found or expired.")

        conf.status = "APPROVED" if approved else "REJECTED"

        if not approved:
            return ActionResult(
                action_id=conf.action_id,
                type=conf.action_type,
                status=ActionStatus.CANCELLED,
                started_at=conf.requested_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=0.0,
                world_model_version_before=self.state_store.world_model_version,
                world_model_version_after=self.state_store.world_model_version,
                trace=ActionTrace(action_id=conf.action_id, steps=[
                    ActionTraceStep(stage="CONFIRMATION_CHECKED", status="FAIL", detail=f"User rejected confirmation: {user_note or 'No reason given'}")
                ]),
                error=ActionErrorDetail(code="USER_REJECTED", message="Action cancelled by user")
            )

        # Retrieve action intent from queue or reconstruct
        queue = self.state_store.tab_action_queues.get(self.state_store.active_tab_id or 1, [])
        matching_intent = next((it for it in queue if it.action_id == conf.action_id), None)
        if not matching_intent:
            matching_intent = ActionIntent(
                action_id=conf.action_id,
                type=conf.action_type,
                target=ActionTarget(expected_name=conf.target_description),
                world_model_version=self.state_store.world_model_version,
                page_version=1,
                created_at=conf.requested_at
            )

        return await self.execute_action(matching_intent, confirmed=True)

    def get_action_queue(self, tab_id: int) -> ActionQueueStatus:
        """
        Get the current action queue status for a tab.
        """
        return action_engine.queue_manager.get_queue_status(tab_id)

    def get_action_trace(self, action_id: str) -> Optional[ActionTrace]:
        """
        Get the execution trace of an action.
        """
        return self.state_store.action_traces.get(action_id)

    def get_action_history(self, limit: int = 50) -> List[ActionResult]:
        """
        Get recent action execution results.
        """
        return self.state_store.action_history[-limit:]

    # ------------------------------------------------------------------------
    # PHASE 9: ACTION VERIFICATION & RECOVERY METHODS
    # ------------------------------------------------------------------------

    async def execute_and_verify(
        self,
        intent: ActionIntent,
        wait_policy: Optional[VerificationWaitPolicy] = None,
        confirmed: bool = False
    ) -> Tuple[ActionResult, VerificationResult]:
        """
        Execute an action and verify its outcome against before/after world snapshots and postconditions.
        """
        # 1. Capture before-snapshot
        snap_before = await self.create_world_snapshot(reason=f"pre_action_{intent.action_id}")

        # 2. Execute action
        action_result = await self.execute_action(intent, confirmed=confirmed)

        # 3. If live browser connected, refresh state
        if self.is_connected():
            await self.refresh_browser_state()

        # 4. Capture after-snapshot
        snap_after = await self.create_world_snapshot(reason=f"post_action_{intent.action_id}")

        # 5. Verify outcome
        verification = await verification_engine.verify_action(
            action_result=action_result,
            before_snapshot=snap_before,
            after_snapshot=snap_after,
            wait_policy=wait_policy
        )

        return action_result, verification

    async def verify_action_result(
        self,
        action_result: ActionResult,
        before_snapshot_id: Optional[str] = None,
        after_snapshot_id: Optional[str] = None,
        wait_policy: Optional[VerificationWaitPolicy] = None
    ) -> VerificationResult:
        """
        Evaluate standalone verification against explicit snapshot IDs.
        """
        snapshots = {s.snapshot_id: s for s in self.state_store.get_world_snapshots()}
        snap_before = snapshots.get(before_snapshot_id) if before_snapshot_id else None
        snap_after = snapshots.get(after_snapshot_id) if after_snapshot_id else None

        return await verification_engine.verify_action(
            action_result=action_result,
            before_snapshot=snap_before,
            after_snapshot=snap_after,
            wait_policy=wait_policy
        )

    def resolve_user_intervention(
        self,
        intervention_id: str,
        status: str = "RESOLVED"
    ) -> Optional[UserInterventionRequest]:
        """
        Resolve a user intervention request and resume workflow state.
        """
        req = self.state_store.user_interventions.get(intervention_id)
        if req:
            req.status = status
            req.resolved_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"[MATRIOSHAI][Verification] User intervention '{intervention_id}' marked as {status}")
        return req

    def get_user_interventions(self) -> List[UserInterventionRequest]:
        """List active/recent user intervention requests."""
        return list(self.state_store.user_interventions.values())

    def create_checkpoint(
        self,
        name: str,
        step_index: int,
        tab_id: Optional[int] = None
    ) -> WorkflowCheckpoint:
        """Create a resumable workflow checkpoint."""
        snapshots = self.state_store.get_world_snapshots()
        latest_snap_id = snapshots[-1].snapshot_id if snapshots else f"snap_{self.state_store.world_model_version}"
        return verification_engine.checkpoint_manager.create_checkpoint(
            name=name,
            step_index=step_index,
            snapshot_id=latest_snap_id,
            tab_id=tab_id
        )

    def get_checkpoints(self) -> List[WorkflowCheckpoint]:
        """List workflow checkpoints."""
        return verification_engine.checkpoint_manager.get_checkpoints()

    def get_verification(self, verification_id: str) -> Optional[VerificationResult]:
        """Get verification result by ID."""
        return self.state_store.verifications.get(verification_id)

    # ------------------------------------------------------------------------
    # PHASE 12: REAL-WORLD TRANSACTION & BOOKING ENGINE METHODS
    # ------------------------------------------------------------------------

    def create_transaction(self, user_request: str, workflow_id: Optional[str] = None) -> Transaction:
        """Create and normalize a new transaction goal."""
        return transaction_engine.create_transaction(user_request, workflow_id=workflow_id)

    def update_transaction_options(
        self,
        transaction_id: str,
        options: List[TransactionOption]
    ) -> Tuple[Transaction, Optional[TransactionOption], bool, str]:
        """Update and score comparison options for a transaction."""
        return transaction_engine.update_options(transaction_id, options)

    def prepare_transaction_review(self, transaction_id: str) -> TransactionReview:
        """Freeze snapshot and prepare pre-commit review package."""
        return transaction_engine.prepare_review(transaction_id)

    def confirm_transaction(
        self,
        transaction_id: str,
        user_note: Optional[str] = None
    ) -> Tuple[TransactionConfirmation, CommitAuthorization]:
        """Record explicit user confirmation and generate scoped commit authorization."""
        return transaction_engine.confirm_transaction(transaction_id, user_note=user_note)

    async def commit_transaction(
        self,
        transaction_id: str,
        commit_action: ActionIntent,
        auth: Optional[CommitAuthorization] = None
    ) -> Tuple[TransactionState, Optional[TransactionReceipt], str]:
        """Execute commit action with drift detection, idempotency, and verification."""
        return await transaction_engine.commit_transaction(transaction_id, commit_action, auth=auth)

    def cancel_transaction(self, transaction_id: str, reason: str = "User cancelled") -> Transaction:
        """Cancel a transaction and release resources."""
        return transaction_engine.cancel_transaction(transaction_id, reason=reason)

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction entity by ID."""
        return self.state_store.transactions.get(transaction_id)

    def get_transaction_receipt(self, receipt_id: str) -> Optional[TransactionReceipt]:
        """Get verified transaction receipt by ID."""
        return self.state_store.transaction_receipts.get(receipt_id)

    # ------------------------------------------------------------------------
    # PHASE 13: SECURITY, PERMISSIONS & HUMAN-IN-THE-LOOP METHODS
    # ------------------------------------------------------------------------

    def evaluate_security_request(
        self,
        request: SecurityRequest
    ) -> Tuple[SecurityDecision, Optional[ActionAuthorization], str]:
        """Evaluate an operation against domain permissions, risk policies, and human takeover."""
        return security_engine.evaluate_request(request)

    def grant_domain_permission(
        self,
        domain: str,
        permissions: List[PermissionCategory],
        scope: PermissionScope = PermissionScope.DOMAIN,
        trust_level: DomainTrustLevel = DomainTrustLevel.TRUSTED,
        ttl_minutes: Optional[int] = 60,
        actor: SecurityActor = SecurityActor.USER
    ) -> DomainPermission:
        """Grant scoped domain permissions."""
        return security_engine.permissions.grant_permission(
            domain=domain,
            permissions=permissions,
            scope=scope,
            trust_level=trust_level,
            ttl_minutes=ttl_minutes,
            actor=actor
        )

    def revoke_domain_permission(self, domain: str) -> bool:
        """Immediately revoke all permissions for a domain."""
        return security_engine.permissions.revoke_permission(domain)

    def set_human_takeover(self, state: TakeoverState) -> TakeoverState:
        """Set human takeover state."""
        return security_engine.takeover.set_takeover_state(state)

    def trigger_emergency_stop(self, reason: str = "User activated emergency kill switch") -> bool:
        """Trigger global emergency stop kill switch."""
        return security_engine.emergency_stop.trigger_emergency_stop(reason)

    def reset_emergency_stop(self) -> bool:
        """Reset emergency stop."""
        return security_engine.emergency_stop.reset_emergency_stop()

    def get_security_state(self) -> Dict[str, Any]:
        """Retrieve high-level security state summary."""
        return {
            "autonomy_level": self.state_store.autonomy_level.value,
            "takeover_state": self.state_store.takeover_state.value,
            "emergency_stop_active": self.state_store.emergency_stop_active,
            "active_permissions_count": len([p for p in self.state_store.domain_permissions.values() if p.status == "ACTIVE"]),
            "domain_permissions": {k: v.model_dump() for k, v in self.state_store.domain_permissions.items()},
            "blocked_domains": list(self.state_store.blocked_domains),
            "pending_authorizations_count": len(self.state_store.action_authorizations),
            "spending_limits": [s.model_dump() for s in self.state_store.spending_limits]
        }

    def get_security_audit_logs(self, limit: int = 50) -> List[SecurityAuditEvent]:
        """Retrieve recent security audit events."""
        return self.state_store.security_audit_events[-limit:]

    # ------------------------------------------------------------------------
    # PHASE 14: PRODUCTION HARDENING, OBSERVABILITY & RUNTIME METHODS
    # ------------------------------------------------------------------------

    def get_runtime_status(self) -> Dict[str, Any]:
        """Get complete runtime status, state, health, and metrics."""
        return matrioshai_runtime.get_status()

    def get_all_component_health(self) -> Dict[str, Any]:
        """Get health status of all 14 architectural subsystems."""
        return {
            "components": {k: v.model_dump() for k, v in self.state_store.component_health.items()},
            "runtime_state": self.state_store.runtime_state.value
        }

    def restart_component(self, component_name: str) -> Tuple[bool, str]:
        """Trigger supervisor restart of a component with restart loop protection."""
        return matrioshai_runtime.supervisor.attempt_restart(component_name)

    def get_runtime_metrics(self) -> Dict[str, Any]:
        """Get real-time operational and resource metrics."""
        return observability_manager.get_metrics_summary()

    def get_dead_letter_items(self, limit: int = 50) -> List[DeadLetterItem]:
        """Get items from the Dead Letter Queue."""
        return dead_letter_queue.get_items(limit)

    def inject_chaos_fault(self, fault_type: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        """Inject controlled failure for chaos testing."""
        fault_injection.inject_fault(fault_type, parameters)

    def clear_chaos_faults(self) -> None:
        """Clear all active fault injections."""
        fault_injection.clear_all_faults()

    # ------------------------------------------------------------------------
    # STATE RECONCILIATION
    # ------------------------------------------------------------------------

    async def refresh_browser_state(self) -> Dict[str, Any]:
        """Force full state reconciliation against the live Chrome browser."""
        if not self.is_connected():
            return self.state_store.get_summary()

        try:
            resp = await self.bridge.send_request(BridgeAction.BROWSER_REFRESH_STATE.value)
            windows_data = resp.get("windows", [])
            tabs_data = resp.get("tabs", [])
            active_tab_data = resp.get("active_tab")

            self.state_store.reconcile_state(windows_data, tabs_data, active_tab_data)
            return self.state_store.get_summary()
        except Exception as e:
            logger.warning(f"[MATRIOSHAI][BrowserManager] Error refreshing state: {e}")
            return self.state_store.get_summary()

    def get_audit_logs(self, limit: int = 50) -> List[BrowserAuditLog]:
        """Retrieve recent audit logs."""
        return self.state_store.get_audit_logs(limit)

# Global BrowserManager instance
browser_manager = BrowserManager()
