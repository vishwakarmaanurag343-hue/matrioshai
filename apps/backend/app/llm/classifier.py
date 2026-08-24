from app.llm.models import TaskComplexity

class TaskComplexityClassifier:
    """
    Evaluates user prompts and architectural intent to classify task complexity.
    Prevents invoking heavy reasoning models for trivial lookups while ensuring
    deep reasoning is applied to strategy, architecture, and coding tasks.
    """

    @classmethod
    def classify(cls, prompt: str, is_agent_task: bool = False) -> TaskComplexity:
        if is_agent_task:
            return TaskComplexity.AUTONOMOUS_AGENT

        p = prompt.strip().lower()

        # 1. Trivial check (short greetings, affirmations)
        if len(p) < 20 and any(w in p for w in ("hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "good morning")):
            return TaskComplexity.TRIVIAL

        # 2. Deep Reasoning check (5C tags, strategy, math, architecture, complex refactoring)
        if any(tag in p for tag in ("@5c", "@ceo", "@coo", "@cfo", "@cmo", "@cto")) or \
           any(phrase in p for phrase in ("strategy", "architecture", "financial analysis", "tradeoff", "evaluate", "compare", "refactor", "diagnose")):
            return TaskComplexity.DEEP_REASONING

        # 3. Autonomous agent actions
        if any(action in p for action in ("write code", "apply patch", "run tests", "fix bug", "execute plan", "automate")):
            return TaskComplexity.AUTONOMOUS_AGENT

        # 4. Standard default
        return TaskComplexity.STANDARD

task_complexity_classifier = TaskComplexityClassifier()
