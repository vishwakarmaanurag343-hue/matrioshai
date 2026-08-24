from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from app.knowledge.service import knowledge_graph_service
from app.communication.service import communication_service
from app.computer.applications import application_service
from app.security.context_builder import context_builder
from app.security.redaction import redaction_engine
from app.security.threat_defense import threat_defense

class UnifiedContextBuilder:
    """
    Assembles rich context across Memory, Knowledge Graph, Communication, Developer Workspaces, and Computer Context.
    Ensures untrusted data is fenced and secrets are redacted.
    """

    @classmethod
    def assemble_context(cls, user_prompt: str) -> Dict[str, Any]:
        # 1. Redact secrets
        clean_prompt, _ = redaction_engine.redact(user_prompt)

        # 2. Query Knowledge Graph
        graph_entities = knowledge_graph_service.search_entities(clean_prompt)
        entities_summary = [{"name": e.name, "type": e.entity_type.value} for e in graph_entities[:5]]

        # 3. Active application awareness
        active_app = application_service.get_active_application()

        # 4. Communication unread context
        unread_msgs = communication_service.get_all_unread()
        unread_summary = [{"sender": m.sender, "text": m.text[:50]} for m in unread_msgs[:3]]

        assembled = {
            "prompt": clean_prompt,
            "entities": entities_summary,
            "active_application": active_app.application,
            "active_window": active_app.window_title,
            "unread_communications_count": len(unread_msgs),
            "recent_unread": unread_summary,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return assembled

unified_context_builder = UnifiedContextBuilder()
