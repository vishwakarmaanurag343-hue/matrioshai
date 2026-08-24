import pytest
from app.security.secrets import secret_store
from app.agent.coding.claude_code import ClaudeCodeSubAgent
from app.agent.coding.provider import deepseek_harness_coding_provider
from app.agent.coding.router import coding_task_router

@pytest.mark.asyncio
async def test_claude_code_unconfigured_rejection(tmp_path):
    # Ensure no key present
    secret_store.delete_secret("claude_code_api_key")

    res = await coding_task_router.route_and_execute(
        task_id="task_test_01",
        user_prompt="Fix the bug",
        workspace_root=str(tmp_path)
    )
    assert res["success"] is False
    assert "not configured" in res["error"]

@pytest.mark.asyncio
async def test_claude_code_execution_flow(tmp_path):
    # Set mock user API key in secret store
    secret_store.set_secret("claude_code_api_key", "sk-ant-test-key-999")

    # Create dummy source file
    test_file = tmp_path / "app.py"
    test_file.write_text("def test(): pass")

    res = await coding_task_router.route_and_execute(
        task_id="task_test_02",
        user_prompt="Fix app.py function",
        workspace_root=str(tmp_path),
        files=["app.py"]
    )
    assert res["success"] is True
    assert res["provider"] == "deepseek_harness"
    assert res["sub_agent"] == "claude_code"
    assert res["tests_passed"] is True
    assert res["verification_passed"] is True
    assert "diff" in res

    # Clean up key
    secret_store.delete_secret("claude_code_api_key")

@pytest.mark.asyncio
async def test_zero_credential_leakage(tmp_path):
    secret_store.set_secret("claude_code_api_key", "sk-ant-secret-value-12345")
    agent = ClaudeCodeSubAgent(str(tmp_path))

    res = await agent.execute_coding_task(
        task_id="task_test_03",
        user_prompt="Check credentials"
    )
    # Ensure raw secret is never present in returned model dict or diff
    res_dict = res.model_dump()
    assert "sk-ant-secret-value-12345" not in str(res_dict)

    secret_store.delete_secret("claude_code_api_key")
