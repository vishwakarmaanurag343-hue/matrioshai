from typing import Dict, Any, Optional, List
from app.agent.coding.provider import deepseek_harness_coding_provider
from app.security.secrets import secret_store
from app.security.audit import audit_logger

class CodingTaskRouter:
    """
    Directs coding intents from Matrioshai to DeepSeek Harness -> Claude Code.
    Validates user credentials before dispatch.
    """

    @classmethod
    def is_claude_code_available(cls) -> bool:
        return secret_store.has_secret("claude_code_api_key")

    @classmethod
    async def route_and_execute(
        self,
        task_id: str,
        user_prompt: str,
        workspace_root: str,
        files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if not secret_store.has_secret("claude_code_api_key"):
            return {
                "task_id": task_id,
                "success": False,
                "error": "Claude Code is not configured. Please add your Claude credential in Settings.",
                "provider": "deepseek_harness",
                "sub_agent": "claude_code"
            }

        audit_logger.log_event(
            event_type="CODING_TASK_ROUTED",
            action="route_and_execute",
            resource=task_id,
            decision="ALLOWED",
            reason="Coding task routed to DeepSeek Harness -> Claude Code"
        )

        return await deepseek_harness_coding_provider.execute_coding_task(
            task_id=task_id,
            user_prompt=user_prompt,
            workspace_root=workspace_root,
            files=files
        )

coding_task_router = CodingTaskRouter()
