from typing import List, Tuple
from app.agent.models import PlanDefinition, StepDefinition
from app.security.permissions import tool_registry, AutonomyTier, PermissionLevel
from app.security.audit import audit_logger
from app.core.logging import logger

class PlanValidator:
    """
    Validates proposed execution plans prior to execution:
    - Verifies all tools exist in ToolRegistry.
    - Rejects any plan containing Tier 3 operations (rm -rf, destructive wipes, etc.).
    - Flags Tier 2 actions as requiring explicit user confirmation.
    - Enforces maximum step bounds (max 20 steps).
    """

    MAX_ALLOWED_STEPS = 20

    @classmethod
    def validate_plan(cls, plan: PlanDefinition, workspace_root: str = None) -> Tuple[bool, str, PlanDefinition]:
        if len(plan.steps) == 0:
            return False, "Plan contains no steps.", plan

        if len(plan.steps) > cls.MAX_ALLOWED_STEPS:
            audit_logger.log_event(
                event_type="PLAN_VALIDATED",
                action="validate_plan",
                decision="BLOCKED",
                reason=f"Plan step count ({len(plan.steps)}) exceeds maximum limit of {cls.MAX_ALLOWED_STEPS}."
            )
            return False, f"Plan exceeds maximum allowed steps of {cls.MAX_ALLOWED_STEPS}", plan

        validated_steps: List[StepDefinition] = []

        for step in plan.steps:
            tool_def = tool_registry.get_tool(step.tool_name)
            if not tool_def:
                audit_logger.log_event(
                    event_type="PLAN_VALIDATED",
                    action="validate_plan",
                    decision="BLOCKED",
                    reason=f"Tool '{step.tool_name}' in step {step.sequence} is not in ToolRegistry."
                )
                return False, f"Unknown tool '{step.tool_name}' in step {step.sequence}", plan

            # Check Tier 3 prohibited operations
            if tool_def.autonomy_tier == AutonomyTier.TIER_3 or tool_def.permission_level == PermissionLevel.DESTRUCTIVE:
                audit_logger.log_event(
                    event_type="PLAN_VALIDATED",
                    action="validate_plan",
                    decision="BLOCKED",
                    reason=f"Tier 3 / Destructive tool '{step.tool_name}' in step {step.sequence} is strictly prohibited from agent plans."
                )
                return False, f"Prohibited Tier 3 tool '{step.tool_name}' in step {step.sequence}", plan

            # Set approval requirement if Tier 2
            needs_approval = (tool_def.autonomy_tier == AutonomyTier.TIER_2 or tool_def.requires_confirmation)
            risk = "MEDIUM" if needs_approval else "LOW"

            validated_steps.append(StepDefinition(
                sequence=step.sequence,
                objective=step.objective,
                action_type=step.action_type,
                tool_name=step.tool_name,
                arguments=step.arguments,
                risk_level=risk,
                approval_required=needs_approval
            ))

        validated_plan = PlanDefinition(
            goal_summary=plan.goal_summary,
            steps=validated_steps,
            estimated_risk="MEDIUM" if any(s.approval_required for s in validated_steps) else "LOW"
        )

        audit_logger.log_event(
            event_type="PLAN_VALIDATED",
            action="validate_plan",
            decision="ALLOWED",
            reason=f"Plan with {len(validated_steps)} steps successfully validated."
        )

        return True, "Plan valid", validated_plan

plan_validator = PlanValidator()
