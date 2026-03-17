import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from mcp.types import ToolAnnotations

from mcp_common.config import ToolSettings

logger = logging.getLogger(__name__)

class SupportsToolRegistration(Protocol):
    def tool(
        self,
        name_or_fn: Callable[..., Awaitable[str]],
        *,
        name: str,
        tags: set[str] | None = None,
        annotations: ToolAnnotations | None = None,
    ) -> Callable[..., Awaitable[str]]: ...


@dataclass(frozen=True)
class ToolSpec:
    name: str
    groups: frozenset[str]
    tags: frozenset[str]
    annotations: ToolAnnotations
    register: Callable[[SupportsToolRegistration], None]


def build_tool_tags(name: str, groups: frozenset[str]) -> frozenset[str]:
    tags = set(groups)
    if "read" in groups:
        tags.add("read-only")
    if "mutate" in groups:
        tags.add("write")
    if "destructive" in groups:
        tags.add("destructive")
    if "open-world" in groups:
        tags.add("open-world")
    if "closed-world" in groups:
        tags.add("closed-world")
    if name.startswith("navidrome_") or name.startswith("slskd_"):
        tags.add("remote-service")
        tags.add("open-world")
    elif name in {
        "read_file",
        "read_multiple_files",
        "list_directory",
        "create_directory",
        "tree",
        "list_allowed_directories",
        "get_file_info",
        "search_files",
        "search_within_files",
        "write_file",
        "copy_file",
        "move_file",
        "delete_file",
        "modify_file",
        "patch_file",
    }:
        tags.add("local-filesystem")
        tags.add("closed-world")
    return frozenset(tags)


def build_tool_annotations(name: str, groups: frozenset[str]) -> ToolAnnotations:
    read_only = "read" in groups and "mutate" not in groups
    destructive = "destructive" in groups or name in {
        "delete_file",
        "navidrome_delete_playlist",
        "slskd_delete_search",
        "slskd_cancel_search",
        "slskd_cancel_download",
        "slskd_clear_completed_downloads",
    }
    open_world = "open-world" in groups or name.startswith(("navidrome_", "slskd_"))
    idempotent = read_only or name in {
        "create_directory",
        "write_file",
        "modify_file",
        "patch_file",
        "navidrome_rate",
        "navidrome_like",
        "navidrome_unlike",
    }
    return ToolAnnotations(
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )


def should_enable_tool(spec: ToolSpec, settings: ToolSettings) -> bool:
    if settings.enabled_tools is not None and spec.name not in settings.enabled_tools:
        return False
    if spec.groups & settings.disabled_tool_groups:
        return False
    return spec.name not in settings.disabled_tools


def register_enabled_tools(
    mcp: SupportsToolRegistration,
    specs: Iterable[ToolSpec],
    settings: ToolSettings,
) -> None:
    enabled: list[str] = []
    disabled: list[str] = []
    for spec in specs:
        if should_enable_tool(spec, settings):
            spec.register(mcp)
            enabled.append(spec.name)
        else:
            disabled.append(spec.name)
    logger.info("Enabled tools: %s", ", ".join(enabled) if enabled else "(none)")
    logger.info("Disabled tools: %s", ", ".join(disabled) if disabled else "(none)")
