from mcp.types import ToolAnnotations

from mcp_common.config import ToolSettings
from mcp_common.tool_registry import (
    ToolSpec,
    build_tool_annotations,
    build_tool_tags,
    should_enable_tool,
)


def make_spec(name: str, *groups: str) -> ToolSpec:
    group_set = frozenset(groups)
    return ToolSpec(
        name=name,
        groups=group_set,
        tags=build_tool_tags(name, group_set),
        annotations=build_tool_annotations(name, group_set),
        register=lambda _: None,
    )


def test_tool_allowlist_has_highest_precedence() -> None:
    spec = make_spec("alpha", "read")
    settings = ToolSettings(enabled_tools={"beta"})
    assert should_enable_tool(spec, settings) is False


def test_tool_group_disable_applies() -> None:
    spec = make_spec("alpha", "mutate")
    settings = ToolSettings(disabled_tool_groups={"mutate"})
    assert should_enable_tool(spec, settings) is False


def test_tool_name_disable_applies() -> None:
    spec = make_spec("alpha", "read")
    settings = ToolSettings(disabled_tools={"alpha"})
    assert should_enable_tool(spec, settings) is False


def test_build_tool_tags_marks_local_read_tool() -> None:
    tags = build_tool_tags("read_file", frozenset({"read"}))

    assert tags >= {"read", "read-only", "local-filesystem", "closed-world"}


def test_build_tool_annotations_marks_destructive_remote_tool() -> None:
    annotations = build_tool_annotations(
        "slskd_cancel_download",
        frozenset({"mutate", "downloads"}),
    )

    assert annotations == ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    )
