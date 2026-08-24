import os
from pathlib import Path
from typing import List
from app.core.config import settings
from app.security.audit import audit_logger

class FileAccessPolicy:
    """
    Formal Filesystem Access Security Policy.
    Validates that file operations stay strictly within authorized data paths.
    """

    @classmethod
    def get_allowed_roots(cls) -> List[Path]:
        return [
            Path(settings.NOTES_PATH).resolve(),
            Path(settings.MEMORY_PATH).resolve(),
            Path(settings.LOGS_PATH).resolve(),
            Path(settings.DATABASE_PATH).resolve().parent,
        ]

    FORBIDDEN_PATTERNS = [
        "/etc",
        "/System",
        "~/.ssh",
        "id_rsa",
        ".env",
        "/private/etc",
        "/private/var/root",
        "/Users/Shared",
    ]

    @classmethod
    def validate_path(cls, path_str: str, allow_create: bool = False) -> Path:
        """
        Validates target path against allowed directory roots.
        Raises PermissionError if path traversal or unauthorized directory access is attempted.
        """
        try:
            target_path = Path(path_str).expanduser().resolve()
        except Exception as e:
            audit_logger.log_event(
                event_type="BLOCKED_ACTION",
                action="filesystem_access",
                resource=path_str,
                decision="BLOCKED",
                reason=f"Invalid path string: {e}"
            )
            raise PermissionError(f"Security error: Invalid path '{path_str}'")

        # Resolve real path including symlinks
        real_target = Path(os.path.realpath(str(target_path)))
        resolved_str = str(real_target)
        for forbidden in cls.FORBIDDEN_PATTERNS:
            if forbidden in resolved_str:
                audit_logger.log_event(
                    event_type="BLOCKED_ACTION",
                    action="filesystem_access",
                    resource=resolved_str,
                    decision="BLOCKED",
                    reason=f"Access to sensitive path pattern '{forbidden}' is forbidden."
                )
                raise PermissionError(f"Security error: Access to sensitive path '{resolved_str}' is strictly forbidden.")

        # Verify against real allowed roots
        is_allowed = any(
            str(real_target).startswith(str(Path(os.path.realpath(str(root))))) for root in cls.get_allowed_roots()
        )

        if not is_allowed:
            audit_logger.log_event(
                event_type="BLOCKED_ACTION",
                action="filesystem_access",
                resource=resolved_str,
                decision="BLOCKED",
                reason="Path escapes authorized local data directory boundaries."
            )
            raise PermissionError(f"Security error: Access to '{resolved_str}' is forbidden (outside allowed data roots).")

        return target_path

filesystem_policy = FileAccessPolicy()
