from app.orchestrator.models import UserIntent

class IntentRouter:
    """
    Classifies user requests into architectural domain intents.
    NEVER directly executes tools.
    """

    @classmethod
    def classify_intent(cls, prompt: str) -> UserIntent:
        p = prompt.lower().strip()

        # 1. 5C Executive Reasoning / Decisions
        if any(tag in p for tag in ("@5c", "@ceo", "@coo", "@cfo", "@cmo", "@cto")) or \
           any(phrase in p for phrase in ("should we launch", "executive decision", "strategic evaluation", "business strategy")):
            return UserIntent.EXECUTIVE_REASONING

        # 2. Developer Tasks
        if any(phrase in p for phrase in ("fix the bug", "write a test", "git commit", "create file", "run diagnostics", "apply patch", "npm install", "refactor")):
            return UserIntent.DEVELOPER_TASK

        # 3. Communication Intelligence
        if any(phrase in p for phrase in ("reply to", "send message", "unread messages", "email client", "telegram", "whatsapp", "inbox")):
            return UserIntent.COMMUNICATION

        # 4. Computer Use
        if any(phrase in p for phrase in ("open chrome", "click on", "take screenshot", "type in app", "frontmost window", "screen perception")):
            return UserIntent.COMPUTER_USE

        # 5. Knowledge / Memory Query
        if any(phrase in p for phrase in ("what decisions did we make", "what do you remember", "what entities", "who works on")):
            return UserIntent.KNOWLEDGE_QUERY

        # 6. Multi-domain reasoning
        if ("client" in p and "proposal" in p and "what should i do" in p) or ("analyze" in p and "technically and financially" in p):
            return UserIntent.MULTI_DOMAIN

        return UserIntent.GENERAL_CHAT

intent_router = IntentRouter()
