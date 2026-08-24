import json
from typing import Optional
from app.communication.models import ConversationSummaryResponse, CommunicationConversation
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.communication.privacy import communication_privacy
from app.core.logging import logger

SUMMARIZE_PROMPT = """
You are the MATRIOSHAI Communication Summarizer.
Summarize the conversation thread, extract important points, open questions, and action items.
Respond ONLY in valid raw JSON matching this format:
{
  "summary": "Concise summary of current discussion",
  "important_points": ["Point 1", "Point 2"],
  "open_questions": ["Question 1"],
  "action_items": ["Action item 1"],
  "confidence": "HIGH"
}
"""

class SummarizationService:
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider or OllamaProvider()

    async def summarize_conversation(self, conv: CommunicationConversation) -> ConversationSummaryResponse:
        recent_text = "\n".join([f"{m.sender}: {m.text}" for m in conv.recent_messages])
        fenced_input, _ = communication_privacy.sanitize_message_content(recent_text)

        messages = [
            {"role": "system", "content": SUMMARIZE_PROMPT},
            {"role": "user", "content": f"CONVERSATION:\n{fenced_input}\n\nSummarize."}
        ]

        logger.info(f"Summarizing conversation '{conv.title}'...")
        try:
            res = await self.llm_provider.chat(messages=messages, temperature=0.1)
            clean = res.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            parsed = json.loads(clean.strip())
            return ConversationSummaryResponse(
                conversation_id=conv.id,
                summary=parsed.get("summary", "Conversation reviewed."),
                important_points=parsed.get("important_points", []),
                open_questions=parsed.get("open_questions", []),
                action_items=parsed.get("action_items", []),
                confidence=parsed.get("confidence", "HIGH")
            )
        except Exception:
            return ConversationSummaryResponse(
                conversation_id=conv.id,
                summary=f"Discussion involving {', '.join(conv.participants)} with {len(conv.recent_messages)} messages.",
                important_points=[m.text[:100] for m in conv.recent_messages[-2:]],
                open_questions=[],
                action_items=["Review message thread"],
                confidence="MEDIUM"
            )

summarization_service = SummarizationService()
