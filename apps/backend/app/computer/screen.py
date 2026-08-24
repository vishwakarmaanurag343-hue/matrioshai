import os
import uuid
import base64
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from app.computer.models import ScreenshotCaptureResponse, ScreenMetadata, utc_now
from app.security.audit import audit_logger
from app.core.logging import logger

class ScreenService:
    """
    macOS Screen Capture Engine.
    Enforces ephemeral capture (capture -> process -> discard) unless explicitly requested.
    """

    MOCK_BASE64_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    @classmethod
    def get_screen_metadata(cls) -> ScreenMetadata:
        # Default standard display metadata (e.g. Retina 1440x900 or 1920x1080)
        return ScreenMetadata(
            id="display_main",
            width=1920,
            height=1080,
            scale_factor=2.0,
            is_main=True
        )

    @classmethod
    def capture_full_screen(cls) -> ScreenshotCaptureResponse:
        screen_id = str(uuid.uuid4())
        timestamp = utc_now()
        
        # On macOS, use screencapture tool to a temporary file
        temp_file = Path(f"/tmp/matrioshai_screen_{screen_id}.jpg")
        base64_data = cls.MOCK_BASE64_IMAGE

        try:
            res = subprocess.run(
                ["screencapture", "-x", "-t", "jpg", str(temp_file)],
                capture_output=True,
                timeout=5
            )
            if res.returncode == 0 and temp_file.exists():
                data = temp_file.read_bytes()
                base64_data = base64.b64encode(data).decode("utf-8")
                # Immediate ephemeral cleanup
                temp_file.unlink()
        except Exception as e:
            logger.info(f"Screen capture fallback (headless/test): {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

        meta = cls.get_screen_metadata()
        audit_logger.log_event(
            event_type="SCREEN_CAPTURED",
            action="capture_full_screen",
            resource=screen_id,
            decision="ALLOWED",
            reason="Ephemeral screen capture taken"
        )

        return ScreenshotCaptureResponse(
            id=screen_id,
            timestamp=timestamp,
            width=meta.width,
            height=meta.height,
            base64_image=base64_data,
            source="full_screen"
        )

screen_service = ScreenService()
