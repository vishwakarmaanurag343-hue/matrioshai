import uuid
from typing import Dict, List, Optional
from app.proactive.models import ProactiveSuggestion, ProactiveSignalType, ProactivePriority, utc_now
from app.security.audit import audit_logger

class ProactiveService:
    """
    Proactive Intelligence Engine.
    Discovers actionable signals (deadlines, unanswered communications, unresolved decisions)
    with explainable evidence and user dismissal controls.
    """

    def __init__(self):
        self._suggestions: Dict[str, ProactiveSuggestion] = {}
        self._seed_default_suggestions()

    def _seed_default_suggestions(self):
        s1 = ProactiveSuggestion(
            id="sug_unanswered_1",
            signal_type=ProactiveSignalType.UNANSWERED_COMMUNICATION,
            priority=ProactivePriority.IMPORTANT,
            title="Unanswered message from Alice (Client)",
            reason="Alice asked for the architecture proposal update with no subsequent reply.",
            evidence="Inbound message in Telegram: 'Can you send the updated architecture proposal by tomorrow?'",
            suggested_action="Review draft reply or open Communication workspace."
        )
        s2 = ProactiveSuggestion(
            id="sug_decision_1",
            signal_type=ProactiveSignalType.UNRESOLVED_DECISION,
            priority=ProactivePriority.NORMAL,
            title="Pending 5C Decision: Mac-first vs Multi-platform",
            reason="Decision has been open for 3 days without final executive synthesis signoff.",
            evidence="Decision record 'Mac-first Foundation' has status OPEN in 5C Council.",
            suggested_action="Open 5C Executive tab to review synthesized recommendation."
        )
        self._suggestions[s1.id] = s1
        self._suggestions[s2.id] = s2

    def get_active_suggestions(self) -> List[ProactiveSuggestion]:
        return [s for s in self._suggestions.values() if not s.is_dismissed and not s.is_snoozed]

    def dismiss_suggestion(self, suggestion_id: str) -> bool:
        sug = self._suggestions.get(suggestion_id)
        if sug:
            sug.is_dismissed = True
            audit_logger.log_event(
                event_type="PROACTIVE_SUGGESTION_DISMISSED",
                action="dismiss",
                resource=suggestion_id,
                decision="ALLOWED",
                reason="User dismissed proactive suggestion"
            )
            return True
        return False

    def snooze_suggestion(self, suggestion_id: str) -> bool:
        sug = self._suggestions.get(suggestion_id)
        if sug:
            sug.is_snoozed = True
            audit_logger.log_event(
                event_type="PROACTIVE_SUGGESTION_SNOOZED",
                action="snooze",
                resource=suggestion_id,
                decision="ALLOWED",
                reason="User snoozed proactive suggestion"
            )
            return True
        return False

proactive_service = ProactiveService()
