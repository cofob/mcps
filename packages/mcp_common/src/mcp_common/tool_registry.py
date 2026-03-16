import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from mcp_common.config import ToolSettings

logger = logging.getLogger(__name__)

class SupportsToolRegistration(Protocol):
    def tool(
        self,
        name_or_fn: Callable[..., Awaitable[str]],
        *,
        name: str,
    ) -> Callable[..., Awaitable[str]]: ...


@dataclass(frozen=True)
class ToolSpec:
    name: str
    groups: frozenset[str]
    register: Callable[[SupportsToolRegistration], None]


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
