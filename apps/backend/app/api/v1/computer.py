from typing import Optional
from fastapi import APIRouter, HTTPException, status
from app.computer.models import (
    ComputerStatusResponse, ComputerSessionResponse, ScreenshotCaptureResponse,
    VisionAnalysisResponse, OCRResult, ApplicationContext, ActionApprovalRequest,
    ComputerPrivacyMode, MouseAction, KeyboardAction
)
from app.computer.service import computer_service
from app.computer.screen import screen_service
from app.computer.vision import vision_service
from app.computer.ocr import ocr_service
from app.computer.applications import application_service
from app.computer.mouse import mouse_service
from app.computer.keyboard import keyboard_service

router = APIRouter(prefix="/computer", tags=["Multimodal Computer Use"])

@router.get("/status", response_model=ComputerStatusResponse)
def get_computer_status():
    return computer_service.get_status()

@router.post("/emergency-stop", response_model=ComputerStatusResponse)
def emergency_stop():
    computer_service.emergency_stop()
    return computer_service.get_status()

@router.post("/session/start", response_model=ComputerSessionResponse)
def start_session(task_id: Optional[str] = None):
    return computer_service.start_session(task_id)

@router.post("/session/stop", response_model=Optional[ComputerSessionResponse])
def stop_session():
    return computer_service.stop_session()

@router.post("/screenshot", response_model=ScreenshotCaptureResponse)
def capture_screenshot():
    return screen_service.capture_full_screen()

@router.post("/ocr", response_model=OCRResult)
def run_ocr(screen_capture: ScreenshotCaptureResponse):
    return ocr_service.extract_text(screen_capture.base64_image)

@router.post("/analyze", response_model=VisionAnalysisResponse)
async def analyze_screen(screen_capture: ScreenshotCaptureResponse):
    return await vision_service.analyze_screen(screen_capture.base64_image)

@router.get("/application", response_model=ApplicationContext)
def get_active_application():
    return application_service.get_active_application()

@router.post("/mouse", response_model=dict)
def dispatch_mouse(action: MouseAction):
    ok, msg = mouse_service.execute_mouse_action(action)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}

@router.post("/keyboard", response_model=dict)
def dispatch_keyboard(action: KeyboardAction):
    ok, msg = keyboard_service.execute_keyboard_action(action)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}
