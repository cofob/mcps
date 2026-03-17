from collections.abc import Awaitable, Callable
from typing import cast

from fastmcp import FastMCP
from starlette.applications import Starlette

from mcp_common import (
    SupportsToolRegistration,
    ToolSpec,
    build_auth_provider,
    build_http_app,
    build_tool_annotations,
    build_tool_tags,
    register_enabled_tools,
)
from mcp_common.logging import configure_logging
from tg_export_txt_mcp import __version__
from tg_export_txt_mcp.config import TgExportTxtSettings
from tg_export_txt_mcp.service import TgExportTxtService
from tg_export_txt_mcp.tools import ReadTools, SearchTools


def _tool_spec(method: Callable[..., Awaitable[str]], name: str, *groups: str) -> ToolSpec:
    group_set = frozenset(groups)
    tags = build_tool_tags(name, group_set)
    annotations = build_tool_annotations(name, group_set)

    def register_tool(mcp: SupportsToolRegistration) -> None:
        mcp.tool(method, name=name, tags=set(tags), annotations=annotations)

    return ToolSpec(
        name=name,
        groups=group_set,
        tags=tags,
        annotations=annotations,
        register=register_tool,
    )


def _make_tool_specs(service: TgExportTxtService) -> list[ToolSpec]:
    read_tools = ReadTools(service)
    search_tools = SearchTools(service)
    return [
        _tool_spec(read_tools.read_export_file, "read_export_file", "read"),
        _tool_spec(search_tools.search_exports, "search_exports", "read", "search"),
    ]


def create_mcp(settings: TgExportTxtSettings) -> FastMCP:
    auth = build_auth_provider(settings.oauth2) if settings.mcp_auth_mode.value == "oauth2" else None
    mcp = FastMCP(name="tg-export-txt-mcp", auth=auth)
    service = TgExportTxtService(settings)
    register_enabled_tools(cast(SupportsToolRegistration, mcp), _make_tool_specs(service), settings.tools)
    return mcp


def create_app(settings: TgExportTxtSettings | None = None) -> Starlette:
    resolved = settings or TgExportTxtSettings.from_env()
    configure_logging(resolved.log_level)
    mcp = create_mcp(resolved)
    mcp_app = mcp.http_app(path="/mcp")
    return build_http_app(mcp_app, service_name="tg-export-txt-mcp", version=__version__)
