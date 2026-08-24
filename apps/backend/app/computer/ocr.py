import re
from typing import Optional, List
from app.computer.models import OCRResult, OCRRegion
from app.security.redaction import redaction_engine
from app.security.threat_defense import threat_defense
from app.security.audit import audit_logger
from app.core.logging import logger

class OCRService:
    """
    Optical Character Recognition Abstraction.
    All extracted text is treated strictly as UNTRUSTED SCREEN CONTENT.
    """

    @classmethod
    def extract_text(cls, base64_image: str) -> OCRResult:
        # Default text extraction (or Vision-backed OCR parser)
        # Mock structured extraction for testing & baseline
        full_text = "MATRIOSHAI Desktop Dashboard\nSubmit Button\nAddress Bar: https://localhost:1420"
        
        # 1. Redact any secrets found in OCR text
        sanitized_text, redactions = redaction_engine.redact(full_text)

        # 2. Check threat defense
        threat_scan = threat_defense.scan_content(sanitized_text, source_label="ocr_screen")
        contains_threat = threat_scan["has_threats"]

        regions = [
            OCRRegion(text="MATRIOSHAI Desktop Dashboard", x=100, y=50, width=300, height=30, confidence=0.98),
            OCRRegion(text="Submit Button", x=842, y=621, width=120, height=42, confidence=0.96),
            OCRRegion(text="Address Bar", x=200, y=100, width=500, height=35, confidence=0.95),
        ]

        audit_logger.log_event(
            event_type="OCR_EXTRACTED",
            action="extract_text",
            decision="ALLOWED",
            reason=f"OCR extracted {len(regions)} regions ({len(sanitized_text)} chars)"
        )

        return OCRResult(
            full_text=f"[UNTRUSTED SCREEN CONTENT]\n{sanitized_text}\n[END UNTRUSTED SCREEN CONTENT]",
            regions=regions,
            contains_sensitive_data=(len(redactions) > 0 or contains_threat)
        )

ocr_service = OCRService()
