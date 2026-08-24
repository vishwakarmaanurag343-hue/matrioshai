import pytest
from app.executive.roles import ExecutiveRole, ROLE_REGISTRY
from app.executive.router import ExecutiveRouter
from app.executive.models import ExecutiveResponse, SynthesisResponse, ConfidenceLevel
from app.executive.prompts import build_executive_prompt
from app.executive.reasoning import ExecutiveReasoningEngine
from app.llm.base import LLMProvider

class MockExecutiveLLMProvider(LLMProvider):
    async def chat(self, messages, model=None, temperature=0.7) -> str:
        return """{
            "summary": "Strategic evaluation indicates strong market viability.",
            "key_findings": ["Growing market segment", "Clear competitive differentiation"],
            "assumptions": ["Customer acquisition cost is below ₹1000"],
            "risks": ["Execution delay risk"],
            "recommendations": ["Initiate phased rollout"],
            "confidence": "HIGH",
            "confidence_reason": "High quality context provided",
            "missing_information": ["Competitor pricing details"]
        }"""

    async def stream_chat(self, messages, model=None, temperature=0.7):
        yield "mock"

    async def health(self):
        return {"connected": True, "model_available": True, "details": "Mock provider"}

    async def model_info(self, model_name: str):
        return {"name": model_name}

def test_executive_roles_metadata():
    assert len(ROLE_REGISTRY) == 5
    ceo_meta = ROLE_REGISTRY[ExecutiveRole.CEO]
    assert ceo_meta.role == ExecutiveRole.CEO
    assert "Strategy" in ceo_meta.focus_areas
    assert len(ceo_meta.core_questions) >= 4

    cfo_meta = ROLE_REGISTRY[ExecutiveRole.CFO]
    assert "Strictly distinguish KNOWN DATA" in cfo_meta.evidence_criteria

def test_executive_router_command_parsing():
    # Test @CEO command
    role, is_5c, clean = ExecutiveRouter.parse_command("@CEO Should we pivot the product?")
    assert role == ExecutiveRole.CEO
    assert is_5c is False
    assert clean == "Should we pivot the product?"

    # Test @5C command
    role, is_5c, clean = ExecutiveRouter.parse_command("@5C Should we launch next month?")
    assert role is None
    assert is_5c is True
    assert clean == "Should we launch next month?"

    # Test Case Insensitivity
    role, is_5c, clean = ExecutiveRouter.parse_command("@cto What database should we use?")
    assert role == ExecutiveRole.CTO
    assert clean == "What database should we use?"

    # Non-executive standard message
    role, is_5c, clean = ExecutiveRouter.parse_command("Hello Matrioshai, help me with a note")
    assert role is None
    assert is_5c is False
    assert clean == "Hello Matrioshai, help me with a note"

def test_role_prompt_construction():
    ceo_prompt = build_executive_prompt(ExecutiveRole.CEO)
    assert "CHIEF EXECUTIVE OFFICER" in ceo_prompt
    assert "You MUST return your response as a valid JSON object" in ceo_prompt
    assert "UNTRUSTED DATA" in ceo_prompt

    cfo_prompt = build_executive_prompt(ExecutiveRole.CFO)
    assert "CHIEF FINANCIAL OFFICER" in cfo_prompt
    assert "Insufficient financial data" in cfo_prompt

@pytest.mark.asyncio
async def test_executive_reasoning_engine_parsing():
    engine = ExecutiveReasoningEngine(MockExecutiveLLMProvider())
    resp = await engine.analyze(ExecutiveRole.CEO, [{"role": "user", "content": "Analyze launch"}])
    
    assert isinstance(resp, ExecutiveResponse)
    assert resp.role == ExecutiveRole.CEO
    assert resp.confidence == ConfidenceLevel.HIGH
    assert len(resp.key_findings) == 2
    assert "Growing market segment" in resp.key_findings[0]
