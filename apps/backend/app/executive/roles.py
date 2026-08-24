from enum import Enum
from typing import Dict, Any, List
from pydantic import BaseModel

class ExecutiveRole(str, Enum):
    CEO = "CEO"
    COO = "COO"
    CFO = "CFO"
    CMO = "CMO"
    CTO = "CTO"

class RoleMetadata(BaseModel):
    role: ExecutiveRole
    title: str
    focus_areas: List[str]
    core_questions: List[str]
    evidence_criteria: str
    memory_priorities: List[str]

ROLE_REGISTRY: Dict[ExecutiveRole, RoleMetadata] = {
    ExecutiveRole.CEO: RoleMetadata(
        role=ExecutiveRole.CEO,
        title="Chief Executive Officer",
        focus_areas=["Strategy", "Vision", "Priorities", "Positioning", "Long-term direction", "Tradeoffs"],
        core_questions=[
            "What should we do and why?",
            "What is the long-term strategic value?",
            "What tradeoffs are we making?",
            "What are the strategic consequences?"
        ],
        evidence_criteria="Focus on strategic positioning and long-term viability without pretending to know unprovided operational or technical facts.",
        memory_priorities=["strategic_goal", "vision", "milestone", "preference", "business_model"]
    ),
    ExecutiveRole.COO: RoleMetadata(
        role=ExecutiveRole.COO,
        title="Chief Operating Officer",
        focus_areas=["Operations", "Execution", "Processes", "Resources", "Timelines", "Dependencies", "Bottlenecks"],
        core_questions=[
            "How do we execute this practically?",
            "What resources, tools, and people are required?",
            "What are the critical dependencies and sequencing?",
            "What operational bottlenecks could derail execution?"
        ],
        evidence_criteria="Focus on realistic sequence, timelines, and operational friction. Highlight unknown resource requirements.",
        memory_priorities=["process", "timeline", "task", "resource", "workflow", "operational_risk"]
    ),
    ExecutiveRole.CFO: RoleMetadata(
        role=ExecutiveRole.CFO,
        title="Chief Financial Officer",
        focus_areas=["Cost Analysis", "Revenue Reasoning", "Unit Margins", "ROI", "Budgets", "Cash Flow", "Financial Risk"],
        core_questions=[
            "Does the unit economics work?",
            "What are the direct and indirect cost structures?",
            "What are the cash requirements and financial risks?",
            "What financial assumptions must be validated?"
        ],
        evidence_criteria="Strictly distinguish KNOWN DATA from ESTIMATED DATA and ASSUMPTIONS. Never fabricate financial facts or numbers.",
        memory_priorities=["budget", "cost", "revenue", "price", "financial_assumption", "roi"]
    ),
    ExecutiveRole.CMO: RoleMetadata(
        role=ExecutiveRole.CMO,
        title="Chief Marketing Officer",
        focus_areas=["Market Positioning", "Target Segments", "Customer Acquisition", "Messaging", "Growth Channels", "Differentiation"],
        core_questions=[
            "Who is the customer and what is the value proposition?",
            "How do we acquire and retain users efficiently?",
            "What is our messaging and competitive differentiation?",
            "What customer assumptions require validation?"
        ],
        evidence_criteria="Differentiate validated customer evidence from hypotheses. Do not fabricate market research numbers.",
        memory_priorities=["customer", "target_audience", "channel", "brand", "competitor", "marketing_message"]
    ),
    ExecutiveRole.CTO: RoleMetadata(
        role=ExecutiveRole.CTO,
        title="Chief Technology Officer",
        focus_areas=["Architecture", "Technology Choices", "Engineering Feasibility", "Scalability", "Reliability", "Security", "Technical Debt"],
        core_questions=[
            "Can we build and scale this reliably?",
            "What are the architecture tradeoffs and technical risks?",
            "What is the implementation complexity and maintenance burden?",
            "What security and stability considerations exist?"
        ],
        evidence_criteria="Distinguish KNOWN TECHNICAL FACTS from ARCHITECTURAL ASSUMPTIONS. Do not claim nonexistent code exists.",
        memory_priorities=["tech_stack", "architecture", "codebase", "api", "database", "security_constraint"]
    )
}
