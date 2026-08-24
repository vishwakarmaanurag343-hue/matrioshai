import os
import shutil
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.tools.policies import workspace_validator
from app.security.audit import audit_logger
from app.core.config import settings
from app.core.logging import logger

def utc_now():
    return datetime.now(timezone.utc)

class PatchService:
    """
    Diff-First Code Proposal and Transactional Rollback Engine.
    - Generates backups before modifying any existing file.
    - Verifies file integrity before applying patches.
    - Enables single-click transactional rollback.
    """

    @classmethod
    def get_backups_dir(cls) -> Path:
        backups = Path(settings.NOTES_PATH).parent / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        return backups

    @classmethod
    def create_backup(cls, workspace_root: str, proposal_id: str, files: List[str]) -> Path:
        proposal_backup_dir = cls.get_backups_dir() / proposal_id
        proposal_backup_dir.mkdir(parents=True, exist_ok=True)

        metadata = {"files": {}, "timestamp": utc_now().isoformat()}

        for rel_path in files:
            real_file = workspace_validator.validate_workspace_path(workspace_root, rel_path)
            if real_file.exists() and real_file.is_file():
                backup_dest = proposal_backup_dir / rel_path.replace("/", "_")
                shutil.copy2(real_file, backup_dest)
                
                # Record content hash
                content = real_file.read_bytes()
                metadata["files"][rel_path] = {
                    "backup_file": backup_dest.name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "existed": True
                }
            else:
                metadata["files"][rel_path] = {
                    "existed": False
                }

        meta_file = proposal_backup_dir / "backup_manifest.json"
        meta_file.write_text(json.dumps(metadata, indent=2))
        return proposal_backup_dir

    @classmethod
    def apply_file_write(
        cls,
        workspace_root: str,
        rel_path: str,
        new_content: str,
        expected_sha256: Optional[str] = None
    ) -> bool:
        real_file = workspace_validator.validate_workspace_path(workspace_root, rel_path)

        # If file already exists and expected hash is provided, verify it hasn't changed on disk
        if real_file.exists() and expected_sha256:
            current_hash = hashlib.sha256(real_file.read_bytes()).hexdigest()
            if current_hash != expected_sha256:
                audit_logger.log_event(
                    event_type="BLOCKED_ACTION",
                    action="apply_patch",
                    resource=rel_path,
                    decision="BLOCKED",
                    reason="Stale patch detected: file was modified on disk after proposal generation."
                )
                raise ValueError(f"Security error: File '{rel_path}' changed on disk since the proposal was generated.")

        real_file.parent.mkdir(parents=True, exist_ok=True)
        real_file.write_text(new_content, encoding="utf-8")
        
        audit_logger.log_event(
            event_type="DEVELOPER_FILE_WRITE",
            action="apply_patch",
            resource=rel_path,
            decision="ALLOWED",
            reason=f"Applied changes to {rel_path} ({len(new_content)} bytes)"
        )
        return True

    @classmethod
    def rollback_proposal(cls, workspace_root: str, proposal_id: str) -> bool:
        proposal_backup_dir = cls.get_backups_dir() / proposal_id
        meta_file = proposal_backup_dir / "backup_manifest.json"
        
        if not meta_file.exists():
            raise FileNotFoundError(f"Backup manifest not found for proposal '{proposal_id}'")

        metadata = json.loads(meta_file.read_text())
        for rel_path, file_info in metadata.get("files", {}).items():
            real_file = workspace_validator.validate_workspace_path(workspace_root, rel_path)
            
            if file_info.get("existed", False):
                backup_file = proposal_backup_dir / file_info["backup_file"]
                if backup_file.exists():
                    real_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, real_file)
                    logger.info(f"Restored file '{rel_path}' from backup {backup_file}")
            else:
                # If file didn't exist prior to proposal, delete it on rollback
                if real_file.exists():
                    real_file.unlink()
                    logger.info(f"Removed new file '{rel_path}' during rollback")

        audit_logger.log_event(
            event_type="DEVELOPER_ROLLBACK",
            action="rollback_proposal",
            resource=proposal_id,
            decision="ALLOWED",
            reason=f"Rolled back {len(metadata.get('files', {}))} files"
        )
        return True

patch_service = PatchService()
