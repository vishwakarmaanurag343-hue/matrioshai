from app.security.permissions import tool_registry, ToolDefinition, PermissionLevel, AutonomyTier

def register_communication_tools():
    # 1. Read & Query tools (Tier 1 - Autonomous)
    tool_registry.register_tool(ToolDefinition(
        name="list_communication_providers",
        description="List registered communication providers and connection status",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=False
    ))

    tool_registry.register_tool(ToolDefinition(
        name="get_conversations",
        description="List conversations across enabled communication providers",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="get_messages",
        description="Fetch messages from specific conversation",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="search_messages",
        description="Search messages across enabled providers",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="get_unread_messages",
        description="Retrieve unread and likely unanswered messages",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="get_notifications",
        description="Retrieve pending application notifications",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="summarize_conversation",
        description="Summarize message thread and action items",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="generate_reply",
        description="Generate multiple styled reply suggestions",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="draft_message",
        description="Prepare a message draft without sending",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        causes_side_effects=False
    ))

    # 2. Modifying / External Sending tools (Tier 2 - Confirmation Required)
    tool_registry.register_tool(ToolDefinition(
        name="send_message",
        description="Send message to external recipient via provider",
        permission_level=PermissionLevel.EXTERNAL_ACTION,
        autonomy_tier=AutonomyTier.TIER_2,
        requires_confirmation=True,
        causes_side_effects=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="mark_message_read",
        description="Mark message as read on provider",
        permission_level=PermissionLevel.WRITE,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        causes_side_effects=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="delete_conversation",
        description="Destructive deletion of full conversation thread",
        permission_level=PermissionLevel.DESTRUCTIVE,
        autonomy_tier=AutonomyTier.TIER_3,
        requires_confirmation=True,
        causes_side_effects=True
    ))

register_communication_tools()
