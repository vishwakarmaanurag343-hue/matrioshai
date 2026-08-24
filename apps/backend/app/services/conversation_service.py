import json
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.db_models import Conversation, Message, utc_now
from app.memory.memory_service import MemoryService
from app.security.context_builder import context_builder
from app.security.classification import DestinationType
from app.core.logging import logger

class ConversationService:
    def __init__(self, db: Session):
        self.db = db
        self.memory_service = MemoryService(db)

    def create_conversation(self, title: Optional[str] = "New Conversation") -> Conversation:
        title_clean = (title or "New Conversation").strip()
        conv = Conversation(title=title_clean)
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        logger.info(f"Created conversation [{conv.id}] - '{conv.title}'")
        return conv

    def list_conversations(self, include_archived: bool = False) -> List[Conversation]:
        q = self.db.query(Conversation)
        if not include_archived:
            q = q.filter(Conversation.archived == False)
        return q.order_by(Conversation.updated_at.desc()).all()

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        return self.db.query(Conversation).filter(Conversation.id == conversation_id).first()

    def update_conversation(self, conversation_id: str, title: Optional[str] = None, archived: Optional[bool] = None) -> Optional[Conversation]:
        conv = self.get_conversation(conversation_id)
        if not conv:
            return None
        if title is not None:
            conv.title = title.strip()
        if archived is not None:
            conv.archived = archived
        conv.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def delete_conversation(self, conversation_id: str) -> bool:
        conv = self.get_conversation(conversation_id)
        if not conv:
            return False
        self.db.delete(conv)
        self.db.commit()
        logger.info(f"Deleted conversation [{conversation_id}]")
        return True

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        conv = self.get_conversation(conversation_id)
        if not conv:
            raise ValueError(f"Conversation [{conversation_id}] not found.")

        meta_json = json.dumps(metadata) if metadata else None
        now_time = utc_now()
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=now_time,
            model=model,
            metadata_json=meta_json
        )
        self.db.add(msg)
        conv.updated_at = now_time
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def build_llm_messages(
        self,
        conversation_id: str,
        prompt: str,
        destination: DestinationType = DestinationType.LOCAL
    ) -> List[Dict[str, str]]:
        """
        Builds LLM messages through ContextBuilder and PrivacyGatekeeper.
        Protects against prompt injection by isolating untrusted retrieved data.
        """
        # 1. Retrieve Core Memory
        core_memories = [
            {"source": mem.source_type, "content": mem.content}
            for mem in self.memory_service.get_core_memory()
        ]

        # 2. Retrieve Recall Memory
        relevant_memories = [
            {"source_type": rm.get("source_type", "recall"), "content": rm.get("content", "")}
            for rm in self.memory_service.search_memory(query=prompt, limit=3)
            if rm.get("relevance_score", 0) > 0.5
        ]

        # 3. Retrieve recent chat history
        chat_history = []
        conv = self.get_conversation(conversation_id)
        if conv and conv.messages:
            recent_msgs = conv.messages[-10:]
            for m in recent_msgs:
                chat_history.append({"role": m.role, "content": m.content})

        # 4. Construct safe context
        return context_builder.build_safe_context(
            user_prompt=prompt,
            core_memories=core_memories,
            retrieved_items=relevant_memories,
            chat_history=chat_history,
            destination=destination
        )
