import asyncio
import json
import time
from sqlalchemy.orm import Session
from app.models.db_models import AgentTask, AgentStep, Workspace, utc_now
from app.agent.models import AgentTaskStatus, AgentStepStatus, StepDefinition
from app.agent.executor import step_executor
from app.agent.recovery import recovery_engine
from app.agent.state import agent_state_manager
from app.security.audit import audit_logger
from app.core.logging import logger

class AgentExecutionLoop:
    """
    Bounded, persistent execution loop orchestrating multi-step tasks:
    - Persists step states in SQLite.
    - Handles pause, resume, cancel.
    - Enforces max runtime timeout (10 mins).
    - Triggers recovery on step failure (max 3 retries).
    """

    MAX_RUNTIME_SECONDS = 600  # 10 minutes

    @classmethod
    async def run_task(cls, db_session_factory, task_id: str):
        start_time = time.time()
        agent_state_manager.register_task(task_id)

        # Broadcast task started
        await agent_state_manager.broadcast_event(task_id, "task.started", {"task_id": task_id})

        with db_session_factory() as db:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found.")
                return

            task.status = AgentTaskStatus.RUNNING.value
            task.updated_at = utc_now()
            db.commit()

            ws_root = None
            if task.workspace_id:
                ws = db.query(Workspace).filter(Workspace.id == task.workspace_id).first()
                if ws:
                    ws_root = ws.root_path

        observations = []

        while True:
            # Check timeout
            if (time.time() - start_time) > cls.MAX_RUNTIME_SECONDS:
                with db_session_factory() as db:
                    t = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                    if t:
                        t.status = AgentTaskStatus.EXPIRED.value
                        t.failure_reason = f"Execution exceeded maximum timeout of {cls.MAX_RUNTIME_SECONDS} seconds."
                        t.updated_at = utc_now()
                        db.commit()
                await agent_state_manager.broadcast_event(task_id, "task.failed", {"reason": "Timeout exceeded"})
                break

            # Check cancellation
            if agent_state_manager.is_cancelled(task_id):
                with db_session_factory() as db:
                    t = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                    if t:
                        t.status = AgentTaskStatus.CANCELLED.value
                        t.updated_at = utc_now()
                        db.commit()
                await agent_state_manager.broadcast_event(task_id, "task.cancelled", {"task_id": task_id})
                break

            # Check pause
            await agent_state_manager.wait_if_paused(task_id)

            # Fetch next pending step
            with db_session_factory() as db:
                step = db.query(AgentStep).filter(
                    AgentStep.task_id == task_id,
                    AgentStep.status == AgentStepStatus.PENDING.value
                ).order_by(AgentStep.sequence.asc()).first()

                if not step:
                    # All steps completed
                    t = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                    if t:
                        t.status = AgentTaskStatus.COMPLETED.value
                        t.result = "All plan steps completed successfully."
                        t.updated_at = utc_now()
                        db.commit()
                    await agent_state_manager.broadcast_event(task_id, "task.completed", {"task_id": task_id})
                    break

                step_id = step.id
                step_def = StepDefinition(
                    sequence=step.sequence,
                    objective=step.objective,
                    action_type=step.action_type,
                    tool_name=step.tool_name,
                    arguments=json.loads(step.arguments_json or "{}"),
                    risk_level=step.risk_level,
                    approval_required=step.approval_required
                )
                step.status = AgentStepStatus.RUNNING.value
                step.started_at = utc_now()
                db.commit()

            await agent_state_manager.broadcast_event(task_id, "step.started", {"step_id": step_id, "sequence": step_def.sequence})

            # Execute Step
            success, output, details = await step_executor.execute_step(task_id, step_def, ws_root)

            if output == "CONFIRMATION_REQUIRED":
                # Pause task and await user approval
                with db_session_factory() as db:
                    s = db.query(AgentStep).filter(AgentStep.id == step_id).first()
                    t = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                    if s and t:
                        s.status = AgentStepStatus.AWAITING_APPROVAL.value
                        s.approval_id = details.get("confirmation_id")
                        t.status = AgentTaskStatus.AWAITING_APPROVAL.value
                        t.requires_approval = True
                        t.updated_at = utc_now()
                        db.commit()

                await agent_state_manager.broadcast_event(task_id, "approval.required", {
                    "step_id": step_id,
                    "approval_id": details.get("confirmation_id")
                })
                # Execution loop pauses until user approves
                break

            with db_session_factory() as db:
                s = db.query(AgentStep).filter(AgentStep.id == step_id).first()
                t = db.query(AgentTask).filter(AgentTask.id == task_id).first()
                if not s or not t:
                    break

                if success:
                    s.status = AgentStepStatus.COMPLETED.value
                    s.result = output
                    s.completed_at = utc_now()
                    t.steps_completed += 1
                    t.current_step = step_def.sequence
                    t.updated_at = utc_now()
                    db.commit()
                    observations.append(output)
                    await agent_state_manager.broadcast_event(task_id, "step.completed", {"step_id": step_id, "result": output[:200]})
                else:
                    s.status = AgentStepStatus.FAILED.value
                    s.error = output
                    s.completed_at = utc_now()
                    t.retry_count += 1
                    t.updated_at = utc_now()
                    db.commit()
                    await agent_state_manager.broadcast_event(task_id, "step.failed", {"step_id": step_id, "error": output})

                    # Trigger recovery replanning
                    if t.retry_count <= t.max_retries:
                        replan = await recovery_engine.replan_on_failure(
                            user_goal=t.user_goal,
                            failed_step=step_def,
                            error_msg=output,
                            observations=observations,
                            retry_count=t.retry_count,
                            max_retries=t.max_retries
                        )
                        if replan:
                            # Insert new steps
                            for new_s in replan.steps:
                                db_step = AgentStep(
                                    task_id=task_id,
                                    sequence=new_s.sequence,
                                    objective=new_s.objective,
                                    action_type=new_s.action_type,
                                    tool_name=new_s.tool_name,
                                    arguments_json=json.dumps(new_s.arguments),
                                    status=AgentStepStatus.PENDING.value,
                                    risk_level=new_s.risk_level,
                                    approval_required=new_s.approval_required
                                )
                                db.add(db_step)
                            db.commit()
                            continue

                    # Failed completely
                    t.status = AgentTaskStatus.FAILED.value
                    t.failure_reason = f"Step {step_def.sequence} failed: {output}"
                    db.commit()
                    await agent_state_manager.broadcast_event(task_id, "task.failed", {"reason": t.failure_reason})
                    break

agent_execution_loop = AgentExecutionLoop()
