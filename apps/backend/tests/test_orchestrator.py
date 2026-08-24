import pytest
from app.orchestrator.models import UserIntent, OrchestrationTaskStatus
from app.orchestrator.router import intent_router
from app.orchestrator.context import unified_context_builder
from app.orchestrator.service import unified_orchestrator

def test_intent_router_classification():
    # Executive
    assert intent_router.classify_intent("@5C Should we expand to Windows?") == UserIntent.EXECUTIVE_REASONING
    assert intent_router.classify_intent("Should we launch this product now?") == UserIntent.EXECUTIVE_REASONING

    # Developer
    assert intent_router.classify_intent("Fix the bug in main.py and apply patch") == UserIntent.DEVELOPER_TASK

    # Communication
    assert intent_router.classify_intent("Reply to Alice on Telegram") == UserIntent.COMMUNICATION

    # Computer Use
    assert intent_router.classify_intent("Open Chrome and take screenshot") == UserIntent.COMPUTER_USE

    # Knowledge Query
    assert intent_router.classify_intent("What decisions did we make about Matrioshai?") == UserIntent.KNOWLEDGE_QUERY

def test_unified_context_assembly():
    ctx = unified_context_builder.assemble_context("What technologies does MATRIOSHAI use?")
    assert "prompt" in ctx
    assert "entities" in ctx
    assert "active_application" in ctx
    assert "unread_communications_count" in ctx

def test_orchestration_task_creation_and_plan():
    task = unified_orchestrator.create_task("Reply to client message on Telegram")
    assert task.id is not None
    assert task.intent == UserIntent.COMMUNICATION
    assert task.plan is not None
    assert len(task.plan.steps) == 3
    assert task.plan.steps[2].tool_name == "send_message"
    assert task.plan.steps[2].approval_required is True

def test_orchestration_task_cancellation():
    task = unified_orchestrator.create_task("Fix the bug in server")
    assert task.status != OrchestrationTaskStatus.CANCELLED
    
    ok = unified_orchestrator.cancel_task(task.id)
    assert ok is True
    assert unified_orchestrator.get_task(task.id).status == OrchestrationTaskStatus.CANCELLED

def test_daily_briefing():
    briefing = unified_orchestrator.get_daily_briefing()
    assert briefing.greeting is not None
    assert len(briefing.priorities) >= 1
    assert briefing.top_recommendation is not None
    assert briefing.executive_insight is not None

def test_global_search():
    res = unified_orchestrator.global_search("MATRIOSHAI")
    assert res.query == "MATRIOSHAI"
    assert len(res.results) >= 1
    sources = [r.source for r in res.results]
    assert "knowledge_graph" in sources
