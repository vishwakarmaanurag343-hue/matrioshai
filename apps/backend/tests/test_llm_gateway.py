import pytest
from app.llm.models import TaskComplexity, ModelCapability
from app.llm.classifier import task_complexity_classifier
from app.llm.gateway import llm_gateway

def test_task_complexity_classifier():
    # Trivial queries
    assert task_complexity_classifier.classify("hello") == TaskComplexity.TRIVIAL
    assert task_complexity_classifier.classify("thanks!") == TaskComplexity.TRIVIAL

    # Deep Reasoning queries
    assert task_complexity_classifier.classify("@5C Should we expand to multi-modal?") == TaskComplexity.DEEP_REASONING
    assert task_complexity_classifier.classify("Evaluate the architectural tradeoffs of our storage engine") == TaskComplexity.DEEP_REASONING

    # Autonomous Agent actions
    assert task_complexity_classifier.classify("Write code to implement payment gateway", is_agent_task=True) == TaskComplexity.AUTONOMOUS_AGENT
    assert task_complexity_classifier.classify("Apply patch to fix login bug") == TaskComplexity.AUTONOMOUS_AGENT

    # Standard queries
    assert task_complexity_classifier.classify("What is the capital of France?") == TaskComplexity.STANDARD

def test_llm_gateway_model_routing():
    model_spec = llm_gateway.route_model(TaskComplexity.DEEP_REASONING)
    assert model_spec.id is not None
    assert ModelCapability.REASONING in model_spec.capabilities
    assert model_spec.is_local is True
