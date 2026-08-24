"""
MATRIOSHAI Closed-Loop Agent Planning & Execution Engine (Phase 10)

Coordinates Goal Understanding, World Model Observation, Deterministic Planning,
Safe Action Dispatch, Multi-Signal Verification, and Dynamic Replanning.
Never treats action execution as task success. Operates as a closed loop.
"""

import time
import json
import secrets
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Set
from app.core.logging import logger
from app.browser.state_store import (
    browser_state_store,
    BrowserStateStore,
    ActionIntent,
    ActionType,
    ActionTarget,
    ActionPostcondition,
    ActionResult,
    ActionStatus,
    BrowserWorldModel,
    BrowserWorldSnapshot,
    WorldElement,
    WorldPageState,
    VerificationResult,
    VerificationStatus,
    FailureClass,
    RecoveryType,
    IdempotencyClass,
    AgentTaskState,
    TaskPriority,
    PlanDecisionType,
    TabRole,
    TaskTabContext,
    TaskAssumption,
    SuccessCriterion,
    AgentGoal,
    PlanStep,
    AgentPlan,
    PlanDecision,
    TaskProgress,
    TaskMemory,
    AgentResult,
    AgentTask,
    AgentEvent
)
from app.browser.world_model import world_model_engine
from app.browser.action_engine import action_engine
from app.browser.verification_engine import verification_engine
from app.llm.gateway import llm_gateway

class GoalNormalizationEngine:
    """
    Normalizes natural language user requests into structured AgentGoals.
    Distinguishes hard constraints from soft preferences without hallucinating missing data.
    """

    def normalize(self, user_request: str, goal_id: Optional[str] = None, priority: TaskPriority = TaskPriority.NORMAL) -> Tuple[AgentGoal, Optional[str]]:
        gid = goal_id or f"goal_{secrets.token_hex(4)}"
        text = user_request.strip()
        text_lower = text.lower()

        normalized_data: Dict[str, Any] = {}
        hard_constraints: List[str] = []
        soft_preferences: List[str] = []
        success_criteria: List[SuccessCriterion] = []
        forbidden_actions: List[str] = []

        # Simple goal intent classification
        if "open " in text_lower or "navigate to " in text_lower or "go to " in text_lower:
            url_part = text.split(" ")[-1]
            if not url_part.startswith("http"):
                url_part = f"https://{url_part}" if "." in url_part else url_part
            normalized_data["intent_type"] = "NAVIGATE"
            normalized_data["target_url"] = url_part
            hard_constraints.append(f"url={url_part}")
            success_criteria.append(SuccessCriterion(
                criterion_id=f"crit_{secrets.token_hex(3)}",
                description=f"Browser navigated to {url_part}",
                evaluation_type="URL_MATCH",
                expected_value=url_part
            ))
        elif "flight" in text_lower or "book" in text_lower:
            normalized_data["intent_type"] = "BOOKING"
            # Look for flight specifics
            if "from " in text_lower and "to " in text_lower:
                try:
                    origin = text_lower.split("from ")[1].split(" to ")[0].strip()
                    dest = text_lower.split(" to ")[1].split(" ")[0].strip()
                    normalized_data["origin"] = origin
                    normalized_data["destination"] = dest
                    hard_constraints.append(f"origin={origin}")
                    hard_constraints.append(f"destination={dest}")
                except Exception:
                    pass
            success_criteria.append(SuccessCriterion(
                criterion_id=f"crit_{secrets.token_hex(3)}",
                description="Booking confirmation reached",
                evaluation_type="TEXT_PRESENT",
                expected_value="Confirmation"
            ))
        elif "search" in text_lower or "find" in text_lower:
            normalized_data["intent_type"] = "SEARCH"
            # Extract query terms
            parts = text.split("for ") if "for " in text else text.split("search ")
            query = parts[-1].strip() if len(parts) > 1 else text
            normalized_data["search_query"] = query
            hard_constraints.append(f"query={query}")
            success_criteria.append(SuccessCriterion(
                criterion_id=f"crit_{secrets.token_hex(3)}",
                description="Search results displayed",
                evaluation_type="TEXT_PRESENT",
                expected_value=query
            ))
        else:
            normalized_data["intent_type"] = "GENERAL_INTERACTION"
            normalized_data["raw_instruction"] = text
            success_criteria.append(SuccessCriterion(
                criterion_id=f"crit_{secrets.token_hex(3)}",
                description="Goal instruction executed and verified",
                evaluation_type="VERIFICATION_PASSED"
            ))

        # Check soft preferences
        if "cheapest" in text_lower or "lowest price" in text_lower:
            soft_preferences.append("prefer_cheapest_option")
        if "fastest" in text_lower or "non-stop" in text_lower:
            soft_preferences.append("prefer_fastest_route")

        # Check for missing critical parameters in flight booking
        clarification_msg = None
        if normalized_data.get("intent_type") == "BOOKING":
            if not normalized_data.get("destination"):
                clarification_msg = "Please specify your destination."
            elif not normalized_data.get("origin"):
                clarification_msg = "Please specify your departure city/origin."

        goal = AgentGoal(
            goal_id=gid,
            user_request=text,
            normalized_goal=normalized_data,
            hard_constraints=hard_constraints,
            soft_preferences=soft_preferences,
            success_criteria=success_criteria,
            forbidden_actions=forbidden_actions,
            confirmation_policy="HIGH_IMPACT_ONLY",
            priority=priority,
            created_at=datetime.now(timezone.utc).isoformat()
        )

        return goal, clarification_msg

