import asyncio
import json
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.db_models import AgentTask, AgentStep, Workspace, utc_now
from app.agent.models import (
    TaskCreateRequest, TaskResponse, StepResponse, AgentTaskStatus, AgentStepStatus
)
from app.agent.planner import agent_planner
from app.agent.validator import plan_validator
from app.agent.loop import agent_execution_loop
from app.agent.state import agent_state_manager
from app.core.database import SessionLocal
from app.security.confirmation import confirmation_system
from app.security.audit import audit_logger
from app.core.logging import logger

class AgentService:
    def __init__(self, db: Session):
        self.db = db

    async def create_and_plan_task(self, req: TaskCreateRequest) -> TaskResponse:
        ws_root = None
        if req.workspace_id:
            ws = self.db.query(Workspace).filter(Workspace.id == req.workspace_id).first()
            if ws:
                ws_root = ws.root_path

        # 1. Create Task in SQLite
        task = AgentTask(
            user_goal=req.user_goal,
            workspace_id=req.workspace_id,
            status=AgentTaskStatus.PLANNING.value,
            max_steps=min(req.max_steps or 20, 20)
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        audit_logger.log_event(
            event_type="TASK_CREATED",
            action="create_task",
            resource=task.id,
            decision="ALLOWED",
            reason=f"Task created with goal: {req.user_goal[:80]}"
        )

        # 2. Generate and validate plan
        candidate_plan = await agent_planner.generate_plan(
            user_goal=req.user_goal,
            workspace_context=f"Workspace root: {ws_root}" if ws_root else None,
            max_steps=task.max_steps
        )

        ok, reason, valid_plan = plan_validator.validate_plan(candidate_plan, ws_root)
        if not ok:
            task.status = AgentTaskStatus.FAILED.value
            task.failure_reason = f"Plan validation failed: {reason}"
            self.db.commit()
            return self._format_task(task)

        # 3. Persist steps
        task.risk_level = valid_plan.estimated_risk
        task.status = AgentTaskStatus.CREATED.value

        for step in valid_plan.steps:
            db_step = AgentStep(
                task_id=task.id,
                sequence=step.sequence,
                objective=step.objective,
                action_type=step.action_type,
                tool_name=step.tool_name,
                arguments_json=json.dumps(step.arguments),
                status=AgentStepStatus.PENDING.value,
                risk_level=step.risk_level,
                approval_required=step.approval_required
            )
            self.db.add(db_step)

        self.db.commit()
        self.db.refresh(task)

        # 4. Trigger execution in background task
        asyncio.create_task(agent_execution_loop.run_task(SessionLocal, task.id))

        return self._format_task(task)

    def list_tasks(self) -> List[TaskResponse]:
        tasks = self.db.query(AgentTask).order_by(AgentTask.created_at.desc()).all()
        return [self._format_task(t) for t in tasks]

    def get_task(self, task_id: str) -> Optional[TaskResponse]:
        t = self.db.query(AgentTask).filter(AgentTask.id == task_id).first()
        return self._format_task(t) if t else None

    def pause_task(self, task_id: str) -> TaskResponse:
        t = self.db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not t:
            raise ValueError("Task not found")
        agent_state_manager.pause_task(task_id)
        t.status = AgentTaskStatus.PAUSED.value
        t.updated_at = utc_now()
        self.db.commit()
        audit_logger.log_event(event_type="TASK_PAUSED", action="pause_task", resource=task_id, decision="ALLOWED")
        return self._format_task(t)

    def resume_task(self, task_id: str) -> TaskResponse:
        t = self.db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not t:
            raise ValueError("Task not found")
        agent_state_manager.resume_task(task_id)
        t.status = AgentTaskStatus.RUNNING.value
        t.updated_at = utc_now()
        self.db.commit()
        audit_logger.log_event(event_type="TASK_RESUMED", action="resume_task", resource=task_id, decision="ALLOWED")
        return self._format_task(t)

    def cancel_task(self, task_id: str) -> TaskResponse:
        t = self.db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not t:
            raise ValueError("Task not found")
        agent_state_manager.cancel_task(task_id)
        t.status = AgentTaskStatus.CANCELLED.value
        t.updated_at = utc_now()
        self.db.commit()
        audit_logger.log_event(event_type="TASK_CANCELLED", action="cancel_task", resource=task_id, decision="ALLOWED")
        return self._format_task(t)

    async def approve_step(self, task_id: str, step_id: str, approved: bool) -> TaskResponse:
        t = self.db.query(AgentTask).filter(AgentTask.id == task_id).first()
        s = self.db.query(AgentStep).filter(AgentStep.id == step_id, AgentStep.task_id == task_id).first()
        if not t or not s:
            raise ValueError("Task or Step not found")

        if approved:
            s.status = AgentStepStatus.PENDING.value  # ready to execute
            t.status = AgentTaskStatus.RUNNING.value
            t.requires_approval = False
            self.db.commit()
            audit_logger.log_event(event_type="APPROVAL_GRANTED", action="approve_step", resource=step_id, decision="ALLOWED")
            # Resume background loop
            asyncio.create_task(agent_execution_loop.run_task(SessionLocal, task_id))
        else:
            s.status = AgentStepStatus.FAILED.value
            s.error = "Step rejected by user."
            t.status = AgentTaskStatus.FAILED.value
            t.failure_reason = "Step approval rejected by user."
            self.db.commit()
            audit_logger.log_event(event_type="APPROVAL_REJECTED", action="reject_step", resource=step_id, decision="BLOCKED")

        return self._format_task(t)

    def _format_task(self, t: AgentTask) -> TaskResponse:
        steps_res = []
        for s in t.steps:
            steps_res.append(StepResponse(
                id=s.id,
                task_id=s.task_id,
                sequence=s.sequence,
                objective=s.objective,
                action_type=s.action_type,
                tool_name=s.tool_name,
                arguments=json.loads(s.arguments_json or "{}"),
                status=AgentStepStatus(s.status),
                risk_level=s.risk_level,
                approval_required=s.approval_required,
                approval_id=s.approval_id,
                started_at=s.started_at,
                completed_at=s.completed_at,
                result=s.result,
                error=s.error
            ))

        return TaskResponse(
            id=t.id,
            workspace_id=t.workspace_id,
            user_goal=t.user_goal,
            status=AgentTaskStatus(t.status),
            risk_level=t.risk_level,
            current_step=t.current_step,
            max_steps=t.max_steps,
            steps_completed=t.steps_completed,
            retry_count=t.retry_count,
            max_retries=t.max_retries,
            requires_approval=t.requires_approval,
            result=t.result,
            failure_reason=t.failure_reason,
            steps=steps_res,
            created_at=t.created_at,
            updated_at=t.updated_at
        )
