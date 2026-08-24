import json
from typing import Optional, List, Dict, Any
from app.agent.models import PlanDefinition, StepDefinition
from app.agent.prompts import RECOVERY_SYSTEM_PROMPT
from app.agent.validator import plan_validator
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.security.audit import audit_logger
from app.core.logging import logger

class RecoveryEngine:
    """
    Handles step failures and formulates bounded recovery replans (max 3 retries).
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider or OllamaProvider()

    async def replan_on_failure(
        self,
        user_goal: str,
        failed_step: StepDefinition,
        error_msg: str,
        observations: List[str],
        retry_count: int,
        max_retries: int = 3
    ) -> Optional[PlanDefinition]:
        if retry_count >= max_retries:
            logger.warning(f"Replan aborted: retry count {retry_count} reached max {max_retries}.")
            return None

        prompt = f"GOAL: {user_goal}\nFAILED STEP {failed_step.sequence}: {failed_step.objective}\nERROR: {error_msg}\nOBSERVATIONS:\n" + "\n".join(observations[-3:])
        messages = [
            {"role": "system", "content": RECOVERY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Generating replan for retry attempt {retry_count + 1}/{max_retries}...")
        try:
            res = await self.llm_provider.chat(messages=messages, temperature=0.1)
            clean = res.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            parsed = json.loads(clean.strip())

            steps = []
            for i, s in enumerate(parsed.get("steps", [])[:5], failed_step.sequence):
                steps.append(StepDefinition(
                    sequence=i,
                    objective=s.get("objective", f"Recovery step {i}"),
                    action_type="TOOL_CALL",
                    tool_name=s.get("tool_name", "read_file"),
                    arguments=s.get("arguments", {}),
                    risk_level=s.get("risk_level", "LOW"),
                    approval_required=False
                ))

            candidate_plan = PlanDefinition(
                goal_summary=f"Recovery plan: {user_goal[:60]}",
                steps=steps,
                estimated_risk="LOW"
            )

            ok, reason, valid_plan = plan_validator.validate_plan(candidate_plan)
            if not ok:
                logger.error(f"Replan failed validation: {reason}")
                return None

            audit_logger.log_event(
                event_type="REPLAN_CREATED",
                action="replan_on_failure",
                decision="ALLOWED",
                reason=f"Generated {len(valid_plan.steps)} recovery steps on attempt {retry_count + 1}"
            )
            return valid_plan

        except Exception as e:
            logger.error(f"Failed to generate replan: {e}")
            return None

recovery_engine = RecoveryEngine()