class RelevantWorldState:
    """
    Filters raw World Model into a compressed context for token efficiency.
    Excludes footers, copyright, and irrelevant navigation links.
    """

    @staticmethod
    def extract_summary(
        world: Optional[BrowserWorldModel] = None,
        state_store: Optional[BrowserStateStore] = None,
        target_tab_id: Optional[int] = None
    ) -> Dict[str, Any]:
        store = state_store or browser_state_store
        active_tab = target_tab_id or (world.active_tab_id if world else store.active_tab_id) or 1

        page = world.page_states.get(active_tab) if (world and active_tab in world.page_states) else store.page_states.get(active_tab)
        elements = world.elements.get(active_tab, []) if (world and active_tab in world.elements) else store.world_elements.get(active_tab, [])

        if not page and not elements:
            return {"status": "EMPTY_WORLD"}

        # Filter to only interactive / visible elements
        relevant_els = [
            {
                "id": el.element_ref.element_id,
                "role": el.role,
                "name": el.name[:80],
                "visible": el.visible,
                "enabled": el.enabled
            }
            for el in elements
            if el.visible and el.role in ["button", "link", "textbox", "searchbox", "checkbox", "radio", "combobox", "tab"]
        ][:40]

        return {
            "tab_id": active_tab,
            "url": page.url if page else "",
            "title": page.title if page else "",
            "page_version": page.page_version if page else 1,
            "has_dialogs": len(page.active_dialogs) > 0 if page else False,
            "interactive_elements_count": len(relevant_els),
            "elements": relevant_els
        }

class PlannerContext:
    """
    Context package passed to the Planner on every cycle.
    """

    def __init__(
        self,
        goal: AgentGoal,
        task: AgentTask,
        world_summary: Dict[str, Any],
        recent_actions: List[Dict[str, Any]],
        recent_verifications: List[Dict[str, Any]],
        failure_history: List[str]
    ):
        self.goal = goal
        self.task = task
        self.world_summary = world_summary
        self.recent_actions = recent_actions
        self.recent_verifications = recent_verifications
        self.failure_history = failure_history

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": {
                "id": self.goal.goal_id,
                "request": self.goal.user_request,
                "hard_constraints": self.goal.hard_constraints,
                "soft_preferences": self.goal.soft_preferences,
                "success_criteria": [c.model_dump() for c in self.goal.success_criteria]
            },
            "task_state": self.task.state.value,
            "iteration": self.task.iteration_count,
            "progress": self.task.progress.model_dump(),
            "world": self.world_summary,
            "recent_actions": self.recent_actions[-3:],
            "recent_verifications": self.recent_verifications[-3:],
            "failure_history": self.failure_history[-5:]
        }

