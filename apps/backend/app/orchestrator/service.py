import uuid
from typing import Dict, List, Optional
from app.orchestrator.models import (
    UserIntent, OrchestrationTask, OrchestrationTaskStatus, ActionPlan, ActionStep,
    DailyBriefingResponse, GlobalSearchResponse, GlobalSearchResultItem, utc_now
)
from app.orchestrator.router import intent_router
from app.orchestrator.context import unified_context_builder
from app.knowledge.service import knowledge_graph_service
from app.communication.service import communication_service
from app.proactive.service import proactive_service
from app.security.confirmation import confirmation_system
from app.security.audit import audit_logger
from app.core.logging import logger

class UnifiedOrchestrator:
    """
    Central Coordinator for the MATRIOSHAI Operating System.
    Connects Memory, Knowledge, 5C, Developer, Computer, Communication, and Proactive intelligence.
    """

    def __init__(self):
        self._tasks: Dict[str, OrchestrationTask] = {}

    def create_task(self, user_prompt: str) -> OrchestrationTask:
        intent = intent_router.classify_intent(user_prompt)
        task_id = str(uuid.uuid4())
        
        # Assemble unified context
        ctx = unified_context_builder.assemble_context(user_prompt)

        # Formulate ActionPlan
        steps = []
        if intent == UserIntent.COMMUNICATION:
            steps.append(ActionStep(
                id=str(uuid.uuid4()),
                sequence=1,
                tool_name="get_unread_messages",
                reason="Read latest communication thread",
                risk_level="LOW",
                autonomy_tier="TIER_1",
                approval_required=False
            ))
            steps.append(ActionStep(
                id=str(uuid.uuid4()),
                sequence=2,
                tool_name="generate_reply",
                reason="Draft structured reply suggestions",
                risk_level="LOW",
                autonomy_tier="TIER_1",
                approval_required=False
            ))
            steps.append(ActionStep(
                id=str(uuid.uuid4()),
                sequence=3,
                tool_name="send_message",
                reason="Send approved message to recipient",
                risk_level="MEDIUM",
                autonomy_tier="TIER_2",
                approval_required=True
            ))
        elif intent == UserIntent.DEVELOPER_TASK:
            steps.append(ActionStep(
                id=str(uuid.uuid4()),
                sequence=1,
                tool_name="apply_patch",
                reason="Apply code modifications to project files",
                risk_level="MEDIUM",
                autonomy_tier="TIER_2",
                approval_required=True
            ))
        else:
            steps.append(ActionStep(
                id=str(uuid.uuid4()),
                sequence=1,
                tool_name="general_reasoning",
                reason="Analyze user prompt with unified context",
                risk_level="LOW",
                autonomy_tier="TIER_1",
                approval_required=False
            ))

        plan = ActionPlan(
            plan_id=str(uuid.uuid4()),
            goal=user_prompt,
            reason=f"Orchestrated plan for intent {intent.value}",
            intent=intent,
            steps=steps,
            risk_level="MEDIUM" if any(s.approval_required for s in steps) else "LOW",
            autonomy_tier="TIER_2" if any(s.approval_required for s in steps) else "TIER_1",
            expected_outcome="Task executed with safety verifications"
        )

        task = OrchestrationTask(
            id=task_id,
            user_prompt=user_prompt,
            intent=intent,
            status=OrchestrationTaskStatus.WAITING_APPROVAL if any(s.approval_required for s in steps) else OrchestrationTaskStatus.COMPLETED,
            plan=plan,
            current_step=0,
            result=f"Plan generated with {len(steps)} steps."
        )

        self._tasks[task.id] = task

        audit_logger.log_event(
            event_type="ORCHESTRATION_TASK_CREATED",
            action="create_task",
            resource=task.id,
            decision="ALLOWED",
            reason=f"Created task with intent: {intent.value}"
        )
        return task

    def get_task(self, task_id: str) -> Optional[OrchestrationTask]:
        return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task:
            task.status = OrchestrationTaskStatus.CANCELLED
            task.updated_at = utc_now()
            audit_logger.log_event(
                event_type="ORCHESTRATION_TASK_CANCELLED",
                action="cancel_task",
                resource=task_id,
                decision="ALLOWED"
            )
            return True
        return False

    def get_daily_briefing(self) -> DailyBriefingResponse:
        unreads = len(communication_service.get_all_unread())
        pending_confs = len([r for r in confirmation_system._pending_requests.values() if not r.approved])
        suggestions = proactive_service.get_active_suggestions()

        return DailyBriefingResponse(
            greeting="Good morning, Anurag. MATRIOSHAI is online and ready.",
            priorities=[
                "Follow up on architecture proposal with Alice",
                "Review Mac-first development roadmap"
            ],
            important_messages=unreads,
            open_decisions=1,
            upcoming_deadlines=1,
            pending_approvals=pending_confs,
            top_recommendation="Review pending communication reply drafts in Unified Inbox.",
            executive_insight="5C Consensus: Mac-first foundation provides optimal hardware leverage before Windows expansion."
        )

    def global_search(self, query: str) -> GlobalSearchResponse:
        results = []
        q = query.lower()

        # 1. Search Knowledge Graph
        ents = knowledge_graph_service.search_entities(query)
        for e in ents:
            results.append(GlobalSearchResultItem(
                id=e.id,
                source="knowledge_graph",
                title=f"Entity: {e.name} ({e.entity_type.value})",
                snippet=f"Canonical: {e.canonical_name}, Aliases: {', '.join(e.aliases)}",
                confidence=e.confidence
            ))

        # 2. Search Communication Messages
        msgs = communication_service.search_all_messages(query)
        for m in msgs:
            results.append(GlobalSearchResultItem(
                id=m.id,
                source="communication",
                title=f"Message from {m.sender}",
                snippet=m.text,
                confidence=0.95
            ))

        audit_logger.log_event(
            event_type="GLOBAL_SEARCH",
            action="global_search",
            resource=query,
            decision="ALLOWED",
            reason=f"Found {len(results)} matches"
        )
        return GlobalSearchResponse(query=query, results=results)

unified_orchestrator = UnifiedOrchestrator()
