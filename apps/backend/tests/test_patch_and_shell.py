import pytest
from pathlib import Path
from app.tools.patch import patch_service
from app.tools.shell import safe_shell
from app.tools.filesystem import safe_fs

def test_safe_filesystem_reading_and_search(tmp_path):
    ws_dir = tmp_path / "search_project"
    ws_dir.mkdir()
    src_dir = ws_dir / "src"
    src_dir.mkdir()
    
    file1 = src_dir / "index.ts"
    file1.write_text("export const API_URL = 'http://localhost:8000';\nconst user = 'alice';")

    file2 = src_dir / "secret.env"
    file2.write_text("DATABASE_URL=postgres://user:pass@localhost/db")

    # Read file
    res = safe_fs.read_file(str(ws_dir), "src/index.ts")
    assert res.is_binary is False
    assert "export const API_URL" in res.content

    # Search code
    search_res = safe_fs.search_code(str(ws_dir), "API_URL")
    assert len(search_res) >= 1
    assert search_res[0].file_path == "src/index.ts"
    assert search_res[0].line_number == 1

def test_patch_application_and_rollback(tmp_path):
    ws_dir = tmp_path / "patch_project"
    ws_dir.mkdir()
    target_file = ws_dir / "config.ts"
    target_file.write_text("export const TIMEOUT = 1000;")

    proposal_id = "test_prop_123"

    # 1. Create safety backup
    patch_service.create_backup(str(ws_dir), proposal_id, ["config.ts"])
    
    # 2. Apply new file content
    patch_service.apply_file_write(str(ws_dir), "config.ts", "export const TIMEOUT = 5000;")
    assert target_file.read_text() == "export const TIMEOUT = 5000;"

    # 3. Rollback
    patch_service.rollback_proposal(str(ws_dir), proposal_id)
    assert target_file.read_text() == "export const TIMEOUT = 1000;"

@pytest.mark.asyncio
async def test_safe_shell_execution_and_timeout(tmp_path):
    # Test safe git status in non-git folder
    res = await safe_shell.execute_command(str(tmp_path), "git status")
    assert res.exit_code != 0  # not a git repository

    # Test sanitized env removes tokens
    env = safe_shell.get_sanitized_env()
    assert not any("SECRET" in k.upper() for k in env.keys())
    assert not any("TOKEN" in k.upper() for k in env.keys())
