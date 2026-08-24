import pytest
from app.executive.roles import ExecutiveRole
from app.executive.models import ExecutiveResponse, ConfidenceLevel
from app.executive.service import ExecutiveService
from app.llm.base import LLMProvider

class Mock5CLLMProvider(LLMProvider):
    async def chat(self, messages, model=None, temperature=0.7) -> str:
        sys_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        
        # If synthesizing
        if "5C Executive Council Synthesizer" in sys_msg:
            return """{
                "summary": "5C Council recommends proceeding with cautious rollout.",
                "agreements": ["Market demand is validated (CMO, CEO).", "Technical foundation is ready (CTO)."],
                "conflicts": ["CFO expresses concern over burn rate vs CEO growth timeline.", "COO requires 2 weeks more for QA."],
                "critical_risks": ["Financial runway exhaustion if conversion is below 2%."],
                "missing_information": ["Validated customer acquisition costs in target tier."],
                "final_recommendation": "Launch closed beta to first 100 users while monitoring unit economics.",
                "next_actions": ["Conduct beta onboarding (COO)", "Track customer acquisition cost (CFO/CMO)"]
            }"""
        
        # Individual role mock responses
        if "CHIEF FINANCIAL OFFICER" in sys_msg:
            return """{
                "summary": "Insufficient financial data to confirm profit margins.",
                "key_findings": ["Current pricing structure is tentative"],
                "assumptions": ["Revenue per user = ₹2000/mo"],
                "risks": ["Negative gross margins without economies of scale"],
                "recommendations": ["Conduct unit economics sensitivity modeling"],
                "confidence": "LOW",
                "confidence_reason": "Missing historical conversion data",
                "missing_information": ["Hosting cost projections", "Payment gateway fees"]
            }"""

        return """{
            "summary": "Executive analysis complete.",
            "key_findings": ["Feasibility confirmed"],
            "assumptions": ["Target timeline is achievable"],
            "risks": ["Operational complexity"],
            "recommendations": ["Execute milestone 1"],
            "confidence": "HIGH",
            "confidence_reason": "Clear specs",
            "missing_information": ["None"]
        }"""

    async def stream_chat(self, messages, model=None, temperature=0.7):
        yield "mock"

    async def health(self):
        return {"connected": True, "model_available": True, "details": "Mock provider"}

    async def model_info(self, model_name: str):
        return {"name": model_name}

@pytest.mark.asyncio
async def test_5c_council_parallel_execution_and_synthesis(test_db):
    mock_provider = Mock5CLLMProvider()
    service = ExecutiveService(test_db, llm_provider=mock_provider)

    synthesis = await service.run_5c_council(
        prompt="Should we launch the new subscription plan?",
        save_as_decision=True,
        decision_title="Subscription Launch Decision"
    )

    assert len(synthesis.executive_assessments) == 5
    assert ExecutiveRole.CEO in synthesis.executive_assessments
    assert ExecutiveRole.CFO in synthesis.executive_assessments
    assert ExecutiveRole.CTO in synthesis.executive_assessments

    # Verify CFO surfaced missing information and low confidence due to data limits
    cfo_resp = synthesis.executive_assessments[ExecutiveRole.CFO]
    assert cfo_resp.confidence == ConfidenceLevel.LOW
    assert "Insufficient financial data" in cfo_resp.summary

    # Verify Synthesis detected cross-functional conflicts
    assert len(synthesis.agreements) >= 2
    assert len(synthesis.conflicts) >= 2
    assert "CFO expresses concern" in synthesis.conflicts[0]
    assert len(synthesis.next_actions) >= 2

@pytest.mark.asyncio
async def test_decision_persistence_and_memory_promotion(test_db):
    mock_provider = Mock5CLLMProvider()
    service = ExecutiveService(test_db, llm_provider=mock_provider)

    synthesis = await service.run_5c_council(
        prompt="Should we open source the security layer?",
        save_as_decision=True,
        decision_title="Open Source Security"
    )

    # 1. Check listed decisions
    decisions = service.list_decisions()
    assert len(decisions) >= 1
    d = next(dec for dec in decisions if dec.title == "Open Source Security")
    assert d.question == "Should we open source the security layer?"
    assert len(d.executive_inputs) == 5

    # 2. Promote to durable recall memory
    promoted = service.promote_decision_to_memory(d.id)
    assert promoted is True

    # 3. Verify memory search finds the decision
    mem_results = service.context_builder.memory_service.search_memory("Open Source Security")
    assert len(mem_results) >= 1
    assert "DECISION [Open Source Security]" in mem_results[0]["content"]
