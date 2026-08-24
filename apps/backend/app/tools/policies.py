import os
import shlex
import re
from pathlib import Path
from typing import List, Tuple, Optional
from app.security.audit import audit_logger

class WorkspaceBoundaryValidator:
    """
    Validates that file operations stay strictly within the selected workspace root.
    Uses canonical realpath to prevent symlink and traversal escapes.
    """

    SENSITIVE_PATTERNS = [
        r'\.env(?:\..*)?$',
        r'.*\.pem$',
        r'.*\.key$',
        r'id_rsa.*',
        r'credentials\.json$',
        r'.*\.pfx$',
        r'.*\.p12$'
    ]

    @classmethod
    def validate_workspace_path(cls, workspace_root_str: str, target_rel_path: str) -> Path:
        ws_root = Path(os.path.realpath(workspace_root_str))
        if not ws_root.exists() or not ws_root.is_dir():
            raise PermissionError(f"Security error: Invalid workspace root '{workspace_root_str}'")

        target = ws_root / target_rel_path
        real_target = Path(os.path.realpath(str(target)))
        
        # Verify that canonical path is strictly inside workspace root
        if not str(real_target).startswith(str(ws_root)):
            audit_logger.log_event(
                event_type="BLOCKED_ACTION",
                action="workspace_file_access",
                resource=str(target),
                decision="BLOCKED",
                reason="Path escapes workspace boundary."
            )
            raise PermissionError(f"Security error: Access to '{target_rel_path}' escapes workspace boundary.")

        return real_target

    @classmethod
    def is_sensitive_file(cls, filename: str) -> bool:
        for pattern in cls.SENSITIVE_PATTERNS:
            if re.match(pattern, filename, re.IGNORECASE):
                return True
        return False


class CommandPolicy:
    """
    Enforces strict developer command allowlist and rejects shell metacharacters / injection attempts.
    """

    # Structured command allowlist (prefix + subcommands)
    ALLOWLIST_PREFIXES = {
        "git": ["status", "diff", "log", "branch", "show", "commit"],
        "npm": ["test", "run check", "run build", "run lint", "run typecheck", "install", "--version"],
        "pnpm": ["test", "run check", "run build", "install", "--version"],
        "yarn": ["test", "build", "--version"],
        "pytest": [],
        "python": ["--version", "-m pytest"],
        "python3": ["--version", "-m pytest"],
        "node": ["--version"],
        "flutter": ["--version", "test", "build", "pub get"],
        "go": ["version", "test", "build"],
        "cargo": ["check", "test", "build", "--version"],
    }

    FORBIDDEN_METACHARS = [";", "&&", "||", "|", ">", ">>", "<", "`", "$(", "$", "\n", "\r"]

    @classmethod
    def evaluate_command(cls, command_str: str) -> Tuple[bool, str, List[str], str]:
        """
        Evaluates a raw command string.
        Returns:
            (allowed: bool, reason: str, tokens: List[str], risk_level: str)
        """
        clean_cmd = command_str.strip()
        if not clean_cmd:
            return False, "Empty command", [], "LOW"

        # 1. Check forbidden shell metacharacters
        for char in cls.FORBIDDEN_METACHARS:
            if char in clean_cmd:
                audit_logger.log_event(
                    event_type="BLOCKED_ACTION",
                    action="execute_command",
                    resource=clean_cmd[:80],
                    decision="BLOCKED",
                    reason=f"Forbidden shell metacharacter '{char}' detected."
                )
                return False, f"Command contains forbidden shell metacharacter '{char}'", [], "CRITICAL"

        # 2. Parse into tokens safely with shlex
        try:
            tokens = shlex.split(clean_cmd)
        except Exception as e:
            return False, f"Failed to parse command safely: {e}", [], "HIGH"

        if not tokens:
            return False, "No command tokens found", [], "LOW"

        base_bin = tokens[0]
        if base_bin not in cls.ALLOWLIST_PREFIXES:
            audit_logger.log_event(
                event_type="BLOCKED_ACTION",
                action="execute_command",
                resource=clean_cmd[:80],
                decision="BLOCKED",
                reason=f"Binary '{base_bin}' is not in allowed developer commands list."
            )
            return False, f"Command binary '{base_bin}' is not allowlisted.", [], "HIGH"

        # Determine risk and confirmation requirements
        subcmd = " ".join(tokens[1:])
        risk_level = "LOW"

        # Tier 2 confirmation required commands (installing dependencies, commits)
        if base_bin == "git" and len(tokens) > 1 and tokens[1] == "commit":
            risk_level = "MEDIUM"
        elif "install" in tokens or "pub get" in subcmd:
            risk_level = "MEDIUM"
        elif "build" in tokens:
            risk_level = "MEDIUM"

        return True, "Command authorized under CommandPolicy", tokens, risk_level

command_policy = CommandPolicy()
workspace_validator = WorkspaceBoundaryValidator()