class StuckDetector:
    """
    Detects action loop oscillation (A -> B -> A -> B), consecutive identical actions,
    and stagnant task progress.
    """

    def __init__(self):
        self.action_history: List[str] = []
        self.failure_history: List[str] = []

    def record_action(self, action_signature: str):
        self.action_history.append(action_signature)

    def record_failure(self, failure_signature: str):
        self.failure_history.append(failure_signature)

    def is_stuck(self) -> Tuple[bool, Optional[str]]:
        # 1. Check identical action repeated 3+ times
        if len(self.action_history) >= 3 and len(set(self.action_history[-3:])) == 1:
            return True, f"Action loop detected: '{self.action_history[-1]}' repeated 3 times"

        # 2. Check 2-step oscillation (A -> B -> A -> B)
        if len(self.action_history) >= 4:
            if self.action_history[-1] == self.action_history[-3] and self.action_history[-2] == self.action_history[-4]:
                return True, f"Plan oscillation detected between '{self.action_history[-2]}' and '{self.action_history[-1]}'"

        # 3. Check identical failure repeated 3+ times
        if len(self.failure_history) >= 3 and len(set(self.failure_history[-3:])) == 1:
            return True, f"Persistent repeated failure: '{self.failure_history[-1]}'"

        return False, None

class GoalCompletionEngine:
    """
    Evaluates whether an AgentGoal has met all explicit SuccessCriteria.
    """

    def evaluate_completion(self, goal: AgentGoal, world: Optional[BrowserWorldModel], store: BrowserStateStore) -> bool:
        if not goal.success_criteria:
            return True

        tab_id = store.active_tab_id or 1
        page = store.page_states.get(tab_id)
        elements = store.world_elements.get(tab_id, [])

        all_satisfied = True
        for crit in goal.success_criteria:
            if crit.evaluation_type == "URL_MATCH":
                exp = str(crit.expected_value or "").lower()
                if page and exp in page.url.lower():
                    crit.is_satisfied = True
                    crit.evidence = f"URL '{page.url}' matched '{exp}'"
                else:
                    crit.is_satisfied = False
                    all_satisfied = False
            elif crit.evaluation_type == "TEXT_PRESENT":
                exp = str(crit.expected_value or "").lower()
                found = any(exp in el.name.lower() for el in elements) or (page and exp in page.title.lower())
                if found:
                    crit.is_satisfied = True
                    crit.evidence = f"Text '{exp}' found on page"
                else:
                    crit.is_satisfied = False
                    all_satisfied = False
            elif crit.evaluation_type == "ELEMENT_PRESENT":
                exp = str(crit.expected_value or "").lower()
                found = any(exp in el.name.lower() or exp in el.role.lower() for el in elements)
                if found:
                    crit.is_satisfied = True
                    crit.evidence = f"Element '{exp}' found"
                else:
                    crit.is_satisfied = False
                    all_satisfied = False
            else:
                crit.is_satisfied = True

        return all_satisfied

