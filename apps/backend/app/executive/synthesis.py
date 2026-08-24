import json
import re
from typing import Dict, Any, Optional, List
from app.executive.roles import ExecutiveRole
from app.executive.models import ExecutiveResponse, SynthesisResponse
from app.executive.prompts import SYNTHESIS_SYSTEM_PROMPT
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.core.logging import logger

class SynthesisEngine:
    """
    Cross-functional 5C Synthesis Engine.
    Takes the structured findings from all 5 executive roles, detects alignments,
    disagreements, critical risks, missing context, and synthesizes a unified recommendation.
    """

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider or OllamaProvider()

    def _extract_json_block(self, text: str) -> Optional[Dict[str, Any]]:
        clean_text = text.strip()
        try:
            return json.loads(clean_text)
        except Exception:
            pass

        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        start = clean_text.find('{')
        end = clean_text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(clean_text[start:end+1])
            except Exception:
                pass

        return None

    def _format_executive_inputs_for_prompt(
        self,
        assessments: Dict[ExecutiveRole, ExecutiveResponse]
    ) -> str:
        blocks = []
        for role, resp in assessments.items():
            block = (
                f"### {role.value} ({role.name}) ASSESSMENT:\n"
                f"- Summary: {resp.summary}\n"
                f"- Key Findings: {', '.join(resp.key_findings) if resp.key_findings else 'None'}\n"
                f"- Assumptions: {', '.join(resp.assumptions) if resp.assumptions else 'None'}\n"
                f"- Risks: {', '.join(resp.risks) if resp.risks else 'None'}\n"
                f"- Recommendations: {', '.join(resp.recommendations) if resp.recommendations else 'None'}\n"
                f"- Confidence: {resp.confidence.value}\n"
                f"- Missing Info: {', '.join(resp.missing_information) if resp.missing_information else 'None'}\n"
            )
            blocks.append(block)
        return "\n".join(blocks)

    async def synthesize(
        self,
        question: str,
        assessments: Dict[ExecutiveRole, ExecutiveResponse]
    ) -> SynthesisResponse:
        logger.info("Synthesizing 5C cross-functional executive council analysis...")
        
        exec_context = self._format_executive_inputs_for_prompt(assessments)
        user_content = (
            f"DECISION QUESTION:\n{question}\n\n"
            f"EXECUTIVE ASSESSMENTS:\n{exec_context}\n\n"
            "Please analyze the cross-functional alignments, conflicts, critical risks, and synthesize a final recommendation."
        )

        messages = [
            {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        raw_response = await self.llm_provider.chat(messages=messages, temperature=0.2)
        parsed = self._extract_json_block(raw_response)

        if not parsed:
            logger.warning("Synthesis JSON parsing fallback triggered.")
            # Fallback programmatic disagreement extraction
            agreements = []
            conflicts = []
            risks = []
            for r, a in assessments.items():
                risks.extend(a.risks)
            
            return SynthesisResponse(
                question=question,
                summary="5C Council completed analysis with mixed perspectives.",
                agreements=["All executive roles reviewed the decision context."],
                conflicts=["Evaluation criteria differ across operational, technical, and financial domains."],
                critical_risks=list(set(risks))[:5],
                missing_information=["Integrated quantitative scenario modeling"],
                final_recommendation=raw_response[:350] if raw_response else "Review individual executive assessments.",
                next_actions=["Review CTO and COO operational requirements", "Validate CFO unit economics"],
                executive_assessments=assessments
            )

        return SynthesisResponse(
            question=question,
            summary=parsed.get("summary", "5C Council Synthesis completed."),
            agreements=parsed.get("agreements", []),
            conflicts=parsed.get("conflicts", []),
            critical_risks=parsed.get("critical_risks", []),
            missing_information=parsed.get("missing_information", []),
            final_recommendation=parsed.get("final_recommendation", "Proceed with validated milestones."),
            next_actions=parsed.get("next_actions", []),
            executive_assessments=assessments
        )
