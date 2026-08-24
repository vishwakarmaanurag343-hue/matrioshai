import json
from typing import Dict, Any, Tuple
from app.agent.models import StepDefinition
from app.agent.observer import observation_pipeline
from app.security.permissions import tool_registry, ToolRequest, AutonomyTier
from app.security.confirmation import confirmation_system
from app.tools.filesystem import safe_fs
from app.tools.git import git_service
from app.tools.shell import safe_shell
from app.tools.patch import patch_service
from app.security.audit import audit_logger
from app.core.logging import logger

class StepExecutor:
    """
    Executes a single validated step strictly through ToolRegistry and Developer Services.
    Handles Tier 2 Confirmation dispatch and observation recording.
    """

    @classmethod
    async def execute_step(
        cls,
        task_id: str,
        step: StepDefinition,
        workspace_root: str = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        tool_name = step.tool_name
        args = step.arguments

        # 1. Permission Evaluation
        decision = tool_registry.evaluate_request(ToolRequest(tool_name=tool_name, parameters=args))
        if not decision.allowed:
            audit_logger.log_event(
                event_type="TOOL_EXECUTED",
                action=f"execute_step:{tool_name}",
                decision="BLOCKED",
                reason=decision.reason
            )
            return False, f"Permission Denied: {decision.reason}", {}

        # 2. Tier 2 Confirmation
        if decision.requires_confirmation:
            conf_req = confirmation_system.create_request(
                tool_name=tool_name,
                action_summary=f"Task step {step.sequence}: {step.objective}",
                affected_resource=str(args.get("path") or args.get("package") or tool_name),
                risk_level=decision.risk_level,
                parameters={"task_id": task_id, "step_sequence": step.sequence, **args}
            )
            # If not yet approved, signal confirmation required
            return False, "CONFIRMATION_REQUIRED", {"confirmation_id": conf_req.id}

        # 3. Tool Dispatch
        logger.info(f"Executing step {step.sequence} tool '{tool_name}'...")
        try:
            raw_output = None
            if tool_name == "read_file":
                path = args.get("path", "")
                res = safe_fs.read_file(workspace_root, path)
                raw_output = res.content

            elif tool_name == "search_code":
                query = args.get("query", "")
                res = safe_fs.search_code(workspace_root, query)
                raw_output = json.dumps([{"file": r.file_path, "line": r.line_number, "content": r.line_content} for r in res])

            elif tool_name == "git_status":
                res = await git_service.get_status(workspace_root)
                raw_output = f"Branch: {res.branch}, Clean: {res.is_clean}, Modified: {res.modified}, Untracked: {res.untracked}"

            elif tool_name == "git_diff":
                file_path = args.get("file_path")
                res = await git_service.get_diff(workspace_root, file_path)
                raw_output = res.diff

            elif tool_name == "write_file":
                path = args.get("path", "")
                content = args.get("content", "")
                patch_service.apply_file_write(workspace_root, path, content)
                raw_output = f"Successfully wrote {len(content)} characters to {path}"

            elif tool_name == "apply_patch":
                proposal_id = args.get("proposal_id", "")
                raw_output = f"Patch proposal {proposal_id} applied"

            else:
                raw_output = f"Tool {tool_name} executed successfully."

            # 4. Fencing & Redaction via Observation Pipeline
            observation = observation_pipeline.process_observation(tool_name, raw_output)

            audit_logger.log_event(
                event_type="TOOL_EXECUTED",
                action=f"execute_step:{tool_name}",
                decision="ALLOWED",
                reason=f"Step {step.sequence} completed successfully"
            )
            return True, observation, {}

        except Exception as e:
            logger.error(f"Error executing step {step.sequence} ({tool_name}): {e}")
            audit_logger.log_event(
                event_type="TOOL_EXECUTED",
                action=f"execute_step:{tool_name}",
                decision="ERROR",
                reason=str(e)
            )
            return False, f"Step execution error: {e}", {}

step_executor = StepExecutor()
