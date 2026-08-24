from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.executive.roles import ExecutiveRole, ROLE_REGISTRY
from app.memory.memory_service import MemoryService
from app.services.notes_service import NotesService
from app.security.context_builder import context_builder
from app.security.classification import DestinationType
from app.executive.prompts import build_executive_prompt

class ExecutiveContextBuilder:
    """
    Builds role-aware safe context for individual executive roles.
    Prioritizes memory and notes relevant to the specific executive domain.
    All context passes strictly through PrivacyGatekeeper and ContextBuilder.
    """

    def __init__(self, db: Session):
        self.db = db
        self.memory_service = MemoryService(db)
        self.notes_service = NotesService(db)

    def build_role_context(
        self,
        role: ExecutiveRole,
        user_prompt: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        destination: DestinationType = DestinationType.LOCAL
    ) -> List[Dict[str, str]]:
        role_meta = ROLE_REGISTRY[role]

        # 1. Retrieve Core Memory (Global User Preferences & Facts)
        core_memories = [
            {"source": mem.source_type, "content": mem.content}
            for mem in self.memory_service.get_core_memory()
        ]

        # 2. Retrieve Role-Aware Recall Memory
        # Search using both the user's prompt and role-specific domain keywords
        role_keywords = " ".join(role_meta.memory_priorities)
        combined_query = f"{user_prompt} {role_keywords}"
        
        relevant_memories = [
            {"source_type": f"{role.value.lower()}_memory", "content": rm.get("content", "")}
            for rm in self.memory_service.search_memory(query=combined_query, limit=4)
            if rm.get("relevance_score", 0) > 0.4
        ]

        # 3. Retrieve relevant notes
        note_matches = self.notes_service.list_notes(query=user_prompt)
        retrieved_notes = [
            {"source_type": f"note_{n['title']}", "content": n['content']}
            for n in note_matches[:2]
        ]

        all_retrieved = relevant_memories + retrieved_notes

        # 4. Construct messages with role-specific system prompt
        messages = context_builder.build_safe_context(
            user_prompt=user_prompt,
            core_memories=core_memories,
            retrieved_items=all_retrieved,
            chat_history=chat_history,
            destination=destination
        )

        # Replace standard system instruction with role-specific executive prompt
        role_sys_prompt = build_executive_prompt(role)
        # Keep retrieved context from ContextBuilder, just prepend the executive role instructions
        if messages and messages[0]["role"] == "system":
            existing_untrusted = messages[0]["content"]
            # Extract UNTRUSTED RETRIEVED CONTEXT part if present
            if "[UNTRUSTED RETRIEVED CONTEXT" in existing_untrusted:
                untrusted_part = existing_untrusted[existing_untrusted.find("[UNTRUSTED RETRIEVED CONTEXT"):]
                messages[0]["content"] = f"{role_sys_prompt}\n\n{untrusted_part}"
            else:
                messages[0]["content"] = role_sys_prompt

        return messages
