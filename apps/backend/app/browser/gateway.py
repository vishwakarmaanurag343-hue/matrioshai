import uuid
from typing import Dict, List, Optional
from app.browser.models import (
    BrowserTab, BrowserBookmark, BrowserHistoryItem, PageContextSummary, AdBlockStats
)
from app.browser.filter_list import filter_list_manager
from app.browser.context_extractor import browser_context_extractor
from app.security.audit import audit_logger

class BrowserGateway:
    """
    Central Browser Control Gateway:
    - Manages browser tab lifecycle (create, close, switch, navigate).
    - Tracks history and bookmarks securely without storing plain credentials.
    - Connects page context to Matrioshai AI assistant.
    """

    def __init__(self):
        self._tabs: Dict[str, BrowserTab] = {}
        self._history: List[BrowserHistoryItem] = []
        self._bookmarks: List[BrowserBookmark] = []
        
        # Initialize default tab
        initial_tab = BrowserTab(
            id=str(uuid.uuid4()),
            title="Matrioshai Search",
            url="https://matrioshai.local",
            is_active=True
        )
        self._tabs[initial_tab.id] = initial_tab

    def list_tabs(self) -> List[BrowserTab]:
        return list(self._tabs.values())

    def create_tab(self, url: str = "about:blank", title: str = "New Tab") -> BrowserTab:
        tab_id = str(uuid.uuid4())
        # Set all other tabs inactive
        for t in self._tabs.values():
            t.is_active = False

        tab = BrowserTab(
            id=tab_id,
            title=title,
            url=url,
            is_active=True
        )
        self._tabs[tab_id] = tab

        audit_logger.log_event(
            event_type="BROWSER_TAB_CREATED",
            action="create_tab",
            resource=tab_id,
            decision="ALLOWED"
        )
        return tab

    def close_tab(self, tab_id: str) -> bool:
        if tab_id in self._tabs:
            del self._tabs[tab_id]
            if self._tabs and not any(t.is_active for t in self._tabs.values()):
                # Make first remaining tab active
                next(iter(self._tabs.values())).is_active = True
            return True
        return False

    def switch_tab(self, tab_id: str) -> Optional[BrowserTab]:
        if tab_id in self._tabs:
            for t in self._tabs.values():
                t.is_active = (t.id == tab_id)
            return self._tabs[tab_id]
        return None

    def navigate_tab(self, tab_id: str, url: str) -> Optional[BrowserTab]:
        if tab_id in self._tabs:
            tab = self._tabs[tab_id]
            tab.url = url
            tab.title = url.replace("https://", "").replace("http://", "").split("/")[0]
            tab.is_secure = url.lower().startswith("https://") or url.lower().startswith("about:")

            # Record in history
            self._history.append(BrowserHistoryItem(
                id=str(uuid.uuid4()),
                title=tab.title,
                url=tab.url
            ))
            return tab
        return None

    def get_active_tab_context(self, raw_html: str = "") -> Optional[PageContextSummary]:
        active_tab = next((t for t in self._tabs.values() if t.is_active), None)
        if not active_tab:
            return None

        return browser_context_extractor.extract_context(
            url=active_tab.url,
            raw_html_or_text=raw_html or f"<html><body><h1>{active_tab.title}</h1><p>Welcome to {active_tab.url}</p></body></html>",
            title=active_tab.title
        )

browser_gateway = BrowserGateway()
