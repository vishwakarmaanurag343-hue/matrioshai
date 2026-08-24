import pytest
from app.computer.models import MouseAction, KeyboardAction, UIElement, ComputerPrivacyMode
from app.computer.policy import computer_policy
from app.computer.screen import screen_service
from app.computer.ocr import ocr_service
from app.computer.vision import vision_service
from app.computer.applications import application_service
from app.computer.service import computer_service
from app.security.permissions import tool_registry, ToolRequest, AutonomyTier

def test_screen_capture_and_metadata():
    cap = screen_service.capture_full_screen()
    assert cap.id is not None
    assert cap.width == 1920
    assert cap.height == 1080
    assert len(cap.base64_image) > 0

def test_ocr_extraction_and_untrusted_fencing():
    ocr_res = ocr_service.extract_text("mock_base64")
    assert "[UNTRUSTED SCREEN CONTENT]" in ocr_res.full_text
    assert len(ocr_res.regions) >= 1

def test_vision_ui_detection_and_stale_target():
    elements = [
        UIElement(type="button", label="Submit", x=842, y=621, width=120, height=42),
        UIElement(type="address_bar", label="Address Bar", x=200, y=100, width=500, height=35)
    ]
    # 1. Target present at expected location
    is_present = vision_service.validate_target_presence("Submit", 842, 621, elements)
    assert is_present is True

    # 2. Stale target moved or missing
    is_stale = vision_service.validate_target_presence("Submit", 100, 100, elements)
    assert is_stale is False

def test_mouse_coordinate_bounds_and_policy():
    # Valid click inside 1920x1080
    valid_click = MouseAction(action="click", x=500, y=300)
    ok, reason, risk = computer_policy.validate_mouse_action(valid_click, 1920, 1080)
    assert ok is True
    assert risk == "MEDIUM"

    # Out of bounds click
    invalid_click = MouseAction(action="click", x=2500, y=300)
    ok, reason, risk = computer_policy.validate_mouse_action(invalid_click, 1920, 1080)
    assert ok is False
    assert "outside" in reason.lower()

def test_keyboard_policy_and_sensitive_text_block():
    # Valid typing
    valid_type = KeyboardAction(action="type_text", text="hello world")
    ok, reason, risk = computer_policy.validate_keyboard_action(valid_type)
    assert ok is True

    # Attempting to type credential automatically must be BLOCKED
    secret_type = KeyboardAction(action="type_text", text="my_secret_password_123")
    ok, reason, risk = computer_policy.validate_keyboard_action(secret_type)
    assert ok is False
    assert risk == "CRITICAL"

def test_computer_tool_registry_and_tiers():
    # Perception tool is Tier 1
    req_screen = tool_registry.evaluate_request(ToolRequest(tool_name="capture_screen"))
    assert req_screen.allowed is True
    assert req_screen.autonomy_tier == AutonomyTier.TIER_1

    # Mouse click is Tier 2 confirmation required
    req_click = tool_registry.evaluate_request(ToolRequest(tool_name="click"))
    assert req_click.allowed is True
    assert req_click.requires_confirmation is True
    assert req_click.autonomy_tier == AutonomyTier.TIER_2

def test_emergency_stop_and_privacy_modes():
    computer_service.set_control_enabled(True)
    assert computer_service.control_enabled is True

    # Trigger emergency stop
    computer_service.emergency_stop()
    assert computer_service.control_enabled is False

    # Privacy mode transition
    computer_service.set_privacy_mode(ComputerPrivacyMode.PRIVATE)
    assert computer_service.privacy_mode == ComputerPrivacyMode.PRIVATE
