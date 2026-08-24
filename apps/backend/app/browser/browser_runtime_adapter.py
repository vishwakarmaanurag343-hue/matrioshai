from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import time
import logging

logger = logging.getLogger("matrioshai.browser.runtime_adapter")


class ObservationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SERIALIZATION_FAILED = "SERIALIZATION_FAILED"
    EMPTY_CONFIRMED = "EMPTY_CONFIRMED"


class RuntimeType(str, Enum):
    CHROME_EXTENSION = "CHROME_EXTENSION"
    TAURI_WKWEBVIEW = "TAURI_WKWEBVIEW"
    HEADLESS = "HEADLESS"


class RobustElement(BaseModel):
    element_id: str
    role: str
    name: str
    tag: Optional[str] = None
    aria_label: Optional[str] = None
    title: Optional[str] = None
    href: Optional[str] = None
    input_type: Optional[str] = None
    placeholder: Optional[str] = None
    value: Optional[str] = None
    disabled: bool = False
    visible: bool = True
    selector: str
    rect: Optional[Dict[str, Any]] = None
    sensitive: bool = False
    accessible_name: Optional[str] = None
    enabled: bool = True
    is_searchbox: bool = False


class UniversalObservationResult(BaseModel):
    status: ObservationStatus
    runtime_type: RuntimeType
    url: str
    title: str
    ready_state: str = "complete"
    headings: List[str] = Field(default_factory=list)
    text_blocks: List[str] = Field(default_factory=list)
    interactive_elements: List[RobustElement] = Field(default_factory=list)
    links_count: int = 0
    forms_count: int = 0
    tables_count: int = 0
    timestamp: float = Field(default_factory=time.time)
    observation_failed: bool = False
    error_detail: Optional[str] = None


class ActionResult(BaseModel):
    success: bool
    action: str
    target: Optional[str] = None
    value: Optional[str] = None
    message: str
    risk_level: str = "Low"
    approval_required: bool = False
    error: Optional[str] = None


class BrowserRuntime(ABC):
    """
    Abstract Universal Browser Runtime Contract (Phase 15).
    Provides a decoupled interface for both Chrome (MV3 Extension) and Desktop (Tauri WKWebView).
    """

    @abstractmethod
    async def observe(self, tab_id: Optional[str] = None) -> UniversalObservationResult:
        """Extracts complete WAI-ARIA and DOM semantic representation from the live page."""
        pass

    @abstractmethod
    async def navigate(self, url: str, tab_id: Optional[str] = None) -> ActionResult:
        """Navigates to the specified URL."""
        pass

    @abstractmethod
    async def click(self, element_id: str, tab_id: Optional[str] = None) -> ActionResult:
        """Dispatches verified native click to the resolved element."""
        pass

    @abstractmethod
    async def type_text(self, element_id: str, text: str, tab_id: Optional[str] = None) -> ActionResult:
        """Types text into the target element."""
        pass

    @abstractmethod
    async def scroll(self, direction: str = "down", tab_id: Optional[str] = None) -> ActionResult:
        """Scrolls the active viewport."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Returns runtime connectivity, version, and bridge health status."""
        pass


