from collections.abc import Awaitable, Callable
from typing import cast

from fastmcp import FastMCP
from starlette.applications import Starlette

from filesystem_mcp import __version__
from filesystem_mcp.config import FilesystemSettings
from filesystem_mcp.service import FilesystemService
from filesystem_mcp.tools import DirectoryTools, InfoTools, ReadTools, SearchTools, WriteTools
from mcp_common import (
    SupportsToolRegistration,
    ToolSpec,
    build_auth_provider,
    build_http_app,
    register_enabled_tools,
)
from mcp_common.logging import configure_logging


def _tool_spec(method: Callable[..., Awaitable[str]], name: str, *groups: str) -> ToolSpec:
    def register_tool(mcp: SupportsToolRegistration) -> None:
        mcp.tool(method, name=name)

    return ToolSpec(
        name=name,
        groups=frozenset(groups),
        register=register_tool,
    )


def _register_file_resource(mcp: FastMCP, service: FilesystemService) -> None:
    @mcp.resource(
        "file://{path*}",
        name="file://",
        description="Read a file from the configured filesystem root.",
    )
    def file_resource(path: str) -> str | bytes:
        return service.resource_content(path)

    del file_resource


def _make_tool_specs(service: FilesystemService) -> list[ToolSpec]:
    read_tools = ReadTools(service)
    directory_tools = DirectoryTools(service)
    info_tools = InfoTools(service)
    search_tools = SearchTools(service)
    write_tools = WriteTools(service)
    return [
        _tool_spec(read_tools.read_file, "read_file", "read"),
        _tool_spec(read_tools.read_multiple_files, "read_multiple_files", "read"),
        _tool_spec(directory_tools.list_directory, "list_directory", "read", "directory"),
        _tool_spec(directory_tools.create_directory, "create_directory", "mutate", "directory"),
        _tool_spec(directory_tools.tree, "tree", "read", "directory"),
        _tool_spec(
            directory_tools.list_allowed_directories,
            "list_allowed_directories",
            "read",
            "directory",
        ),
        _tool_spec(info_tools.get_file_info, "get_file_info", "read", "info"),
        _tool_spec(search_tools.search_files, "search_files", "read", "search"),
        _tool_spec(
            search_tools.search_within_files,
            "search_within_files",
            "read",
            "search",
        ),
        _tool_spec(write_tools.write_file, "write_file", "mutate", "write"),
        _tool_spec(write_tools.copy_file, "copy_file", "mutate", "write"),
        _tool_spec(write_tools.move_file, "move_file", "mutate", "write"),
        _tool_spec(write_tools.delete_file, "delete_file", "mutate", "write"),
        _tool_spec(write_tools.modify_file, "modify_file", "mutate", "write"),
        _tool_spec(write_tools.patch_file, "patch_file", "mutate", "write"),
    ]


def create_mcp(settings: FilesystemSettings) -> FastMCP:
    auth = (
        build_auth_provider(settings.oauth2)
        if settings.mcp_auth_mode.value == "oauth2"
        else None
    )
    mcp = FastMCP(name="filesystem-mcp", auth=auth)
    service = FilesystemService(settings)
    register_enabled_tools(
        cast(SupportsToolRegistration, mcp),
        _make_tool_specs(service),
        settings.tools,
    )
    _register_file_resource(mcp, service)
    return mcp


def create_app(settings: FilesystemSettings | None = None) -> Starlette:
    resolved = settings or FilesystemSettings.from_env()
    configure_logging(resolved.log_level)
    mcp = create_mcp(resolved)
    mcp_app = mcp.http_app(path="/mcp")
    return build_http_app(mcp_app, service_name="filesystem-mcp", version=__version__)
