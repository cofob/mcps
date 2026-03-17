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
    create_async_client,
    register_enabled_tools,
)
from mcp_common.logging import configure_logging
from slskd_mcp import __version__
from slskd_mcp.client import SlskdClient
from slskd_mcp.config import SlskdSettings
from slskd_mcp.tools import DownloadTools, FileTools, SearchTools, UploadTools, UserTools


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


def _make_tool_specs(client: SlskdClient) -> list[ToolSpec]:
    search_tools = SearchTools(client)
    user_tools = UserTools(client)
    download_tools = DownloadTools(client)
    upload_tools = UploadTools(client)
    file_tools = FileTools(client)
    return [
        _tool_spec(search_tools.create_search, "slskd_create_search", "mutate", "search"),
        _tool_spec(search_tools.list_searches, "slskd_list_searches", "read", "search"),
        _tool_spec(search_tools.get_search, "slskd_get_search", "read", "search"),
        _tool_spec(
            search_tools.get_search_results,
            "slskd_get_search_results",
            "read",
            "search",
        ),
        _tool_spec(search_tools.cancel_search, "slskd_cancel_search", "mutate", "search"),
        _tool_spec(search_tools.delete_search, "slskd_delete_search", "mutate", "search"),
        _tool_spec(user_tools.get_user, "slskd_get_user", "read"),
        _tool_spec(user_tools.browse_user, "slskd_browse_user", "read"),
        _tool_spec(
            download_tools.request_downloads,
            "slskd_request_downloads",
            "mutate",
            "downloads",
        ),
        _tool_spec(
            download_tools.list_downloads,
            "slskd_list_downloads",
            "read",
            "downloads",
        ),
        _tool_spec(
            download_tools.get_download,
            "slskd_get_download",
            "read",
            "downloads",
        ),
        _tool_spec(
            download_tools.get_download_queue_position,
            "slskd_get_download_queue_position",
            "read",
            "downloads",
        ),
        _tool_spec(
            download_tools.cancel_download,
            "slskd_cancel_download",
            "mutate",
            "downloads",
        ),
        _tool_spec(
            download_tools.clear_completed_downloads,
            "slskd_clear_completed_downloads",
            "mutate",
            "downloads",
        ),
        _tool_spec(upload_tools.list_uploads, "slskd_list_uploads", "read", "uploads"),
        _tool_spec(upload_tools.get_upload, "slskd_get_upload", "read", "uploads"),
        _tool_spec(file_tools.list_files, "slskd_list_files", "read", "files"),
    ]


def create_mcp(settings: SlskdSettings) -> FastMCP:
    auth = (
        build_auth_provider(settings.oauth2)
        if settings.mcp_auth_mode.value == "oauth2"
        else None
    )
    mcp = FastMCP(name="slskd-mcp", auth=auth)
    http_client = create_async_client(
        base_url=str(settings.slskd_url),
        timeout_seconds=settings.timeout_seconds,
    )
    client = SlskdClient(settings, http_client)
    register_enabled_tools(
        cast(SupportsToolRegistration, mcp),
        _make_tool_specs(client),
        settings.tools,
    )
    return mcp


def create_app(settings: SlskdSettings | None = None) -> Starlette:
    resolved = settings or SlskdSettings.from_env()
    configure_logging(resolved.log_level)
    mcp = create_mcp(resolved)
    mcp_app = mcp.http_app(path="/mcp")
    return build_http_app(mcp_app, service_name="slskd-mcp", version=__version__)
