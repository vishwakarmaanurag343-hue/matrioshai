from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from pydantic import BaseModel, Field
from app.security.audit import audit_logger

class PermissionLevel(str, Enum):
    READ = "READ"                          # Read-only operations on local data
    WRITE = "WRITE"                        # Local storage / note modifications
    EXTERNAL_ACTION = "EXTERNAL_ACTION"    # Outbound communications, API calls
    DESTRUCTIVE = "DESTRUCTIVE"            # File deletions, terminal commands, database drops

class AutonomyTier(str, Enum):
    TIER_1 = "TIER_1"  # Autonomous: read memory, search notes, summarize, classify
    TIER_2 = "TIER_2"  # Confirmation Required: send email/message, modify external data, commit code
    TIER_3 = "TIER_3"  # Human Completion Required / Prohibited: destructive terminal, financial, credentials

class ToolDefinition(BaseModel):
    name: str
    description: str
    permission_level: PermissionLevel
    autonomy_tier: AutonomyTier
    requires_confirmation: bool = False
    accesses_private_data: bool = False
    causes_side_effects: bool = False

class ToolRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    actor: str = "llm"
    context: Optional[Dict[str, Any]] = None

class PermissionDecision(BaseModel):
    allowed: bool
    requires_confirmation: bool
    autonomy_tier: AutonomyTier
    reason: str
    risk_level: str

