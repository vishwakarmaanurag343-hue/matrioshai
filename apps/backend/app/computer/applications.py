import subprocess
from typing import Optional, Dict, Any
from app.computer.models import ApplicationContext
from app.security.audit import audit_logger
from app.core.logging import logger

class ApplicationService:
    """
    macOS Application & Window Awareness Service.
    Queries active applications and window titles safely.
    """

    @classmethod
    def get_active_application(cls) -> ApplicationContext:
        app_name = "Finder"
        window_title = "Desktop"

        # On macOS, query System Events via safe osascript subprocess
        script = 'tell application "System Events" to get name of first application process whose frontmost is true'
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                app_name = res.stdout.strip()
        except Exception as e:
            logger.info(f"Active app query fallback: {e}")

        # Get window title
        title_script = f'tell application "System Events" to tell process "{app_name}" to get name of front window'
        try:
            res = subprocess.run(["osascript", "-e", title_script], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                window_title = res.stdout.strip()
        except Exception:
            pass

        audit_logger.log_event(
            event_type="APPLICATION_DETECTED",
            action="get_active_application",
            resource=app_name,
            decision="ALLOWED",
            reason=f"Active app: {app_name}, Window: {window_title}"
        )

        return ApplicationContext(
            application=app_name,
            bundle_id=f"com.apple.{app_name.lower()}",
            window_title=window_title,
            window_bounds={"x": 0, "y": 0, "width": 1920, "height": 1080},
            is_active=True
        )

    @classmethod
    def open_application(cls, app_name: str) -> bool:
        audit_logger.log_event(
            event_type="APPLICATION_CONTROL",
            action="open_application",
            resource=app_name,
            decision="ALLOWED",
            reason=f"Opening application '{app_name}'"
        )
        try:
            subprocess.run(["open", "-a", app_name], capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Failed to open application {app_name}: {e}")
            return False

application_service = ApplicationService()
