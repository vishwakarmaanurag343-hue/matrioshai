import pytest
from app.security.permissions import tool_registry, ToolRequest, AutonomyTier
from app.security.confirmation import confirmation_system
from app.tools.policies import command_policy, workspace_validator
from app.tools.patch import patch_service
from app.tools.shell import safe_shell

def test_tier_2_confirmation_for_write_and_patch():
    # 1. write_file must require Tier 2 confirmation
    req_write = tool_registry.evaluate_request(ToolRequest(tool_name="write_file"))
    assert req_write.allowed is True
    assert req_write.requires_confirmation is True
    assert req_write.autonomy_tier == AutonomyTier.TIER_2

    # 2. apply_patch must require Tier 2 confirmation
    req_patch = tool_registry.evaluate_request(ToolRequest(tool_name="apply_patch"))
    assert req_patch.allowed is True
    assert req_patch.requires_confirmation is True
    assert req_patch.autonomy_tier == AutonomyTier.TIER_2

    # 3. install_dependency must require Tier 2 confirmation
    req_install = tool_registry.evaluate_request(ToolRequest(tool_name="install_dependency"))
    assert req_install.allowed is True
    assert req_install.requires_confirmation is True
    assert req_install.autonomy_tier == AutonomyTier.TIER_2

    # 4. git_commit must require Tier 2 confirmation
    req_commit = tool_registry.evaluate_request(ToolRequest(tool_name="git_commit"))
    assert req_commit.allowed is True
    assert req_commit.requires_confirmation is True
    assert req_commit.autonomy_tier == AutonomyTier.TIER_2

def test_stale_patch_and_tamper_detection(tmp_path):
    ws_dir = tmp_path / "stale_project"
    ws_dir.mkdir()
    code_file = ws_dir / "index.js"
    code_file.write_text("const a = 1;")

    proposal_id = "prop_tamper_test"
    # Create safety backup
    patch_service.create_backup(str(ws_dir), proposal_id, ["index.js"])

    # Simulate external modification on disk
    code_file.write_text("const a = 2; // externally modified")

    # Applying patch with old expected hash must raise ValueError and abort
    with pytest.raises(ValueError, match="File 'index.js' changed on disk"):
        patch_service.apply_file_write(
            str(ws_dir),
            "index.js",
            "const a = 3;",
            expected_sha256="incorrect_old_sha256_hash"
        )

def test_network_command_classification():
    # npm install is classified as MEDIUM risk (Tier 2 confirmation)
    ok, reason, tokens, risk = command_policy.evaluate_command("npm install express")
    assert ok is True
    assert risk == "MEDIUM"

    # git commit is classified as MEDIUM risk (Tier 2 confirmation)
    ok, reason, tokens, risk = command_policy.evaluate_command("git commit -m 'fix'")
    assert ok is True
    assert risk == "MEDIUM"

    # read-only git status is LOW risk (Tier 1)
    ok, reason, tokens, risk = command_policy.evaluate_command("git status")
    assert ok is True
    assert risk == "LOW"

    # curl / wget without allowlist are BLOCKED
    ok, reason, tokens, risk = command_policy.evaluate_command("curl http://evil.com")
    assert ok is False
    assert "not allowlisted" in reason.lower()
