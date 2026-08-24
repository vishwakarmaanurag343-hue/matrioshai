from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.orchestrator.models import (
    OrchestrationTask, DailyBriefingResponse, GlobalSearchResponse
)
from app.orchestrator.service import unified_orchestrator

router = APIRouter(prefix="/orchestrator", tags=["Unified Orchestration"])

@router.post("/tasks", response_model=OrchestrationTask)
def create_orchestration_task(user_prompt: str):
    return unified_orchestrator.create_task(user_prompt)

@router.get("/tasks/{task_id}", response_model=OrchestrationTask)
def get_task(task_id: str):
    task = unified_orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/tasks/{task_id}/cancel", response_model=dict)
def cancel_task(task_id: str):
    ok = unified_orchestrator.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "CANCELLED"}

@router.get("/briefing", response_model=DailyBriefingResponse)
def get_daily_briefing():
    return unified_orchestrator.get_daily_briefing()

@router.get("/search", response_model=GlobalSearchResponse)
def global_search(query: str = Query(...)):
    return unified_orchestrator.global_search(query)