class ChromeRuntime(BrowserRuntime):
    """
    Chrome Browser Runtime implementation powered by MV3 Extension & WebSocket Bridge.
    """

    def __init__(self, bridge_manager: Any = None):
        self.bridge_manager = bridge_manager
        self.runtime_type = RuntimeType.CHROME_EXTENSION

    async def observe(self, tab_id: Optional[str] = None) -> UniversalObservationResult:
        if not self.bridge_manager:
            return UniversalObservationResult(
                status=ObservationStatus.UNAVAILABLE,
                runtime_type=self.runtime_type,
                url="about:blank",
                title="Chrome Runtime Disconnected",
                observation_failed=True,
                error_detail="Chrome bridge manager not connected",
            )
        try:
            raw_obs = await self.bridge_manager.get_page_observation(tab_id=tab_id)
            elements = [
                RobustElement(
                    element_id=e.get("element_id", f"el_{i}"),
                    role=e.get("role", "button"),
                    name=e.get("name", ""),
                    tag=e.get("tag"),
                    href=e.get("href"),
                    selector=e.get("selector", f"[data-id='{i}']"),
                    visible=e.get("visible", True),
                    rect=e.get("rect"),
                    accessible_name=e.get("accessible_name") or e.get("name"),
                    enabled=not e.get("disabled", False),
                    is_searchbox=e.get("is_searchbox", False),
                )
                for i, e in enumerate(raw_obs.get("interactive_elements", []))
            ]
            status = ObservationStatus.SUCCESS if elements else ObservationStatus.EMPTY_CONFIRMED
            return UniversalObservationResult(
                status=status,
                runtime_type=self.runtime_type,
                url=raw_obs.get("url", ""),
                title=raw_obs.get("title", ""),
                headings=raw_obs.get("headings", []),
                text_blocks=raw_obs.get("text_blocks", []),
                interactive_elements=elements,
                links_count=raw_obs.get("links_count", len(elements)),
                forms_count=raw_obs.get("forms_count", 0),
                observation_failed=False,
            )
        except Exception as e:
            logger.error(f"[ChromeRuntime.observe] Error: {e}")
            return UniversalObservationResult(
                status=ObservationStatus.TIMEOUT,
                runtime_type=self.runtime_type,
                url="",
                title="Extraction Error",
                observation_failed=True,
                error_detail=str(e),
            )

    async def navigate(self, url: str, tab_id: Optional[str] = None) -> ActionResult:
        if not self.bridge_manager:
            return ActionResult(success=False, action="NAVIGATE", target=url, message="Chrome bridge not connected", error="DISCONNECTED")
        res = await self.bridge_manager.navigate(url=url, tab_id=tab_id)
        return ActionResult(success=res.get("success", True), action="NAVIGATE", target=url, message=f"Navigated to {url}")

    async def click(self, element_id: str, tab_id: Optional[str] = None) -> ActionResult:
        if not self.bridge_manager:
            return ActionResult(success=False, action="CLICK", target=element_id, message="Chrome bridge not connected", error="DISCONNECTED")
        res = await self.bridge_manager.execute_action(action="CLICK", target=element_id, tab_id=tab_id)
        return ActionResult(success=res.get("success", True), action="CLICK", target=element_id, message=f"Clicked {element_id}")

    async def type_text(self, element_id: str, text: str, tab_id: Optional[str] = None) -> ActionResult:
        if not self.bridge_manager:
            return ActionResult(success=False, action="TYPE", target=element_id, value=text, message="Chrome bridge not connected", error="DISCONNECTED")
        res = await self.bridge_manager.execute_action(action="TYPE", target=element_id, value=text, tab_id=tab_id)
        return ActionResult(success=res.get("success", True), action="TYPE", target=element_id, value=text, message=f"Typed text into {element_id}")

    async def scroll(self, direction: str = "down", tab_id: Optional[str] = None) -> ActionResult:
        if not self.bridge_manager:
            return ActionResult(success=False, action="SCROLL", message="Chrome bridge not connected", error="DISCONNECTED")
        res = await self.bridge_manager.execute_action(action="SCROLL", target=direction, tab_id=tab_id)
        return ActionResult(success=res.get("success", True), action="SCROLL", message=f"Scrolled {direction}")

    async def health_check(self) -> Dict[str, Any]:
        connected = self.bridge_manager is not None and getattr(self.bridge_manager, "is_connected", False)
        return {
            "runtime_type": self.runtime_type.value,
            "connected": connected,
            "status": "HEALTHY" if connected else "DISCONNECTED",
        }