class ToolRegistry:
    """Central registry of registered tools with permission policies."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def evaluate_request(self, request: ToolRequest) -> PermissionDecision:
        """Evaluates whether a tool request is allowed, requires confirmation, or is blocked."""
        tool = self.get_tool(request.tool_name)
        if not tool:
            audit_logger.log_event(
                event_type="PERMISSION_CHECK",
                action=f"execute_tool:{request.tool_name}",
                decision="BLOCKED",
                reason=f"Tool '{request.tool_name}' is not registered in ToolRegistry"
            )
            return PermissionDecision(
                allowed=False,
                requires_confirmation=False,
                autonomy_tier=AutonomyTier.TIER_3,
                reason=f"Unknown tool '{request.tool_name}'",
                risk_level="HIGH"
            )

        # Tier 3 actions: Prohibited from autonomous execution
        if tool.autonomy_tier == AutonomyTier.TIER_3 or tool.permission_level == PermissionLevel.DESTRUCTIVE:
            audit_logger.log_event(
                event_type="PERMISSION_CHECK",
                action=f"execute_tool:{tool.name}",
                resource=tool.name,
                decision="BLOCKED",
                reason="Tier 3 / Destructive operation cannot be executed autonomously"
            )
            return PermissionDecision(
                allowed=False,
                requires_confirmation=False,
                autonomy_tier=AutonomyTier.TIER_3,
                reason=f"Action '{tool.name}' is classified as Tier 3 (Human-only / Restricted)",
                risk_level="CRITICAL"
            )

        # Tier 2 actions: Require explicit user confirmation
        if tool.autonomy_tier == AutonomyTier.TIER_2 or tool.requires_confirmation:
            audit_logger.log_event(
                event_type="PERMISSION_CHECK",
                action=f"execute_tool:{tool.name}",
                resource=tool.name,
                decision="CONFIRMATION_REQUIRED",
                reason="Tier 2 operation requires explicit user approval"
            )
            return PermissionDecision(
                allowed=True,
                requires_confirmation=True,
                autonomy_tier=AutonomyTier.TIER_2,
                reason=f"Action '{tool.name}' requires user confirmation before execution",
                risk_level="MEDIUM"
            )

        # Tier 1 actions: Autonomous read/search
        audit_logger.log_event(
            event_type="PERMISSION_CHECK",
            action=f"execute_tool:{tool.name}",
            resource=tool.name,
            decision="ALLOWED",
            reason="Tier 1 autonomous read operation approved"
        )
        return PermissionDecision(
            allowed=True,
            requires_confirmation=False,
            autonomy_tier=AutonomyTier.TIER_1,
            reason=f"Action '{tool.name}' is authorized for autonomous execution",
            risk_level="LOW"
        )

tool_registry = ToolRegistry()

# Register core baseline tool definitions
tool_registry.register_tool(ToolDefinition(
    name="search_notes",
    description="Search local markdown notes repository",
    permission_level=PermissionLevel.READ,
    autonomy_tier=AutonomyTier.TIER_1,
    requires_confirmation=False,
    accesses_private_data=True
))
tool_registry.register_tool(ToolDefinition(
    name="read_memory",
    description="Query recall and archival memory items",
    permission_level=PermissionLevel.READ,
    autonomy_tier=AutonomyTier.TIER_1,
    requires_confirmation=False,
    accesses_private_data=True
))
tool_registry.register_tool(ToolDefinition(
    name="send_external_message",
    description="Send message or email to external recipient",
    permission_level=PermissionLevel.EXTERNAL_ACTION,
    autonomy_tier=AutonomyTier.TIER_2,
    requires_confirmation=True,
    causes_side_effects=True
))
tool_registry.register_tool(ToolDefinition(
    name="delete_all_files",
    description="Destructive file removal operation",
    permission_level=PermissionLevel.DESTRUCTIVE,
    autonomy_tier=AutonomyTier.TIER_3,
    requires_confirmation=True,
    causes_side_effects=True
))

# Register Phase 4 Developer Intelligence tools
tool_registry.register_tool(ToolDefinition(
    name="read_file",
    description="Read file content safely within active workspace",
    permission_level=PermissionLevel.READ,
    autonomy_tier=AutonomyTier.TIER_1,
    requires_confirmation=False,
    accesses_private_data=True
))
tool_registry.register_tool(ToolDefinition(
    name="search_code",
    description="Search text and symbols in active workspace",
    permission_level=PermissionLevel.READ,
    autonomy_tier=AutonomyTier.TIER_1,
    requires_confirmation=False,
    accesses_private_data=True
))
tool_registry.register_tool(ToolDefinition(
    name="git_status",
    description="Inspect git working tree status",
    permission_level=PermissionLevel.READ,
    autonomy_tier=AutonomyTier.TIER_1,
    requires_confirmation=False,
    accesses_private_data=False
))
tool_registry.register_tool(ToolDefinition(
    name="git_diff",
    description="Inspect git diff with secret redaction",
    permission_level=PermissionLevel.READ,
    autonomy_tier=AutonomyTier.TIER_1,
    requires_confirmation=False,
    accesses_private_data=True
))
tool_registry.register_tool(ToolDefinition(
    name="write_file",
    description="Direct write to workspace source file",
    permission_level=PermissionLevel.WRITE,
    autonomy_tier=AutonomyTier.TIER_2,
    requires_confirmation=True,
    causes_side_effects=True
))
tool_registry.register_tool(ToolDefinition(
    name="apply_patch",
    description="Apply approved unified diff proposal with rollback backup",
    permission_level=PermissionLevel.WRITE,
    autonomy_tier=AutonomyTier.TIER_2,
    requires_confirmation=True,
    causes_side_effects=True
))
tool_registry.register_tool(ToolDefinition(
    name="install_dependency",
    description="Install package dependencies (npm install, pip install, etc.)",
    permission_level=PermissionLevel.EXTERNAL_ACTION,
    autonomy_tier=AutonomyTier.TIER_2,
    requires_confirmation=True,
    causes_side_effects=True
))
tool_registry.register_tool(ToolDefinition(
    name="git_commit",
    description="Create git commit in workspace",
    permission_level=PermissionLevel.WRITE,
    autonomy_tier=AutonomyTier.TIER_2,
    requires_confirmation=True,
    causes_side_effects=True
))
tool_registry.register_tool(ToolDefinition(
    name="destructive_command",
    description="Destructive disk or repository removal",
    permission_level=PermissionLevel.DESTRUCTIVE,
    autonomy_tier=AutonomyTier.TIER_3,
    requires_confirmation=True,
    causes_side_effects=True
))
