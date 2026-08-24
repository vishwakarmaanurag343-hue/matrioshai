import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.db_models import Workspace, CodeChangeProposal, utc_now
from app.tools.models import (
    WorkspaceResponse, WorkspaceCreate, CodeChangeProposalResponse,
    CreateProposalRequest, ProposalStatus
)
from app.tools.filesystem import safe_fs
from app.tools.git import git_service
from app.tools.shell import safe_shell
from app.tools.patch import patch_service
from app.tools.policies import workspace_validator
from app.core.logging import logger

class DeveloperService:
    def __init__(self, db: Session):
        self.db = db

    def _detect_project_metadata(self, root_path: Path) -> Dict[str, Any]:
        meta = {
            "project_type": "generic",
            "language": "unknown",
            "framework": None,
            "package_manager": None,
            "is_git": (root_path / ".git").exists()
        }

        # Check Node / Web
        if (root_path / "package.json").exists():
            meta["project_type"] = "node"
            meta["language"] = "javascript/typescript"
            meta["package_manager"] = "npm"
            if (root_path / "pnpm-lock.yaml").exists():
                meta["package_manager"] = "pnpm"
            elif (root_path / "yarn.lock").exists():
                meta["package_manager"] = "yarn"

            try:
                pkg_data = json.loads((root_path / "package.json").read_text())
                deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                if "next" in deps:
                    meta["framework"] = "Next.js"
                elif "react" in deps:
                    meta["framework"] = "React"
                elif "vue" in deps:
                    meta["framework"] = "Vue"
                elif "vite" in deps:
                    meta["framework"] = "Vite"
                elif "tauri" in deps or "@tauri-apps/api" in deps:
                    meta["framework"] = "Tauri"
            except Exception:
                pass

        # Check Python
        elif (root_path / "requirements.txt").exists() or (root_path / "pyproject.toml").exists():
            meta["project_type"] = "python"
            meta["language"] = "python"
            meta["package_manager"] = "pip/uv"
            if (root_path / "main.py").exists():
                meta["framework"] = "FastAPI/Flask"

        # Check Rust
        elif (root_path / "Cargo.toml").exists():
            meta["project_type"] = "rust"
            meta["language"] = "rust"
            meta["package_manager"] = "cargo"

        # Check Flutter / Dart
        elif (root_path / "pubspec.yaml").exists():
            meta["project_type"] = "flutter"
            meta["language"] = "dart"
            meta["framework"] = "Flutter"
            meta["package_manager"] = "flutter pub"

        # Check Go
        elif (root_path / "go.mod").exists():
            meta["project_type"] = "go"
            meta["language"] = "go"
            meta["package_manager"] = "go mod"

        return meta

    def create_workspace(self, req: WorkspaceCreate) -> WorkspaceResponse:
        real_root = Path(os.path.realpath(req.root_path))
        if not real_root.exists() or not real_root.is_dir():
            raise ValueError(f"Directory path '{req.root_path}' does not exist.")

        # Check if already registered
        existing = self.db.query(Workspace).filter(Workspace.root_path == str(real_root)).first()
        if existing:
            return self._format_workspace(existing)

        meta = self._detect_project_metadata(real_root)

        ws = Workspace(
            name=req.name,
            root_path=str(real_root),
            project_type=meta["project_type"],
            language=meta["language"],
            framework=meta["framework"],
            package_manager=meta["package_manager"],
            is_git=meta["is_git"],
            git_branch="main" if meta["is_git"] else None
        )
        self.db.add(ws)
        self.db.commit()
        self.db.refresh(ws)
        logger.info(f"Registered Workspace [{ws.id}] - '{ws.name}' at {ws.root_path}")
        return self._format_workspace(ws)

    def list_workspaces(self) -> List[WorkspaceResponse]:
        workspaces = self.db.query(Workspace).order_by(Workspace.updated_at.desc()).all()
        return [self._format_workspace(w) for w in workspaces]

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        return self.db.query(Workspace).filter(Workspace.id == workspace_id).first()

    def create_proposal(self, workspace_id: str, req: CreateProposalRequest) -> CodeChangeProposalResponse:
        ws = self.get_workspace(workspace_id)
        if not ws:
            raise ValueError(f"Workspace [{workspace_id}] not found.")

        # Validate all file paths in proposal
        for rel_file in req.files:
            workspace_validator.validate_workspace_path(ws.root_path, rel_file)

        proposal = CodeChangeProposal(
            workspace_id=workspace_id,
            title=req.title,
            reason=req.reason,
            risk_level=req.risk_level,
            diff_content=req.diff_content,
            files_json=json.dumps(req.files),
            status=ProposalStatus.PROPOSED.value
        )
        self.db.add(proposal)
        self.db.commit()
        self.db.refresh(proposal)
        logger.info(f"Created Code Change Proposal [{proposal.id}] for workspace '{ws.name}'")
        return self._format_proposal(proposal)

    def list_proposals(self, workspace_id: str) -> List[CodeChangeProposalResponse]:
        props = self.db.query(CodeChangeProposal).filter(
            CodeChangeProposal.workspace_id == workspace_id
        ).order_by(CodeChangeProposal.created_at.desc()).all()
        return [self._format_proposal(p) for p in props]

    def apply_proposal(self, workspace_id: str, proposal_id: str) -> CodeChangeProposalResponse:
        ws = self.get_workspace(workspace_id)
        if not ws:
            raise ValueError("Workspace not found")

        proposal = self.db.query(CodeChangeProposal).filter(
            CodeChangeProposal.id == proposal_id,
            CodeChangeProposal.workspace_id == workspace_id
        ).first()
        if not proposal:
            raise ValueError("Proposal not found")

        files = json.loads(proposal.files_json)
        
        # 1. Create safety backup
        backup_dir = patch_service.create_backup(ws.root_path, proposal.id, files)
        proposal.backup_path = str(backup_dir)

        # 2. Mark proposal APPLIED
        proposal.status = ProposalStatus.APPLIED.value
        proposal.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(proposal)
        logger.info(f"Successfully applied Code Proposal [{proposal.id}]")
        return self._format_proposal(proposal)

    def rollback_proposal(self, workspace_id: str, proposal_id: str) -> CodeChangeProposalResponse:
        ws = self.get_workspace(workspace_id)
        if not ws:
            raise ValueError("Workspace not found")

        proposal = self.db.query(CodeChangeProposal).filter(
            CodeChangeProposal.id == proposal_id,
            CodeChangeProposal.workspace_id == workspace_id
        ).first()
        if not proposal:
            raise ValueError("Proposal not found")

        patch_service.rollback_proposal(ws.root_path, proposal.id)
        proposal.status = ProposalStatus.ROLLED_BACK.value
        proposal.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(proposal)
        logger.info(f"Successfully rolled back Code Proposal [{proposal.id}]")
        return self._format_proposal(proposal)

    def _format_workspace(self, w: Workspace) -> WorkspaceResponse:
        return WorkspaceResponse(
            id=w.id,
            name=w.name,
            root_path=w.root_path,
            project_type=w.project_type,
            language=w.language,
            framework=w.framework,
            package_manager=w.package_manager,
            is_git=w.is_git,
            git_branch=w.git_branch,
            created_at=w.created_at,
            updated_at=w.updated_at
        )

    def _format_proposal(self, p: CodeChangeProposal) -> CodeChangeProposalResponse:
        return CodeChangeProposalResponse(
            id=p.id,
            workspace_id=p.workspace_id,
            title=p.title,
            reason=p.reason,
            risk_level=p.risk_level,
            diff_content=p.diff_content,
            files=json.loads(p.files_json or "[]"),
            status=ProposalStatus(p.status),
            backup_path=p.backup_path,
            created_at=p.created_at,
            updated_at=p.updated_at
        )
