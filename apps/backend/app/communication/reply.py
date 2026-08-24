import json
from typing import Optional, List
from app.communication.models import ReplySuggestionResponse, ReplyOption, CommunicationConversation
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.communication.privacy import communication_privacy
from app.core.logging import logger

REPLY_SYSTEM_PROMPT = """
You are the MATRIOSHAI Communication Assistant.
Generate 4 diverse reply drafts for the active conversation in the following styles:
1. Professional
2. Friendly
3. Concise
4. Detailed

Respond ONLY in valid raw JSON with this format:
{
  "options": [
    {"style": "Professional", "reply_text": "Thank you for the update. I will review and follow up shortly."},
    {"style": "Friendly", "reply_text": "Thanks for sharing! I'll take a look and get back to you soon."},
    {"style": "Concise", "reply_text": "Thanks, will review today."},
    {"style": "Detailed", "reply_text": "Thank you for the details. I have received the proposal and will analyze the scope before sending my feedback."}
  ]
}
"""

class ReplyService:
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider or OllamaProvider()

    async def generate_replies(self, conv: CommunicationConversation) -> ReplySuggestionResponse:
        recent_text = "\n".join([f"{m.sender}: {m.text}" for m in conv.recent_messages[-5:]])
        fenced_input, _ = communication_privacy.sanitize_message_content(recent_text)

        messages = [
            {"role": "system", "content": REPLY_SYSTEM_PROMPT},
            {"role": "user", "content": f"CONVERSATION:\n{fenced_input}\n\nGenerate replies."}
        ]

        logger.info(f"Generating styled reply suggestions for conversation '{conv.title}'...")
        try:
            res = await self.llm_provider.chat(messages=messages, temperature=0.2)
            clean = res.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            parsed = json.loads(clean.strip())
            
            options = [
                ReplyOption(style=opt.get("style", "Standard"), reply_text=opt.get("reply_text", ""))
                for opt in parsed.get("options", [])
            ]
            return ReplySuggestionResponse(conversation_id=conv.id, options=options)
        except Exception:
            # Fallback deterministic replies
            fallback_options = [
                ReplyOption(style="Professional", reply_text="Thank you for your message. I am reviewing the details and will get back to you shortly."),
                ReplyOption(style="Friendly", reply_text="Thanks for reaching out! I'll review and follow up soon."),
                ReplyOption(style="Concise", reply_text="Received. Will review shortly."),
                ReplyOption(style="Detailed", reply_text="Thank you for providing the update. I have noted the points and will prepare the required next steps.")
            ]
            return ReplySuggestionResponse(conversation_id=conv.id, options=fallback_options)

reply_service = ReplyService()
