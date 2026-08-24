import time
from typing import Dict, Any, Optional, List
from app.agent.coding.claude_code import ClaudeCodeSubAgent, ClaudeCodeExecutionResult
from app.security.audit import audit_logger

class DeepSeekHarnessCodingProvider:
    """
    Orchestration layer connecting DeepSeek Harness to the Claude Code sub-agent.
    Enforces Matrioshai's architectural hierarchy:
    MATRIOSHAI -> DeepSeek Harness -> Claude Code Sub-Agent
    """

    def __init__(self):
        self._active_agents: Dict[str, ClaudeCodeSubAgent] = {}

    def get_or_create_subagent(self, workspace_root: str) -> ClaudeCodeSubAgent:
        if workspace_root not in self._active_agents:
            self._active_agents[workspace_root] = ClaudeCodeSubAgent(workspace_root)
        return self._active_agents[workspace_root]

    async def execute_coding_task(
        self,
        task_id: str,
        user_prompt: str,
        workspace_root: str,
        files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        audit_logger.log_event(
            event_type="DEEPSEEK_HARNESS_DISPATCH",
            action="execute_coding_task",
            resource=task_id,
            decision="ALLOWED",
            reason="DeepSeek Harness dispatching task to Claude Code sub-agent"
        )

        sub_agent = self.get_or_create_subagent(workspace_root)
        result: ClaudeCodeExecutionResult = await sub_agent.execute_coding_task(
            task_id=task_id,
            user_prompt=user_prompt,
            files=files
        )

        return {
            "task_id": result.task_id,
            "provider": "deepseek_harness",
            "sub_agent": "claude_code",
            "success": result.success,
            "diff": result.diff,
            "files_modified": result.files_modified,
            "tests_run": result.tests_run,
            "tests_passed": result.tests_passed,
            "verification_passed": result.verification_passed,
            "error": result.error,
            "duration_ms": result.duration_ms
        }

deepseek_harness_coding_provider = DeepSeekHarnessCodingProvider()
