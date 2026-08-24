import json
import re
from typing import Dict, Any, Optional, List
from app.executive.roles import ExecutiveRole
from app.executive.models import ExecutiveResponse, ConfidenceLevel
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.core.logging import logger

class ExecutiveReasoningEngine:
    """
    Executes structured reasoning for an individual executive role.
    Invokes LLMProvider and parses structured JSON output.
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider or OllamaProvider()

    def _extract_json_block(self, text: str) -> Optional[Dict[str, Any]]:
        # Try direct JSON parse
        clean_text = text.strip()
        try:
            return json.loads(clean_text)
        except Exception:
            pass

        # Try finding markdown JSON block ```json ... ```
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Try finding outermost braces { ... }
        start = clean_text.find('{')
        end = clean_text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(clean_text[start:end+1])
            except Exception:
                pass

        return None

    async def analyze(
        self,
        role: ExecutiveRole,
        messages: List[Dict[str, str]]
    ) -> ExecutiveResponse:
        logger.info(f"Executing 5C analysis for role [{role.value}]...")
        raw_response = await self.llm_provider.chat(messages=messages, temperature=0.2)
        parsed = self._extract_json_block(raw_response)

        if not parsed:
            logger.warning(f"Failed to parse structured JSON from [{role.value}] response; formatting fallback.")
            return ExecutiveResponse(
                role=role,
                summary=raw_response[:300] if raw_response else "No analysis produced",
                key_findings=[raw_response] if raw_response else ["Insufficient data"],
                assumptions=["LLM response produced unstructured output"],
                risks=["Output formatting inconsistency"],
                recommendations=["Re-run executive analysis with clearer context"],
                confidence=ConfidenceLevel.LOW,
                confidence_reason="Unstructured output fallback",
                missing_information=["Structured JSON schema compliance"]
            )

        conf_str = parsed.get("confidence", "MEDIUM").upper()
        if conf_str not in ("HIGH", "MEDIUM", "LOW"):
            conf_str = "MEDIUM"

        return ExecutiveResponse(
            role=role,
            summary=parsed.get("summary", "Analysis completed."),
            key_findings=parsed.get("key_findings", []),
            assumptions=parsed.get("assumptions", []),
            risks=parsed.get("risks", []),
            recommendations=parsed.get("recommendations", []),
            confidence=ConfidenceLevel(conf_str),
            confidence_reason=parsed.get("confidence_reason"),
            missing_information=parsed.get("missing_information", [])
        )
