import asyncio
import os
from pathlib import Path
from typing import List, Optional
from app.tools.models import GitStatusResponse, GitDiffResponse
from app.tools.shell import safe_shell
from app.security.redaction import redaction_engine
from app.core.logging import logger

class GitService:
    """
    Safe Git operations within workspace root.
    """

    @classmethod
    async def get_status(cls, workspace_root: str) -> GitStatusResponse:
        git_dir = Path(os.path.realpath(workspace_root)) / ".git"
        if not git_dir.exists():
            return GitStatusResponse(branch="not_a_git_repo", is_clean=True)

        # 1. Get branch
        branch_res = await safe_shell.execute_command(workspace_root, "git branch --show-current")
        branch_name = branch_res.stdout.strip() or "HEAD"

        # 2. Get status porcelain
        status_res = await safe_shell.execute_command(workspace_root, "git status --porcelain")
        modified, staged, untracked = [], [], []

        for line in status_res.stdout.splitlines():
            if len(line) < 3:
                continue
            index_code = line[0]
            work_code = line[1]
            file_name = line[3:].strip()

            if index_code in ("M", "A", "D", "R"):
                staged.append(file_name)
            if work_code in ("M", "D"):
                modified.append(file_name)
            if index_code == "?" and work_code == "?":
                untracked.append(file_name)

        is_clean = len(modified) == 0 and len(staged) == 0 and len(untracked) == 0

        return GitStatusResponse(
            branch=branch_name,
            is_clean=is_clean,
            modified=modified,
            staged=staged,
            untracked=untracked
        )

    @classmethod
    async def get_diff(cls, workspace_root: str, file_path: Optional[str] = None) -> GitDiffResponse:
        cmd = "git diff"
        if file_path:
            cmd = f"git diff -- {file_path}"

        res = await safe_shell.execute_command(workspace_root, cmd)
        sanitized_diff, _ = redaction_engine.redact(res.stdout)

        files_changed = []
        for line in sanitized_diff.splitlines():
            if line.startswith("+++ b/"):
                files_changed.append(line[6:].strip())

        return GitDiffResponse(
            diff=sanitized_diff,
            files_changed=files_changed
        )

git_service = GitService()
