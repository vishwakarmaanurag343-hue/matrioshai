import os
from pathlib import Path
from typing import List, Optional
from app.tools.models import ProjectTreeNode, FileContentResponse, SearchResultItem
from app.tools.policies import workspace_validator
from app.security.redaction import redaction_engine
from app.security.audit import audit_logger
from app.core.logging import logger

class SafeFilesystemService:
    """
    Safe workspace filesystem operations.
    Enforces path boundaries, file size caps, binary filtering, and secret redaction.
    """

    MAX_READ_BYTES = 50_000  # 50 KB max text per read
    IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".nuxt"}

    @classmethod
    def get_project_tree(cls, workspace_root: str, max_depth: int = 3) -> List[ProjectTreeNode]:
        root_path = Path(os.path.realpath(workspace_root))
        if not root_path.exists():
            return []

        def _scan(dir_path: Path, current_depth: int) -> List[ProjectTreeNode]:
            if current_depth > max_depth:
                return []

            nodes = []
            try:
                entries = sorted(list(dir_path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            except Exception as e:
                logger.error(f"Error scanning directory {dir_path}: {e}")
                return []

            for entry in entries:
                if entry.name in cls.IGNORE_DIRS:
                    continue

                rel_path = str(entry.relative_to(root_path))
                is_sensitive = workspace_validator.is_sensitive_file(entry.name)

                if entry.is_dir():
                    children = _scan(entry, current_depth + 1)
                    nodes.append(ProjectTreeNode(
                        name=entry.name,
                        path=rel_path,
                        is_dir=True,
                        is_sensitive=is_sensitive,
                        children=children
                    ))
                else:
                    nodes.append(ProjectTreeNode(
                        name=entry.name,
                        path=rel_path,
                        is_dir=False,
                        size=entry.stat().st_size if entry.exists() else 0,
                        is_sensitive=is_sensitive,
                        children=None
                    ))
            return nodes

        return _scan(root_path, 1)

    @classmethod
    def read_file(cls, workspace_root: str, rel_path: str) -> FileContentResponse:
        real_target = workspace_validator.validate_workspace_path(workspace_root, rel_path)
        if not real_target.exists() or not real_target.is_file():
            raise FileNotFoundError(f"File '{rel_path}' does not exist in workspace.")

        file_size = real_target.stat().st_size
        
        # Check if binary
        try:
            with open(real_target, "rb") as f:
                chunk = f.read(min(file_size, cls.MAX_READ_BYTES))
                if b'\x00' in chunk:
                    return FileContentResponse(
                        path=rel_path,
                        size=file_size,
                        content="[BINARY FILE CONTENT NOT DISPLAYED]",
                        is_binary=True
                    )
                text_content = chunk.decode("utf-8", errors="replace")
        except Exception as e:
            return FileContentResponse(
                path=rel_path,
                size=file_size,
                content=f"[Error reading file: {e}]",
                is_binary=True
            )

        # Redact any sensitive credentials or secrets found in the file content before model exposure
        sanitized_content, _ = redaction_engine.redact(text_content)
        is_truncated = file_size > cls.MAX_READ_BYTES

        audit_logger.log_event(
            event_type="DEVELOPER_FILE_READ",
            action="read_file",
            resource=rel_path,
            decision="ALLOWED",
            reason=f"Read {len(text_content)} characters with secret redaction"
        )

        return FileContentResponse(
            path=rel_path,
            size=file_size,
            content=sanitized_content,
            is_truncated=is_truncated,
            is_binary=False
        )

    @classmethod
    def search_code(cls, workspace_root: str, query: str, max_results: int = 50) -> List[SearchResultItem]:
        root_path = Path(os.path.realpath(workspace_root))
        results = []
        clean_query = query.lower()

        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in cls.IGNORE_DIRS]
            for file in files:
                if workspace_validator.is_sensitive_file(file):
                    continue

                full_path = Path(root) / file
                rel_path = str(full_path.relative_to(root_path))
                
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            if clean_query in line.lower():
                                sanitized_line, _ = redaction_engine.redact(line.strip())
                                results.append(SearchResultItem(
                                    file_path=rel_path,
                                    line_number=line_no,
                                    line_content=sanitized_line[:200]
                                ))
                                if len(results) >= max_results:
                                    return results
                except Exception:
                    continue

        return results

safe_fs = SafeFilesystemService()
