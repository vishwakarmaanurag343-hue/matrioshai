from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.executive.roles import ExecutiveRole, ROLE_REGISTRY, RoleMetadata
from app.executive.models import (
    ExecutiveResponse, SynthesisResponse, AnalyzeRequest, Council5CRequest,
    DecisionResponse, DecisionStatus
)
from app.executive.service import ExecutiveService

router = APIRouter(prefix="/executive", tags=["5C Executive Intelligence"])

@router.get("/roles", response_model=List[RoleMetadata])
def list_executive_roles():
    return list(ROLE_REGISTRY.values())

@router.post("/analyze", response_model=ExecutiveResponse)
async def analyze_single_role(req: AnalyzeRequest, db: Session = Depends(get_db)):
    service = ExecutiveService(db)
    return await service.analyze_role(
        role=req.role,
        prompt=req.prompt,
        conversation_id=req.conversation_id
    )

@router.post("/5c", response_model=SynthesisResponse)
async def run_5c_council(req: Council5CRequest, db: Session = Depends(get_db)):
    service = ExecutiveService(db)
    return await service.run_5c_council(
        prompt=req.prompt,
        conversation_id=req.conversation_id,
        save_as_decision=req.save_as_decision,
        decision_title=req.decision_title
    )

# --- Decision Record Endpoints ---

@router.get("/decisions", response_model=List[DecisionResponse])
def list_decisions(db: Session = Depends(get_db)):
    service = ExecutiveService(db)
    return service.list_decisions()

@router.get("/decisions/{decision_id}", response_model=DecisionResponse)
def get_decision(decision_id: str, db: Session = Depends(get_db)):
    service = ExecutiveService(db)
    decision = service.get_decision(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision

@router.patch("/decisions/{decision_id}/status", response_model=DecisionResponse)
def update_decision_status(decision_id: str, status: DecisionStatus, db: Session = Depends(get_db)):
    service = ExecutiveService(db)
    updated = service.update_decision_status(decision_id, status)
    if not updated:
        raise HTTPException(status_code=404, detail="Decision not found")
    return updated

@router.post("/decisions/{decision_id}/promote-to-memory")
def promote_decision_to_memory(decision_id: str, db: Session = Depends(get_db)):
    service = ExecutiveService(db)
    promoted = service.promote_decision_to_memory(decision_id)
    if not promoted:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"status": "promoted", "decision_id": decision_id}

@router.post("/decisions/{decision_id}/revisit", response_model=SynthesisResponse)
async def revisit_decision(decision_id: str, db: Session = Depends(get_db)):
    service = ExecutiveService(db)
    d = service.get_decision(decision_id)
    if not d:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    # Re-evaluate with current context
    revisit_prompt = f"REVISITING DECISION: {d.question}\nPrevious Recommendation: {d.final_recommendation}"
    synthesis = await service.run_5c_council(
        prompt=revisit_prompt,
        save_as_decision=True,
        decision_title=f"Revisit: {d.title}"
    )
    service.update_decision_status(decision_id, DecisionStatus.REVISIT)
    return synthesis
