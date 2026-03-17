from pathlib import Path
from typing import cast

import pytest
from pydantic import AnyHttpUrl

from filesystem_mcp.app import create_mcp as create_filesystem_mcp
from filesystem_mcp.config import FilesystemSettings
from navidrome_mcp.app import create_mcp as create_navidrome_mcp
from navidrome_mcp.config import NavidromeSettings
from slskd_mcp.app import create_mcp as create_slskd_mcp
from slskd_mcp.config import SlskdSettings


@pytest.mark.asyncio
async def test_filesystem_tools_expose_local_markers(tmp_path: Path) -> None:
    mcp = create_filesystem_mcp(FilesystemSettings(FILESYSTEM_ROOT_DIR=tmp_path))
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    read_tool = tools["read_file"]
    assert read_tool.annotations is not None
    assert read_tool.tags >= {"read", "read-only", "local-filesystem", "closed-world"}
    assert read_tool.annotations.readOnlyHint is True
    assert read_tool.annotations.openWorldHint is False

    delete_tool = tools["delete_file"]
    assert delete_tool.annotations is not None
    assert delete_tool.tags >= {"mutate", "write", "local-filesystem", "closed-world"}
    assert delete_tool.annotations.destructiveHint is True
    assert delete_tool.annotations.readOnlyHint is False


@pytest.mark.asyncio
async def test_navidrome_tools_expose_open_world_markers() -> None:
    mcp = create_navidrome_mcp(
        NavidromeSettings(
            NAVIDROME_URL=cast(AnyHttpUrl, "https://navidrome.example.com"),
            NAVIDROME_USERNAME="alice",
            NAVIDROME_PASSWORD="secret",
        )
    )
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    search_tool = tools["navidrome_search"]
    assert search_tool.annotations is not None
    assert search_tool.tags >= {"read", "read-only", "remote-service", "open-world"}
    assert search_tool.annotations.readOnlyHint is True
    assert search_tool.annotations.openWorldHint is True

    delete_tool = tools["navidrome_delete_playlist"]
    assert delete_tool.annotations is not None
    assert delete_tool.tags >= {"mutate", "write", "remote-service", "open-world"}
    assert delete_tool.annotations.destructiveHint is True


@pytest.mark.asyncio
async def test_slskd_tools_expose_write_and_destructive_markers() -> None:
    mcp = create_slskd_mcp(
        SlskdSettings(
            SLSKD_URL=cast(AnyHttpUrl, "https://slskd.example.com"),
            SLSKD_API_KEY="secret",
        )
    )
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    request_tool = tools["slskd_request_downloads"]
    assert request_tool.annotations is not None
    assert request_tool.tags >= {"mutate", "write", "remote-service", "open-world"}
    assert request_tool.annotations.readOnlyHint is False
    assert request_tool.annotations.destructiveHint is False

    clear_tool = tools["slskd_clear_completed_downloads"]
    assert clear_tool.annotations is not None
    assert clear_tool.tags >= {"mutate", "write", "remote-service", "open-world"}
    assert clear_tool.annotations.destructiveHint is True
