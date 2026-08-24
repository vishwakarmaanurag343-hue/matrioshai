from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.tools.models import (
    WorkspaceCreate, WorkspaceResponse, ProjectTreeNode, FileContentResponse,
    SearchQueryRequest, SearchResultItem, GitStatusResponse, GitDiffResponse,
    CommandExecutionRequest, CommandExecutionResponse, CreateProposalRequest,
    CodeChangeProposalResponse, DiagnosticRequest, DiagnosticResult
)
from app.tools.service import DeveloperService
from app.tools.filesystem import safe_fs
from app.tools.git import git_service
from app.tools.shell import safe_shell
from app.tools.diagnostics import diagnostic_service

router = APIRouter(prefix="/workspaces", tags=["Developer Intelligence"])

@router.get("", response_model=List[WorkspaceResponse])
def list_workspaces(db: Session = Depends(get_db)):
    service = DeveloperService(db)
    return service.list_workspaces()

@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(req: WorkspaceCreate, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    try:
        return service.create_workspace(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{workspace_id}/tree", response_model=List[ProjectTreeNode])
def get_project_tree(workspace_id: str, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    ws = service.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return safe_fs.get_project_tree(ws.root_path)

@router.get("/{workspace_id}/file", response_model=FileContentResponse)
def read_file(workspace_id: str, path: str, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    ws = service.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        return safe_fs.read_file(ws.root_path, path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workspace_id}/search", response_model=List[SearchResultItem])
def search_code(workspace_id: str, req: SearchQueryRequest, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    ws = service.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return safe_fs.search_code(ws.root_path, req.query, req.max_results)

@router.get("/{workspace_id}/git/status", response_model=GitStatusResponse)
async def get_git_status(workspace_id: str, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    ws = service.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return await git_service.get_status(ws.root_path)

@router.get("/{workspace_id}/git/diff", response_model=GitDiffResponse)
async def get_git_diff(workspace_id: str, file_path: Optional[str] = None, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    ws = service.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return await git_service.get_diff(ws.root_path, file_path)

@router.post("/{workspace_id}/command", response_model=CommandExecutionResponse)
async def execute_command(workspace_id: str, req: CommandExecutionRequest, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    ws = service.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        return await safe_shell.execute_command(ws.root_path, req.command, req.timeout_seconds or 30)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Proposals & Rollbacks

@router.get("/{workspace_id}/proposals", response_model=List[CodeChangeProposalResponse])
def list_proposals(workspace_id: str, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    return service.list_proposals(workspace_id)

@router.post("/{workspace_id}/proposals", response_model=CodeChangeProposalResponse)
def create_proposal(workspace_id: str, req: CreateProposalRequest, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    try:
        return service.create_proposal(workspace_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workspace_id}/proposals/{proposal_id}/apply", response_model=CodeChangeProposalResponse)
def apply_proposal(workspace_id: str, proposal_id: str, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    try:
        return service.apply_proposal(workspace_id, proposal_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workspace_id}/proposals/{proposal_id}/rollback", response_model=CodeChangeProposalResponse)
def rollback_proposal(workspace_id: str, proposal_id: str, db: Session = Depends(get_db)):
    service = DeveloperService(db)
    try:
        return service.rollback_proposal(workspace_id, proposal_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workspace_id}/diagnose", response_model=DiagnosticResult)
async def diagnose_error(workspace_id: str, req: DiagnosticRequest):
    return await diagnostic_service.diagnose_error(req.error_log, req.command)
