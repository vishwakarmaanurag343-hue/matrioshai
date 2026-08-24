import asyncio
import json
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.executive.roles import ExecutiveRole, ROLE_REGISTRY
from app.executive.models import (
    ExecutiveResponse, SynthesisResponse, AnalyzeRequest, Council5CRequest,
    DecisionResponse, DecisionInputItem, DecisionStatus, ConfidenceLevel
)
from app.executive.context import ExecutiveContextBuilder
from app.executive.reasoning import ExecutiveReasoningEngine
from app.executive.synthesis import SynthesisEngine
from app.executive.router import ExecutiveRouter
from app.models.db_models import Decision, DecisionExecutiveInput, MemoryItem, utc_now
from app.llm.base import LLMProvider
from app.security.audit import audit_logger
from app.core.logging import logger

class ExecutiveService:
    """
    Main 5C Executive Service Layer.
    Orchestrates:
    - Single executive role analysis
    - Parallel 5C council analysis with concurrency boundaries and timeout
    - Cross-functional synthesis
    - Normalized SQLite Decision records persistence
    - Revisit decision workflow
    - Promoting finalized decisions into durable Memory
    """

    def __init__(self, db: Session, llm_provider: Optional[LLMProvider] = None):
        self.db = db
        self.context_builder = ExecutiveContextBuilder(db)
        self.reasoning_engine = ExecutiveReasoningEngine(llm_provider)
        self.synthesis_engine = SynthesisEngine(llm_provider)

    async def analyze_role(
        self,
        role: ExecutiveRole,
        prompt: str,
        conversation_id: Optional[str] = None
    ) -> ExecutiveResponse:
        audit_logger.log_event(
            event_type="EXECUTIVE_ANALYSIS",
            action=f"analyze_role:{role.value}",
            resource=prompt[:100],
            decision="ALLOWED",
            reason=f"Executed 5C reasoning for role {role.value}"
        )
        
        messages = self.context_builder.build_role_context(
            role=role,
            user_prompt=prompt,
        )

        return await self.reasoning_engine.analyze(role=role, messages=messages)

    async def run_5c_council(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        save_as_decision: bool = True,
        decision_title: Optional[str] = None
    ) -> SynthesisResponse:
        audit_logger.log_event(
            event_type="EXECUTIVE_COUNCIL",
            action="run_5c_council",
            resource=prompt[:100],
            decision="ALLOWED",
            reason="Executed parallel 5C Executive Council evaluation"
        )

        # 1. Execute all 5 roles in parallel with concurrency safety and timeout
        roles = [ExecutiveRole.CEO, ExecutiveRole.COO, ExecutiveRole.CFO, ExecutiveRole.CMO, ExecutiveRole.CTO]
        
        async def _eval_role(r: ExecutiveRole):
            msgs = self.context_builder.build_role_context(role=r, user_prompt=prompt)
            return r, await self.reasoning_engine.analyze(role=r, messages=msgs)

        try:
            # 60 second bounded timeout for parallel council execution
            results = await asyncio.wait_for(
                asyncio.gather(*[_eval_role(r) for r in roles], return_exceptions=True),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            logger.error("5C Council execution timed out.")
            raise TimeoutError("5C Council evaluation timed out after 60s.")

        assessments: Dict[ExecutiveRole, ExecutiveResponse] = {}
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Error in executive role evaluation: {res}")
                continue
            role, response = res
            assessments[role] = response

        # 2. Execute Cross-Functional Synthesis
        synthesis = await self.synthesis_engine.synthesize(question=prompt, assessments=assessments)

        # 3. Persist Decision Record in SQLite if requested
        if save_as_decision:
            title = decision_title or (prompt[:50] + "..." if len(prompt) > 50 else prompt)
            self.persist_decision(title=title, question=prompt, synthesis=synthesis)

        return synthesis

    def persist_decision(
        self,
        title: str,
        question: str,
        synthesis: SynthesisResponse,
        status: DecisionStatus = DecisionStatus.OPEN
    ) -> Decision:
        decision = Decision(
            title=title,
            question=question,
            status=status.value,
            final_recommendation=synthesis.final_recommendation,
            reasoning_summary=synthesis.summary,
            agreements_json=json.dumps(synthesis.agreements),
            conflicts_json=json.dumps(synthesis.conflicts),
            critical_risks_json=json.dumps(synthesis.critical_risks),
            next_actions_json=json.dumps(synthesis.next_actions)
        )
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)

        # Save individual executive inputs
        for role, resp in synthesis.executive_assessments.items():
            input_row = DecisionExecutiveInput(
                decision_id=decision.id,
                role=role.value,
                summary=resp.summary,
                key_findings_json=json.dumps(resp.key_findings),
                assumptions_json=json.dumps(resp.assumptions),
                risks_json=json.dumps(resp.risks),
                recommendations_json=json.dumps(resp.recommendations),
                confidence=resp.confidence.value,
                missing_info_json=json.dumps(resp.missing_information)
            )
            self.db.add(input_row)

        self.db.commit()
        self.db.refresh(decision)
        logger.info(f"Persisted 5C Decision Record [{decision.id}] - '{decision.title}'")
        return decision

    def list_decisions(self) -> List[DecisionResponse]:
        decisions = self.db.query(Decision).order_by(Decision.created_at.desc()).all()
        return [self._format_decision_response(d) for d in decisions]

    def get_decision(self, decision_id: str) -> Optional[DecisionResponse]:
        d = self.db.query(Decision).filter(Decision.id == decision_id).first()
        if not d:
            return None
        return self._format_decision_response(d)

    def update_decision_status(self, decision_id: str, status: DecisionStatus) -> Optional[DecisionResponse]:
        d = self.db.query(Decision).filter(Decision.id == decision_id).first()
        if not d:
            return None
        d.status = status.value
        d.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(d)
        return self._format_decision_response(d)

    def promote_decision_to_memory(self, decision_id: str) -> bool:
        d = self.db.query(Decision).filter(Decision.id == decision_id).first()
        if not d:
            return False

        memory_content = (
            f"DECISION [{d.title}]: {d.question}\n"
            f"Final Recommendation: {d.final_recommendation}\n"
            f"Status: {d.status}"
        )
        mem = MemoryItem(
            source_type="5c_decision",
            source_id=d.id,
            content=memory_content,
            memory_tier="RECALL",
            classification="PRIVATE",
            metadata_json=json.dumps({"decision_id": d.id, "title": d.title})
        )
        self.db.add(mem)
        self.db.commit()
        logger.info(f"Promoted Decision [{d.id}] to durable Recall Memory.")
        return True

    def _format_decision_response(self, d: Decision) -> DecisionResponse:
        inputs = []
        for inp in d.executive_inputs:
            inputs.append(DecisionInputItem(
                id=inp.id,
                role=ExecutiveRole(inp.role),
                summary=inp.summary,
                key_findings=json.loads(inp.key_findings_json or "[]"),
                assumptions=json.loads(inp.assumptions_json or "[]"),
                risks=json.loads(inp.risks_json or "[]"),
                recommendations=json.loads(inp.recommendations_json or "[]"),
                confidence=ConfidenceLevel(inp.confidence),
                missing_information=json.loads(inp.missing_info_json or "[]")
            ))

        return DecisionResponse(
            id=d.id,
            title=d.title,
            question=d.question,
            status=DecisionStatus(d.status),
            final_recommendation=d.final_recommendation,
            reasoning_summary=d.reasoning_summary,
            agreements=json.loads(d.agreements_json or "[]"),
            conflicts=json.loads(d.conflicts_json or "[]"),
            critical_risks=json.loads(d.critical_risks_json or "[]"),
            next_actions=json.loads(d.next_actions_json or "[]"),
            executive_inputs=inputs,
            created_at=d.created_at,
            updated_at=d.updated_at
        )