class TauriWKWebViewRuntime(BrowserRuntime):
    """
    Desktop WKWebView Runtime implementation powered by Tauri IPC & Native JavaScript Injection Engine.
    """

    def __init__(self, tauri_client: Any = None):
        self.tauri_client = tauri_client
        self.runtime_type = RuntimeType.TAURI_WKWEBVIEW

    async def observe(self, tab_id: Optional[str] = None) -> UniversalObservationResult:
        if not self.tauri_client:
            return UniversalObservationResult(
                status=ObservationStatus.UNAVAILABLE,
                runtime_type=self.runtime_type,
                url="about:blank",
                title="WKWebView Disconnected",
                observation_failed=True,
                error_detail="Tauri IPC client not connected",
            )
        try:
            res = await self.tauri_client.invoke("browser_get_semantic_page", {"tab_id": tab_id})
            obs_failed = res.get("observation_failed", False)
            raw_elements = res.get("interactive_elements", [])
            elements = [
                RobustElement(
                    element_id=e.get("element_id", f"el_{i}"),
                    role=e.get("role", "button"),
                    name=e.get("name", ""),
                    tag=e.get("tag"),
                    aria_label=e.get("aria_label"),
                    title=e.get("title"),
                    href=e.get("href"),
                    input_type=e.get("input_type"),
                    placeholder=e.get("placeholder"),
                    value=e.get("value"),
                    disabled=e.get("disabled", False),
                    visible=e.get("visible", True),
                    selector=e.get("selector", f"[data-matrioshai-id='el_{i}']"),
                    rect=e.get("rect"),
                    sensitive=e.get("sensitive", False),
                    accessible_name=e.get("accessible_name") or e.get("name"),
                    enabled=e.get("enabled", not e.get("disabled", False)),
                    is_searchbox=e.get("is_searchbox", False),
                )
                for i, e in enumerate(raw_elements)
            ]
            status_str = res.get("observation_status", "SUCCESS")
            try:
                obs_status = ObservationStatus(status_str)
            except ValueError:
                obs_status = ObservationStatus.SUCCESS if elements else ObservationStatus.EMPTY_CONFIRMED

            return UniversalObservationResult(
                status=obs_status,
                runtime_type=self.runtime_type,
                url=res.get("url", ""),
                title=res.get("title", ""),
                headings=res.get("headings", []),
                text_blocks=res.get("text_blocks", []),
                interactive_elements=elements,
                links_count=res.get("links_count", len(elements)),
                forms_count=res.get("forms_count", 0),
                tables_count=res.get("tables_count", 0),
                observation_failed=obs_failed,
            )
        except Exception as e:
            logger.error(f"[TauriWKWebViewRuntime.observe] Error: {e}")
            return UniversalObservationResult(
                status=ObservationStatus.TIMEOUT,
                runtime_type=self.runtime_type,
                url="",
                title="WKWebView Observation Failed",
                observation_failed=True,
                error_detail=str(e),
            )

    async def navigate(self, url: str, tab_id: Optional[str] = None) -> ActionResult:
        if not self.tauri_client:
            return ActionResult(success=False, action="NAVIGATE", target=url, message="Tauri client not connected", error="DISCONNECTED")
        res = await self.tauri_client.invoke("ai_browser_execute_action", {
            "tab_id": tab_id or "default",
            "action": "NAVIGATE",
            "target": url,
            "user_approved": True,
        })
        return ActionResult(success=res.get("success", True), action="NAVIGATE", target=url, message=res.get("message", f"Navigated to {url}"))

    async def click(self, element_id: str, tab_id: Optional[str] = None) -> ActionResult:
        if not self.tauri_client:
            return ActionResult(success=False, action="CLICK", target=element_id, message="Tauri client not connected", error="DISCONNECTED")
        res = await self.tauri_client.invoke("ai_browser_execute_action", {
            "tab_id": tab_id or "default",
            "action": "CLICK",
            "target": element_id,
            "user_approved": True,
        })
        return ActionResult(success=res.get("success", True), action="CLICK", target=element_id, message=res.get("message", f"Clicked {element_id}"))

    async def type_text(self, element_id: str, text: str, tab_id: Optional[str] = None) -> ActionResult:
        if not self.tauri_client:
            return ActionResult(success=False, action="TYPE", target=element_id, value=text, message="Tauri client not connected", error="DISCONNECTED")
        res = await self.tauri_client.invoke("ai_browser_execute_action", {
            "tab_id": tab_id or "default",
            "action": "TYPE",
            "target": element_id,
            "value": text,
            "user_approved": True,
        })
        return ActionResult(success=res.get("success", True), action="TYPE", target=element_id, value=text, message=res.get("message", f"Typed into {element_id}"))

    async def scroll(self, direction: str = "down", tab_id: Optional[str] = None) -> ActionResult:
        if not self.tauri_client:
            return ActionResult(success=False, action="SCROLL", message="Tauri client not connected", error="DISCONNECTED")
        res = await self.tauri_client.invoke("ai_browser_execute_action", {
            "tab_id": tab_id or "default",
            "action": "SCROLL",
            "target": direction,
            "user_approved": True,
        })
        return ActionResult(success=res.get("success", True), action="SCROLL", message=f"Scrolled {direction}")

    async def health_check(self) -> Dict[str, Any]:
        return {
            "runtime_type": self.runtime_type.value,
            "connected": self.tauri_client is not None,
            "status": "HEALTHY" if self.tauri_client is not None else "STANDALONE",
        }
