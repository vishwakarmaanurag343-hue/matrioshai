import pytest
from app.agent.runtime.models import (
    RuntimeSessionConfig, AgentEvent, AgentEventType, TrajectoryResponse
)
from app.agent.runtime.manager import agent_runtime_manager
from app.agent.runtime.deepseek_harness import deepseek_harness_provider

@pytest.mark.asyncio
async def test_runtime_manager_and_default_provider():
    provider = agent_runtime_manager.get_provider()
    assert provider is not None
    assert provider.provider_name() == "deepseek_harness"

@pytest.mark.asyncio
async def test_deepseek_harness_session_lifecycle():
    config = RuntimeSessionConfig(
        session_id="test_sess_001",
        user_id="user_test",
        workspace_root="/tmp",
        model_name="deepseek-r1:8b"
    )

    # 1. Create Session
    runtime_session_id = await deepseek_harness_provider.create_session(config)
    assert runtime_session_id.startswith("dsh_")

    # 2. Pause & Resume
    paused = await deepseek_harness_provider.pause_session(config.session_id)
    assert paused is True

    resumed = await deepseek_harness_provider.resume_session(config.session_id)
    assert resumed is True

    # 3. Trajectory Inspection
    trajectory = await deepseek_harness_provider.get_trajectory(config.session_id)
    assert isinstance(trajectory, TrajectoryResponse)
    assert trajectory.session_id == config.session_id

    # 4. Cancel & Destroy
    cancelled = await deepseek_harness_provider.cancel_session(config.session_id)
    assert cancelled is True

    destroyed = await deepseek_harness_provider.destroy_session(config.session_id)
    assert destroyed is True

@pytest.mark.asyncio
async def test_deepseek_harness_task_execution_with_permission_boundary(monkeypatch):
    config = RuntimeSessionConfig(
        session_id="test_sess_perm",
        workspace_root="/tmp"
    )
    await deepseek_harness_provider.create_session(config)

    # Mock planner returning safe StepDefinition
    from app.agent.models import PlanDefinition, StepDefinition
    from app.agent.planner import agent_planner

    async def mock_plan(*args, **kwargs):
        return PlanDefinition(
            goal_summary="List files",
            steps=[
                StepDefinition(
                    sequence=1,
                    objective="Search python files",
                    action_type="TOOL_CALL",
                    tool_name="search_code",
                    arguments={"query": "def"},
                    risk_level="LOW",
                    approval_required=False
                )
            ]
        )

    monkeypatch.setattr(agent_planner, "generate_plan", mock_plan)

    # Execute safe read-only task
    result = await deepseek_harness_provider.execute_task(
        session_id="test_sess_perm",
        task_id="task_perm_001",
        user_goal="Find all python files in the project",
        workspace_root="/tmp"
    )
    assert "success" in result
    assert result["steps_completed"] >= 1

    await deepseek_harness_provider.destroy_session(config.session_id)
