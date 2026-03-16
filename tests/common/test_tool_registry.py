from mcp_common.config import ToolSettings
from mcp_common.tool_registry import ToolSpec, should_enable_tool


def test_tool_allowlist_has_highest_precedence() -> None:
    spec = ToolSpec("alpha", frozenset({"read"}), lambda _: None)
    settings = ToolSettings(enabled_tools={"beta"})
    assert should_enable_tool(spec, settings) is False


def test_tool_group_disable_applies() -> None:
    spec = ToolSpec("alpha", frozenset({"mutate"}), lambda _: None)
    settings = ToolSettings(disabled_tool_groups={"mutate"})
    assert should_enable_tool(spec, settings) is False


def test_tool_name_disable_applies() -> None:
    spec = ToolSpec("alpha", frozenset({"read"}), lambda _: None)
    settings = ToolSettings(disabled_tools={"alpha"})
    assert should_enable_tool(spec, settings) is False

