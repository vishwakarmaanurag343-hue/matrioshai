import pytest
import json
from app.agent.models import PlanDefinition, StepDefinition, TaskCreateRequest
from app.agent.validator import plan_validator
from app.agent.planner import AgentPlanner
from app.agent.service import AgentService
from app.llm.base import LLMProvider

class MockAgentLLM(LLMProvider):
    async def chat(self, messages, model=None, temperature=0.7) -> str:
        return """{
            "goal_summary": "Inspect codebase and check status",
            "estimated_risk": "LOW",
            "steps": [
                {
                    "sequence": 1,
                    "objective": "Check git working tree status",
                    "action_type": "TOOL_CALL",
                    "tool_name": "git_status",
                    "arguments": {},
                    "risk_level": "LOW",
                    "approval_required": false
                },
                {
                    "sequence": 2,
                    "objective": "Read package configuration",
                    "action_type": "TOOL_CALL",
                    "tool_name": "read_file",
                    "arguments": {"path": "package.json"},
                    "risk_level": "LOW",
                    "approval_required": false
                }
            ]
        }"""

    async def stream_chat(self, messages, model=None, temperature=0.7):
        yield "mock"

    async def health(self):
        return {"connected": True, "model_available": True, "details": "Mock provider"}

    async def model_info(self, model_name: str):
        return {"name": model_name}

def test_plan_validator_bounds_and_tier_blocking():
    # 1. Valid plan
    valid_plan = PlanDefinition(
        goal_summary="Test plan",
        steps=[
            StepDefinition(sequence=1, objective="Read file", tool_name="read_file", arguments={"path": "test.txt"})
        ]
    )
    ok, reason, validated = plan_validator.validate_plan(valid_plan)
    assert ok is True
    assert len(validated.steps) == 1

    # 2. Plan with Tier 3 destructive tool must be rejected
    dangerous_plan = PlanDefinition(
        goal_summary="Dangerous plan",
        steps=[
            StepDefinition(sequence=1, objective="Delete files", tool_name="destructive_command", arguments={})
        ]
    )
    ok, reason, _ = plan_validator.validate_plan(dangerous_plan)
    assert ok is False
    assert "Tier 3" in reason or "Prohibited" in reason

    # 3. Plan with unknown unregistered tool must be rejected
    unknown_tool_plan = PlanDefinition(
        goal_summary="Unknown tool plan",
        steps=[
            StepDefinition(sequence=1, objective="Run random tool", tool_name="arbitrary_unregistered_tool", arguments={})
        ]
    )
    ok, reason, _ = plan_validator.validate_plan(unknown_tool_plan)
    assert ok is False
    assert "Unknown tool" in reason

    # 4. Plan exceeding 20 steps must be rejected
    huge_steps = [StepDefinition(sequence=i, objective=f"Step {i}", tool_name="read_file", arguments={}) for i in range(1, 25)]
    huge_plan = PlanDefinition(goal_summary="Huge plan", steps=huge_steps)
    ok, reason, _ = plan_validator.validate_plan(huge_plan)
    assert ok is False
    assert "maximum" in reason.lower()

@pytest.mark.asyncio
async def test_agent_task_persistence_and_lifecycle(test_db):
    mock_llm = MockAgentLLM()
    planner = AgentPlanner(llm_provider=mock_llm)
    
    plan = await planner.generate_plan("Audit git status and package.json")
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "git_status"
    assert plan.steps[1].tool_name == "read_file"

    # Test Task creation in SQLite
    service = AgentService(test_db)
    # Monkeypatch planner
    import app.agent.service as svc_module
    svc_module.agent_planner = planner

    task = await service.create_and_plan_task(TaskCreateRequest(user_goal="Audit git status and package.json"))
    assert task.id is not None
    assert len(task.steps) == 2
    assert task.status.value in ("CREATED", "PLANNING", "RUNNING")

    # Test Pause / Resume / Cancel
    paused = service.pause_task(task.id)
    assert paused.status.value == "PAUSED"

    resumed = service.resume_task(task.id)
    assert resumed.status.value == "RUNNING"

    cancelled = service.cancel_task(task.id)
    assert cancelled.status.value == "CANCELLED"
