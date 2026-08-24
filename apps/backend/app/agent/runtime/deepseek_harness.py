import asyncio
import uuid
import json
import time
from typing import Dict, Any, Optional, List
from app.agent.runtime.base import AgentRuntimeProvider
from app.agent.runtime.models import (
    RuntimeSessionConfig, AgentEvent, AgentEventType, TrajectoryResponse, TrajectoryStep, utc_now
)
from app.agent.planner import agent_planner
from app.agent.validator import plan_validator
from app.agent.executor import step_executor
from app.agent.models import StepDefinition
from app.security.audit import audit_logger
from app.core.logging import logger

class DeepSeekHarnessProvider(AgentRuntimeProvider):
    """
    Adapter implementing the AgentRuntimeProvider abstraction for DeepSeek Harness (DSH).
    Executes reasoning, plan generation, and controlled tool interaction while enforcing
    Matrioshai tool permissions and safety invariants.
    """

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._trajectories: Dict[str, List[TrajectoryStep]] = {}
        self._status: Dict[str, str] = {}  # RUNNING, PAUSED, CANCELLED, COMPLETED

    def provider_name(self) -> str:
        return "deepseek_harness"

    async def create_session(self, config: RuntimeSessionConfig) -> str:
        runtime_session_id = f"dsh_{uuid.uuid4().hex[:12]}"
        self._sessions[config.session_id] = {
            "runtime_session_id": runtime_session_id,
            "config": config,
            "created_at": time.time(),
        }
        self._trajectories[config.session_id] = []
        self._status[config.session_id] = "CREATED"

        audit_logger.log_event(
            event_type="AGENT_SESSION_CREATED",
            action="create_session",
            resource=config.session_id,
            decision="ALLOWED",
            reason=f"Created DeepSeek Harness session {runtime_session_id}"
        )
        return runtime_session_id

    async def execute_task(
        self,
        session_id: str,
        task_id: str,
        user_goal: str,
        workspace_root: Optional[str] = None
    ) -> Dict[str, Any]:
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found in DeepSeek Harness provider.")

        self._status[session_id] = "RUNNING"

        # 1. Generate plan using DeepSeek-R1 via AgentPlanner
        plan = await agent_planner.generate_plan(
            user_goal=user_goal,
            workspace_context=f"Workspace root: {workspace_root}" if workspace_root else None
        )

        ok, reason, validated_plan = plan_validator.validate_plan(plan, workspace_root)
        if not ok:
            self._status[session_id] = "FAILED"
            return {
                "success": False,
                "error": f"Plan validation failed: {reason}",
                "steps_completed": 0
            }

        # 2. Execute validated steps through Matrioshai's StepExecutor & ToolRegistry
        steps_completed = 0
        for step in validated_plan.steps:
            if self._status.get(session_id) == "CANCELLED":
                return {"success": False, "error": "Execution cancelled", "steps_completed": steps_completed}

            while self._status.get(session_id) == "PAUSED":
                await asyncio.sleep(0.5)

            # Route step execution through StepExecutor
            success, output, details = await step_executor.execute_step(task_id, step, workspace_root)

            # Record trajectory
            traj_step = TrajectoryStep(
                step_id=str(uuid.uuid4()),
                sequence=step.sequence,
                tool_name=step.tool_name,
                arguments=step.arguments,
                result=output,
                status="COMPLETED" if success else "FAILED"
            )
            self._trajectories[session_id].append(traj_step)

            if not success:
                if output == "CONFIRMATION_REQUIRED":
                    return {
                        "success": False,
                        "status": "AWAITING_APPROVAL",
                        "approval_id": details.get("confirmation_id"),
                        "steps_completed": steps_completed
                    }
                self._status[session_id] = "FAILED"
                return {"success": False, "error": output, "steps_completed": steps_completed}

            steps_completed += 1

        self._status[session_id] = "COMPLETED"
        return {
            "success": True,
            "status": "COMPLETED",
            "steps_completed": steps_completed,
            "result": "DeepSeek Harness execution completed successfully."
        }

    async def pause_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            self._status[session_id] = "PAUSED"
            audit_logger.log_event(
                event_type="AGENT_SESSION_PAUSED",
                action="pause_session",
                resource=session_id,
                decision="ALLOWED"
            )
            return True
        return False

    async def resume_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            self._status[session_id] = "RUNNING"
            audit_logger.log_event(
                event_type="AGENT_SESSION_RESUMED",
                action="resume_session",
                resource=session_id,
                decision="ALLOWED"
            )
            return True
        return False

    async def cancel_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            self._status[session_id] = "CANCELLED"
            audit_logger.log_event(
                event_type="AGENT_SESSION_CANCELLED",
                action="cancel_session",
                resource=session_id,
                decision="ALLOWED"
            )
            return True
        return False

    async def get_trajectory(self, session_id: str) -> TrajectoryResponse:
        steps = self._trajectories.get(session_id, [])
        return TrajectoryResponse(
            session_id=session_id,
            task_id=session_id,
            steps=steps,
            total_steps=len(steps),
            duration_ms=0.0
        )

    async def destroy_session(self, session_id: str) -> bool:
        self._sessions.pop(session_id, None)
        self._trajectories.pop(session_id, None)
        self._status.pop(session_id, None)
        return True

deepseek_harness_provider = DeepSeekHarnessProvider()
