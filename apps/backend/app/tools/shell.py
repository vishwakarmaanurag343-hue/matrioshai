import asyncio
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from app.tools.models import CommandExecutionResponse
from app.tools.policies import command_policy
from app.security.redaction import redaction_engine
from app.security.audit import audit_logger
from app.core.logging import logger

class SafeShellExecutor:
    """
    Executes restricted developer commands safely:
    - shell=False
    - cwd=workspace_root
    - Sanitized environment (removes API keys and secrets)
    - Output size capping (50 KB)
    - Timeout bounds (30s)
    """

    MAX_OUTPUT_BYTES = 50_000

    @classmethod
    def get_sanitized_env(cls) -> Dict[str, str]:
        env = os.environ.copy()
        # Strip sensitive credentials from subprocess environment
        sensitive_env_keys = [
            k for k in env.keys() if any(
                term in k.upper() for term in ("SECRET", "KEY", "TOKEN", "PASSWORD", "AUTH", "CREDENTIAL", "DATABASE_URL")
            )
        ]
        for key in sensitive_env_keys:
            del env[key]
        return env

    @classmethod
    async def execute_command(
        cls,
        workspace_root: str,
        command_str: str,
        timeout_seconds: int = 30
    ) -> CommandExecutionResponse:
        # 1. Policy check
        allowed, reason, tokens, risk = command_policy.evaluate_command(command_str)
        if not allowed:
            raise PermissionError(f"Command execution blocked by CommandPolicy: {reason}")

        ws_path = Path(os.path.realpath(workspace_root))
        if not ws_path.exists() or not ws_path.is_dir():
            raise FileNotFoundError(f"Workspace directory '{workspace_root}' does not exist.")

        start_time = time.time()
        logger.info(f"Executing safe command {tokens} in '{ws_path}'...")

        try:
            process = await asyncio.create_subprocess_exec(
                *tokens,
                cwd=str(ws_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=cls.get_sanitized_env()
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=float(timeout_seconds)
                )
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
                audit_logger.log_event(
                    event_type="DEVELOPER_COMMAND",
                    action="run_command",
                    resource=command_str[:100],
                    decision="TIMEOUT",
                    reason=f"Command exceeded {timeout_seconds}s timeout boundary"
                )
                raise TimeoutError(f"Command '{command_str}' timed out after {timeout_seconds} seconds.")

            exec_time = (time.time() - start_time) * 1000

            stdout_text = stdout_bytes.decode("utf-8", errors="replace")[:cls.MAX_OUTPUT_BYTES]
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")[:cls.MAX_OUTPUT_BYTES]

            # Redact secrets from output
            sanitized_stdout, _ = redaction_engine.redact(stdout_text)
            sanitized_stderr, _ = redaction_engine.redact(stderr_text)

            is_truncated = len(stdout_bytes) > cls.MAX_OUTPUT_BYTES or len(stderr_bytes) > cls.MAX_OUTPUT_BYTES

            audit_logger.log_event(
                event_type="DEVELOPER_COMMAND",
                action="run_command",
                resource=command_str[:100],
                decision="ALLOWED",
                reason=f"Exit code {process.returncode} in {exec_time:.1f}ms"
            )

            return CommandExecutionResponse(
                command=command_str,
                exit_code=process.returncode,
                stdout=sanitized_stdout,
                stderr=sanitized_stderr,
                is_truncated=is_truncated,
                execution_time_ms=exec_time
            )

        except Exception as e:
            if isinstance(e, (PermissionError, TimeoutError, FileNotFoundError)):
                raise e
            raise RuntimeError(f"Command execution error: {e}")

safe_shell = SafeShellExecutor()