class ReplanningEngine:
    """
    Creates updated AgentPlans when triggered by world state shifts, failed actions,
    or user interruptions. Retains completed valid steps.
    """

    def create_replanned_plan(
        self,
        goal: AgentGoal,
        previous_plan: AgentPlan,
        world: Optional[BrowserWorldModel],
        failure_class: Optional[FailureClass] = None,
        reason: str = "World state changed"
    ) -> AgentPlan:
        new_version = previous_plan.version + 1
        new_plan_id = f"plan_{goal.goal_id}_v{new_version}"

        # Preserve already completed steps
        completed_steps = [s for s in previous_plan.steps if s.status == "COMPLETED"]

        # Generate fresh remaining steps
        remaining_steps: List[PlanStep] = []
        step_idx = len(completed_steps) + 1

        # Check goal requirements
        req = goal.user_request.lower()
        if "search" in req or "find" in req:
            query = goal.normalized_goal.get("search_query", "search")
            remaining_steps.append(PlanStep(
                step_id=f"step_{step_idx}",
                step_index=step_idx,
                description=f"Type search query '{query}'",
                objective=f"Enter '{query}' into searchbox",
                intended_action=ActionIntent(
                    action_id=f"act_{secrets.token_hex(4)}",
                    type=ActionType.TYPE,
                    target=ActionTarget(semantic_role="searchbox", expected_name="Search", tab_id=world.active_tab_id if world else 1),
                    parameters={"text": query, "press_enter": True}
                ),
                postconditions=[ActionPostcondition(type="TEXT_PRESENT", expected_value=query)]
            ))
        else:
            remaining_steps.append(PlanStep(
                step_id=f"step_{step_idx}",
                step_index=step_idx,
                description="Interact with active target",
                objective="Proceed toward goal",
                intended_action=ActionIntent(
                    action_id=f"act_{secrets.token_hex(4)}",
                    type=ActionType.CLICK,
                    target=ActionTarget(semantic_role="button", tab_id=world.active_tab_id if world else 1)
                )
            ))

        new_plan = AgentPlan(
            plan_id=new_plan_id,
            goal_id=goal.goal_id,
            version=new_version,
            steps=completed_steps + remaining_steps,
            assumptions=[TaskAssumption(assumption_id=f"asmp_{secrets.token_hex(3)}", statement=f"Re-anchored at version {new_version}")],
            success_criteria=goal.success_criteria,
            is_active=True
        )

        logger.info(f"[MATRIOSHAI][Replanner] Created plan v{new_version} for goal '{goal.goal_id}' ({reason})")
        return new_plan

