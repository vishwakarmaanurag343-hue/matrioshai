from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class BrowserPermissionType(str, Enum):
    READ_PAGE = "READ_PAGE"
    READ_DOM = "READ_DOM"
    CLICK = "CLICK"
    TYPE = "TYPE"
    SCROLL = "SCROLL"
    NAVIGATE = "NAVIGATE"
    SUBMIT_FORM = "SUBMIT_FORM"
    DOWNLOAD = "DOWNLOAD"

class BrowserTab(BaseModel):
    id: str
    title: str = "New Tab"
    url: str = "about:blank"
    favicon: Optional[str] = None
    is_active: bool = False
    is_loading: bool = False
    is_secure: bool = True
    created_at: datetime = Field(default_factory=utc_now)

class BrowserBookmark(BaseModel):
    id: str
    title: str
    url: str
    folder: str = "Bookmarks Bar"
    created_at: datetime = Field(default_factory=utc_now)

class BrowserHistoryItem(BaseModel):
    id: str
    title: str
    url: str
    visited_at: datetime = Field(default_factory=utc_now)
    visit_count: int = 1

class PageContextSummary(BaseModel):
    title: str
    url: str
    visible_text_summary: str
    headings: List[str] = Field(default_factory=list)
    links_count: int = 0
    forms_count: int = 0
    tables_count: int = 0
    is_secure_https: bool = True
    ads_blocked_count: int = 0

class AdBlockStats(BaseModel):
    total_blocked: int = 0
    trackers_blocked: int = 0
    ads_blocked: int = 0
    rules_loaded: int = 0
