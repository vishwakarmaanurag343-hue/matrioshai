from typing import List
from fastapi import APIRouter, HTTPException
from app.proactive.models import ProactiveSuggestion
from app.proactive.service import proactive_service

router = APIRouter(prefix="/proactive", tags=["Proactive Intelligence"])

@router.get("", response_model=List[ProactiveSuggestion])
def get_suggestions():
    return proactive_service.get_active_suggestions()

@router.post("/{suggestion_id}/dismiss", response_model=dict)
def dismiss_suggestion(suggestion_id: str):
    ok = proactive_service.dismiss_suggestion(suggestion_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return {"status": "DISMISSED"}

@router.post("/{suggestion_id}/snooze", response_model=dict)
def snooze_suggestion(suggestion_id: str):
    ok = proactive_service.snooze_suggestion(suggestion_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return {"status": "SNOOZED"}