class Planner:
    """
    Deterministic-First & LLM-Assisted Reactive Planner.
    Selects one immediate ActionIntent or PlanDecision based on current World Model.
    Never interacts with raw Chrome/DOM directly.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self.replanning_engine = ReplanningEngine()

    def create_plan(self, goal: AgentGoal, world: Optional[BrowserWorldModel]) -> AgentPlan:
        plan_id = f"plan_{goal.goal_id}_v1"
        steps: List[PlanStep] = []
        norm = goal.normalized_goal
        intent_type = norm.get("intent_type", "GENERAL_INTERACTION")
        tab_id = world.active_tab_id if world else (self.state_store.active_tab_id or 1)

        if intent_type == "NAVIGATE":
            url = norm.get("target_url", "https://example.com")
            steps.append(PlanStep(
                step_id="step_1",
                step_index=1,
                description=f"Navigate to {url}",
                objective=f"Open target URL {url}",
                intended_action=ActionIntent(
                    action_id=f"act_{secrets.token_hex(4)}",
                    type=ActionType.NAVIGATE,
                    target=ActionTarget(tab_id=tab_id),
                    parameters={"url": url}
                ),
                postconditions=[ActionPostcondition(type="URL_MATCH", expected_value=url)]
            ))
        elif intent_type == "SEARCH":
            query = norm.get("search_query", "")
            steps.append(PlanStep(
                step_id="step_1",
                step_index=1,
                description="Focus search box and type query",
                objective="Input query",
                intended_action=ActionIntent(
                    action_id=f"act_{secrets.token_hex(4)}",
                    type=ActionType.TYPE,
                    target=ActionTarget(semantic_role="searchbox", expected_name="Search", tab_id=tab_id),
                    parameters={"text": query, "press_enter": True}
                ),
                postconditions=[ActionPostcondition(type="TEXT_PRESENT", expected_value=query)]
            ))
        else:
            steps.append(PlanStep(
                step_id="step_1",
                step_index=1,
                description="Perform primary action",
                objective="Execute user instruction",
                intended_action=ActionIntent(
                    action_id=f"act_{secrets.token_hex(4)}",
                    type=ActionType.CLICK,
                    target=ActionTarget(semantic_role="button", expected_name="Submit", tab_id=tab_id)
                )
            ))

        return AgentPlan(
            plan_id=plan_id,
            goal_id=goal.goal_id,
            version=1,
            steps=steps,
            assumptions=[TaskAssumption(assumption_id=f"asmp_{secrets.token_hex(3)}", statement="Initial plan based on user goal")],
            success_criteria=goal.success_criteria,
            is_active=True
        )

    def select_next_step(self, plan: AgentPlan, world: Optional[BrowserWorldModel]) -> PlanDecision:
        # Check remaining pending steps
        pending_steps = [s for s in plan.steps if s.status == "PENDING"]
        if not pending_steps:
            return PlanDecision(
                decision=PlanDecisionType.COMPLETE,
                reason="All plan steps have been completed",
                confidence="HIGH"
            )

        step = pending_steps[0]

        # Deterministic check: if navigation is already at target, skip step
        if step.intended_action and step.intended_action.type == ActionType.NAVIGATE:
            target_url = step.intended_action.parameters.get("url", "")
            tab_id = step.intended_action.target.tab_id if step.intended_action.target else (world.active_tab_id if world else 1)
            page = self.state_store.page_states.get(tab_id)
            if page and target_url and target_url.lower() in page.url.lower():
                step.status = "COMPLETED"
                return self.select_next_step(plan, world)

        # Check for High-Impact Commit Boundary
        if step.intended_action and step.intended_action.target:
            target_name = (step.intended_action.target.expected_name or "").lower()
            if any(hi in target_name for hi in ["pay", "purchase", "buy now", "confirm booking", "delete account", "submit payment"]):
                step.risk_level = "CRITICAL"
                return PlanDecision(
                    decision=PlanDecisionType.ASK_USER,
                    selected_step=step,
                    intended_action=step.intended_action,
                    reason="Commit boundary reached: High-impact financial/destructive action requires explicit confirmation",
                    question_for_user=f"Ready to proceed with '{step.description}'. Do you confirm this action?",
                    clarification_options=["Confirm & Proceed", "Cancel Task"],
                    confidence="HIGH"
                )

        return PlanDecision(
            decision=PlanDecisionType.EXECUTE_ACTION,
            selected_step=step,
            intended_action=step.intended_action,
            reason=f"Selected step {step.step_index}: {step.description}",
            confidence="HIGH"
        )

class AgentExecutionLoop:
    """
    Bounded, Observable Closed-Loop Execution Loop (Phase 10).
    Coordinates Goal Understanding -> Planning -> Validation -> Safe Action -> Verification -> Reconciliation -> Replanning.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self.normalizer = GoalNormalizationEngine()
        self.planner = Planner(self.state_store)
        self.replanner = ReplanningEngine()
        self.completion_engine = GoalCompletionEngine()
        self.stuck_detector = StuckDetector()

    def _emit_event(self, task_id: str, event_type: str, payload: Dict[str, Any]):
        evt = AgentEvent(
            event_id=f"evt_{secrets.token_hex(4)}",
            task_id=task_id,
            event_type=event_type,
            payload=payload,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        self.state_store.agent_events.append(evt)
        if len(self.state_store.agent_events) > self.state_store.MAX_AGENT_EVENTS:
            self.state_store.agent_events.pop(0)
        logger.info(f"[MATRIOSHAI][AgentLoop] Event: {event_type} (task={task_id})")

    def create_task(self, user_request: str, priority: TaskPriority = TaskPriority.NORMAL) -> AgentTask:
        goal, clarification = self.normalizer.normalize(user_request, priority=priority)
        task_id = f"task_{secrets.token_hex(4)}"

        task = AgentTask(
            task_id=task_id,
            goal=goal,
            state=AgentTaskState.WAITING_FOR_USER if clarification else AgentTaskState.CREATED,
            active_tab_id=self.state_store.active_tab_id or 1,
            tab_contexts={
                (self.state_store.active_tab_id or 1): TaskTabContext(
                    tab_id=self.state_store.active_tab_id or 1,
                    role=TabRole.PRIMARY,
                    purpose="Main goal execution tab"
                )
            }
        )

        self.state_store.agent_tasks[task_id] = task
        self._emit_event(task_id, "agent.goal.created", {"user_request": user_request, "goal_id": goal.goal_id})
        self._emit_event(task_id, "agent.goal.normalized", {"normalized": goal.normalized_goal})

        if clarification:
            self._emit_event(task_id, "agent.waiting_for_user", {"clarification_required": clarification})

        return task

    async def run_task_loop(self, task_id: str, max_iterations: int = 30) -> AgentResult:
        start_time = time.time()
        task = self.state_store.agent_tasks.get(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found")

        task.state = AgentTaskState.PLANNING
        self._emit_event(task_id, "agent.planning.started", {})

        # 1. Initial Plan Creation
        current_world = self.state_store.current_world
        plan = self.planner.create_plan(task.goal, current_world)
        task.current_plan = plan
        task.plans.append(plan)
        self._emit_event(task_id, "agent.plan.created", {"plan_id": plan.plan_id, "steps_count": len(plan.steps)})

        task.state = AgentTaskState.READY

        # 2. Main Closed Loop
        while task.iteration_count < max_iterations:
            task.iteration_count += 1
            logger.info(f"[MATRIOSHAI][AgentLoop] Task {task_id} iteration {task.iteration_count}/{max_iterations}")

            # Check if task was paused or aborted externally
            if task.state in [AgentTaskState.PAUSED, AgentTaskState.ABORTED, AgentTaskState.WAITING_FOR_USER]:
                logger.info(f"[MATRIOSHAI][AgentLoop] Task {task_id} paused/waiting in state {task.state.value}")
                break

            # A. Select Next Step
            decision = self.planner.select_next_step(task.current_plan, self.state_store.current_world)

            if decision.decision == PlanDecisionType.COMPLETE:
                # Assess Goal Completion
                is_goal_met = self.completion_engine.evaluate_completion(task.goal, self.state_store.current_world, self.state_store)
                if is_goal_met:
                    task.state = AgentTaskState.COMPLETED
                    self._emit_event(task_id, "agent.task.completed", {"summary": "Goal satisfied cleanly"})
                    break
                else:
                    # Replan if goal not genuinely complete
                    new_plan = self.replanner.create_replanned_plan(task.goal, task.current_plan, self.state_store.current_world, reason="Goal criteria unfulfilled")
                    task.current_plan = new_plan
                    task.plans.append(new_plan)
                    continue

            if decision.decision == PlanDecisionType.ASK_USER:
                task.state = AgentTaskState.WAITING_FOR_USER
                self._emit_event(task_id, "agent.waiting_for_user", {
                    "question": decision.question_for_user,
                    "options": decision.clarification_options
                })
                break

            if decision.decision == PlanDecisionType.ABORT:
                task.state = AgentTaskState.ABORTED
                self._emit_event(task_id, "agent.task.aborted", {"reason": decision.reason})
                break

            # B. Execute Selected Action via Phase 8 & Verify via Phase 9
            if decision.decision == PlanDecisionType.EXECUTE_ACTION and decision.intended_action:
                step = decision.selected_step
                if step:
                    step.status = "EXECUTING"

                intent = decision.intended_action
                self._emit_event(task_id, "agent.action.selected", {"action_id": intent.action_id, "type": intent.type.value})

                # Stuck detection check
                stuck_sig = f"{intent.type.value}:{intent.target.expected_name if intent.target else ''}"
                self.stuck_detector.record_action(stuck_sig)
                is_stuck, stuck_reason = self.stuck_detector.is_stuck()
                if is_stuck:
                    logger.warning(f"[MATRIOSHAI][AgentLoop] Stuck detected: {stuck_reason}")
                    task.state = AgentTaskState.REPLANNING
                    self._emit_event(task_id, "agent.replanning.started", {"reason": stuck_reason})
                    new_plan = self.replanner.create_replanned_plan(task.goal, task.current_plan, self.state_store.current_world, reason=stuck_reason or "")
                    task.current_plan = new_plan
                    task.plans.append(new_plan)
                    continue

                # Execute & Verify
                task.state = AgentTaskState.EXECUTING
                self._emit_event(task_id, "agent.action.executing", {"action_id": intent.action_id})

                snap_before = world_model_engine.create_snapshot(reason=f"pre_action_{intent.action_id}")
                action_res = await action_engine.execute_action(intent, state_store=self.state_store)
                snap_after = world_model_engine.create_snapshot(reason=f"post_action_{intent.action_id}")
                ver_res = await verification_engine.verify_action(
                    action_result=action_res,
                    before_snapshot=snap_before,
                    after_snapshot=snap_after
                )
                task.memory.executed_action_ids.append(action_res.action_id)

                if ver_res.status == VerificationStatus.VERIFIED_SUCCESS:
                    task.state = AgentTaskState.VERIFYING
                    self._emit_event(task_id, "agent.action.verified", {"verification_id": ver_res.verification_id})
                    if step:
                        step.status = "COMPLETED"
                        task.memory.completed_step_ids.append(step.step_id)
                else:
                    self._emit_event(task_id, "agent.action.failed", {
                        "action_id": intent.action_id,
                        "failure_class": ver_res.failure_class.value if ver_res.failure_class else "UNKNOWN"
                    })
                    if step:
                        step.status = "FAILED"
                        task.memory.failed_step_ids.append(step.step_id)

                    # Dynamic Replanning on Failure
                    task.state = AgentTaskState.REPLANNING
                    self._emit_event(task_id, "agent.replanning.started", {"failure_class": ver_res.failure_class.value if ver_res.failure_class else ""})
                    new_plan = self.replanner.create_replanned_plan(
                        goal=task.goal,
                        previous_plan=task.current_plan,
                        world=self.state_store.current_world,
                        failure_class=ver_res.failure_class,
                        reason=f"Verification status: {ver_res.status.value}"
                    )
                    task.current_plan = new_plan
                    task.plans.append(new_plan)

        # 3. Handle loop termination
        if task.iteration_count >= max_iterations and task.state not in [AgentTaskState.COMPLETED, AgentTaskState.WAITING_FOR_USER]:
            task.state = AgentTaskState.FAILED
            self._emit_event(task_id, "agent.task.failed", {"reason": "TASK_COMPLEXITY_LIMIT_REACHED"})

        dur_ms = round((time.time() - start_time) * 1000, 2)
        res = AgentResult(
            task_id=task_id,
            goal_id=task.goal.goal_id,
            status=task.state,
            summary=f"Task {task_id} concluded in state {task.state.value}",
            completed_objectives=task.memory.completed_step_ids,
            remaining_objectives=[s.step_id for s in task.current_plan.steps if s.status != "COMPLETED"] if task.current_plan else [],
            actions_executed=len(task.memory.executed_action_ids),
            recoveries_attempted=len(self.state_store.recovery_traces),
            user_interventions_count=len(self.state_store.user_interventions),
            final_world_version=self.state_store.world_model_version,
            duration_ms=dur_ms,
            evidence=[]
        )
        task.result = res
        return res

    def pause_task(self, task_id: str) -> Optional[AgentTask]:
        task = self.state_store.agent_tasks.get(task_id)
        if task:
            task.state = AgentTaskState.PAUSED
            self._emit_event(task_id, "agent.task.paused", {})
        return task

    async def resume_task(self, task_id: str) -> AgentResult:
        task = self.state_store.agent_tasks.get(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found")

        task.state = AgentTaskState.READY
        self._emit_event(task_id, "agent.task.resumed", {})
        return await self.run_task_loop(task_id)

    def abort_task(self, task_id: str) -> Optional[AgentTask]:
        task = self.state_store.agent_tasks.get(task_id)
        if task:
            task.state = AgentTaskState.ABORTED
            self._emit_event(task_id, "agent.task.aborted", {})
        return task

agent_execution_loop = AgentExecutionLoop()
