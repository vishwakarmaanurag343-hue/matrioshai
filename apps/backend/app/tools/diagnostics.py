import json
from typing import Optional, List
from app.tools.models import DiagnosticResult
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.security.redaction import redaction_engine
from app.core.logging import logger

DIAGNOSTIC_SYSTEM_PROMPT = """
You are the MATRIOSHAI Developer Intelligence Diagnostic Specialist.
Your task is to analyze build errors, test failures, and exception stack traces, and provide a structured root-cause analysis.
DISTINGUISH CLEARLY:
- OBSERVED (Direct facts in the error output)
- INFERRED (Likely root cause based on technical mechanisms)
- HYPOTHESIS (Potential underlying issues to investigate)

You MUST respond strictly in valid raw JSON matching this format:
{
  "error_summary": "Concise summary of the core error",
  "likely_causes": ["Cause 1", "Cause 2"],
  "evidence": ["Observed evidence in log 1", "Observed evidence in log 2"],
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "recommended_actions": ["Action 1 to resolve", "Action 2 to resolve"],
  "suggested_files_to_inspect": ["path/to/file1.ts", "path/to/file2.py"]
}
DO NOT include markdown code blocks. Return ONLY raw JSON.
"""

class DiagnosticService:
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider or OllamaProvider()

    async def diagnose_error(self, error_log: str, command: Optional[str] = None) -> DiagnosticResult:
        # 1. Redact secrets from error log before sending to model
        sanitized_log, _ = redaction_engine.redact(error_log[:15000])

        user_content = f"COMMAND:\n{command or 'N/A'}\n\nERROR LOG / OUTPUT:\n{sanitized_log}\n\nPlease diagnose."
        messages = [
            {"role": "system", "content": DIAGNOSTIC_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        logger.info("Executing diagnostic error reasoning...")
        raw_res = await self.llm_provider.chat(messages=messages, temperature=0.1)

        try:
            clean = raw_res.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            parsed = json.loads(clean.strip())
            return DiagnosticResult(
                error_summary=parsed.get("error_summary", "Build or test failure"),
                likely_causes=parsed.get("likely_causes", []),
                evidence=parsed.get("evidence", []),
                confidence=parsed.get("confidence", "MEDIUM"),
                recommended_actions=parsed.get("recommended_actions", []),
                suggested_files_to_inspect=parsed.get("suggested_files_to_inspect", [])
            )
        except Exception:
            return DiagnosticResult(
                error_summary="Error analysis produced unstructured output",
                likely_causes=[raw_res[:200]] if raw_res else ["Unknown error"],
                evidence=["Log parsed"],
                confidence="LOW",
                recommended_actions=["Inspect recent code diffs manually"],
                suggested_files_to_inspect=[]
            )

diagnostic_service = DiagnosticService()
