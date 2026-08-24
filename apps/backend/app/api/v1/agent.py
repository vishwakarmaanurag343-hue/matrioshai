from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.agent.models import (
    TaskCreateRequest, TaskResponse, StepApprovalRequest
)
from app.agent.service import AgentService
from app.agent.state import agent_state_manager

router = APIRouter(prefix="/agent", tags=["Agent Runtime"])

@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(req: TaskCreateRequest, db: Session = Depends(get_db)):
    service = AgentService(db)
    return await service.create_and_plan_task(req)

@router.get("/tasks", response_model=List[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    service = AgentService(db)
    return service.list_tasks()

@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    service = AgentService(db)
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/tasks/{task_id}/pause", response_model=TaskResponse)
def pause_task(task_id: str, db: Session = Depends(get_db)):
    service = AgentService(db)
    try:
        return service.pause_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/tasks/{task_id}/resume", response_model=TaskResponse)
def resume_task(task_id: str, db: Session = Depends(get_db)):
    service = AgentService(db)
    try:
        return service.resume_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(task_id: str, db: Session = Depends(get_db)):
    service = AgentService(db)
    try:
        return service.cancel_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/tasks/{task_id}/steps/{step_id}/approve", response_model=TaskResponse)
async def approve_step(task_id: str, step_id: str, req: StepApprovalRequest, db: Session = Depends(get_db)):
    service = AgentService(db)
    try:
        return await service.approve_step(task_id, step_id, req.approved)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.websocket("/tasks/{task_id}/events")
async def task_events_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    queue = agent_state_manager.subscribe(task_id)
    try:
        while True:
            event_data = await queue.get()
            await websocket.send_json(event_data)
    except WebSocketDisconnect:
        agent_state_manager.unsubscribe(task_id, queue)
