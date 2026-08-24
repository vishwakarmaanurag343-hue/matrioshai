from typing import Dict, Any, Optional
from app.context.models import TokenBudgetReport

class TokenBudgetManager:
    """
    Token Budget and Cost Manager:
    - Tracks context tokens, tool tokens, prompt input, and completion tokens.
    - Prevents uncontrolled context growth while preserving required files.
    - Estimates token reduction rate to evaluate compression efficiency.
    """

    def __init__(self):
        self._reports: Dict[str, TokenBudgetReport] = {}

    def record_task_budget(
        self,
        task_id: str,
        raw_context_tokens: int,
        optimized_context_tokens: int,
        tool_tokens: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0
    ) -> TokenBudgetReport:
        reduction = 0.0
        if raw_context_tokens > 0:
            reduction = max(0.0, (raw_context_tokens - optimized_context_tokens) / raw_context_tokens) * 100.0

        total = optimized_context_tokens + tool_tokens + input_tokens + output_tokens

        report = TokenBudgetReport(
            task_id=task_id,
            context_tokens=optimized_context_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            tool_tokens=tool_tokens,
            total_task_tokens=total,
            reduction_percentage=round(reduction, 1),
            estimated_cost_usd=round((total / 1000) * 0.003, 5)  # approximate blended token rate
        )
        self._reports[task_id] = report
        return report

    def get_report(self, task_id: str) -> Optional[TokenBudgetReport]:
        return self._reports.get(task_id)

token_budget_manager = TokenBudgetManager()
