from app.security.permissions import tool_registry, ToolDefinition, PermissionLevel, AutonomyTier

def register_computer_tools():
    # 1. Perception tools (Tier 1 - Autonomous)
    tool_registry.register_tool(ToolDefinition(
        name="capture_screen",
        description="Capture full screen screenshot with metadata",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="capture_active_window",
        description="Capture active window screenshot",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="ocr_screen",
        description="Extract text and coordinates via OCR",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="analyze_screen",
        description="Analyze screen UI elements and layout",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="get_active_application",
        description="Get current frontmost application and window title",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        accesses_private_data=False
    ))

    # 2. Interactive Computer tools (Tier 2 - Confirmation Required)
    tool_registry.register_tool(ToolDefinition(
        name="open_application",
        description="Launch or switch to specified macOS application",
        permission_level=PermissionLevel.WRITE,
        autonomy_tier=AutonomyTier.TIER_2,
        requires_confirmation=True,
        causes_side_effects=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="focus_application",
        description="Bring application to front",
        permission_level=PermissionLevel.WRITE,
        autonomy_tier=AutonomyTier.TIER_2,
        requires_confirmation=True,
        causes_side_effects=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="move_mouse",
        description="Move mouse cursor to coordinates",
        permission_level=PermissionLevel.READ,
        autonomy_tier=AutonomyTier.TIER_1,
        requires_confirmation=False,
        causes_side_effects=False
    ))

    tool_registry.register_tool(ToolDefinition(
        name="click",
        description="Click mouse at specified coordinates",
        permission_level=PermissionLevel.WRITE,
        autonomy_tier=AutonomyTier.TIER_2,
        requires_confirmation=True,
        causes_side_effects=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="double_click",
        description="Double click mouse at coordinates",
        permission_level=PermissionLevel.WRITE,
        autonomy_tier=AutonomyTier.TIER_2,
        requires_confirmation=True,
        causes_side_effects=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="right_click",
        description="Right click mouse at coordinates",
        permission_level=PermissionLevel.WRITE,
        autonomy_tier=AutonomyTier.TIER_2,
        requires_confirmation=True,
        causes_side_effects=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="scroll",
        description="Scroll mouse wheel",
        permission_level=PermissionLevel.WRITE,
        autonomy_tier=AutonomyTier.TIER_2,
        requires_confirmation=True,
        causes_side_effects=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="type_text",
        description="Type text string into focused element",
        permission_level=PermissionLevel.WRITE,
        autonomy_tier=AutonomyTier.TIER_2,
        requires_confirmation=True,
        causes_side_effects=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="press_key",
        description="Press specific keyboard key",
        permission_level=PermissionLevel.WRITE,
        autonomy_tier=AutonomyTier.TIER_2,
        requires_confirmation=True,
        causes_side_effects=True
    ))

    tool_registry.register_tool(ToolDefinition(
        name="hotkey",
        description="Trigger key combination (e.g. CMD+C)",
        permission_level=PermissionLevel.WRITE,
        autonomy_tier=AutonomyTier.TIER_2,
        requires_confirmation=True,
        causes_side_effects=True
    ))

# Execute registration on module import
register_computer_tools()
