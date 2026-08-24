from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class ComputerPrivacyMode(str, Enum):
    PRIVATE = "PRIVATE"           # Local only, no visual data leaves Mac
    LOCAL_ONLY = "LOCAL_ONLY"     # Local OCR/Vision only
    CLOUD_ALLOWED = "CLOUD_ALLOWED" # Cloud model vision after Privacy Gate evaluation
    PAUSED = "PAUSED"             # All perception disabled

class ComputerSessionStatus(str, Enum):
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

class ScreenMetadata(BaseModel):
    id: str
    width: int
    height: int
    scale_factor: float = 1.0
    is_main: bool = True
    timestamp: datetime = Field(default_factory=utc_now)

class ScreenshotCaptureResponse(BaseModel):
    id: str
    timestamp: datetime
    width: int
    height: int
    base64_image: str  # JPEG/PNG base64
    source: str = "full_screen"
    application: Optional[str] = None
    window_title: Optional[str] = None

class OCRRegion(BaseModel):
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float

class OCRResult(BaseModel):
    full_text: str
    regions: List[OCRRegion] = Field(default_factory=list)
    contains_sensitive_data: bool = False

class UIElement(BaseModel):
    type: str  # button, text_field, address_bar, dialog, link, icon
    label: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0

class VisionAnalysisResponse(BaseModel):
    application: Optional[str] = None
    description: str
    elements: List[UIElement] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)
    is_dialog_present: bool = False

class ApplicationContext(BaseModel):
    application: str
    bundle_id: Optional[str] = None
    window_title: Optional[str] = None
    window_bounds: Optional[Dict[str, int]] = None
    is_active: bool = True

class MouseAction(BaseModel):
    action: str  # move, click, double_click, right_click, scroll
    x: int
    y: int
    button: str = "left"
    scroll_amount: Optional[int] = None
    screen_id: Optional[str] = None

class KeyboardAction(BaseModel):
    action: str  # type_text, press_key, hotkey
    text: Optional[str] = None
    key: Optional[str] = None
    modifiers: List[str] = Field(default_factory=list)

class ComputerStatusResponse(BaseModel):
    computer_control_enabled: bool
    screen_recording_permission: str  # GRANTED, DENIED, NOT_CONFIGURED
    accessibility_permission: str     # GRANTED, DENIED, NOT_CONFIGURED
    privacy_mode: ComputerPrivacyMode
    active_session: Optional[str] = None

class ComputerSessionResponse(BaseModel):
    id: str
    task_id: Optional[str] = None
    status: ComputerSessionStatus
    privacy_mode: ComputerPrivacyMode
    active_application: Optional[str] = None
    screens_observed: int = 0
    actions_executed: int = 0
    started_at: datetime
    ended_at: Optional[datetime] = None

class ActionApprovalRequest(BaseModel):
    approved: bool
    rejection_reason: Optional[str] = None
