import json
from typing import Optional, Dict, Any, List
from app.agent.models import PlanDefinition, StepDefinition
from app.agent.prompts import PLANNER_SYSTEM_PROMPT
from app.agent.validator import plan_validator
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.security.context_builder import context_builder
from app.security.classification import DestinationType
from app.core.logging import logger

class AgentPlanner:
    """
    Constructs bounded multi-step execution plans from user goals.
    Never executes tools directly.
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider or OllamaProvider()

    async def generate_plan(
        self,
        user_goal: str,
        workspace_context: Optional[str] = None,
        max_steps: int = 20
    ) -> PlanDefinition:
        retrieved = []
        if workspace_context:
            retrieved.append({
                "source_type": "workspace_context",
                "content": workspace_context
            })

        user_content = f"GOAL:\n{user_goal}\n\nMAX STEPS:\n{max_steps}\n\nGenerate execution plan."
        safe_messages = context_builder.build_safe_context(
            user_prompt=user_content,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            retrieved_items=retrieved,
            destination=DestinationType.LOCAL
        )

        logger.info("Generating bounded execution plan...")
        raw_res = await self.llm_provider.chat(messages=safe_messages, temperature=0.1)

        try:
            clean = raw_res.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            parsed = json.loads(clean.strip())

            raw_steps = parsed.get("steps", [])
            steps = []
            for i, s in enumerate(raw_steps[:max_steps], 1):
                steps.append(StepDefinition(
                    sequence=i,
                    objective=s.get("objective", f"Step {i}"),
                    action_type=s.get("action_type", "TOOL_CALL"),
                    tool_name=s.get("tool_name", "read_file"),
                    arguments=s.get("arguments", {}),
                    risk_level=s.get("risk_level", "LOW"),
                    approval_required=s.get("approval_required", False)
                ))

            plan = PlanDefinition(
                goal_summary=parsed.get("goal_summary", user_goal[:100]),
                steps=steps,
                estimated_risk=parsed.get("estimated_risk", "LOW")
            )
            return plan

        except Exception as e:
            logger.warning(f"Plan generation JSON parse failed ({e}), using safe fallback inspection plan")
            # Fallback safe inspection plan
            fallback_steps = [
                StepDefinition(
                    sequence=1,
                    objective="Inspect Git status",
                    action_type="TOOL_CALL",
                    tool_name="git_status",
                    arguments={},
                    risk_level="LOW",
                    approval_required=False
                )
            ]
            return PlanDefinition(
                goal_summary=user_goal[:100],
                steps=fallback_steps,
                estimated_risk="LOW"
            )

agent_planner = AgentPlanner()
