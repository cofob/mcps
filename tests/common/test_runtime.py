from collections.abc import Callable
from typing import cast
from unittest.mock import Mock, patch

from fastmcp import FastMCP
from starlette.applications import Starlette

from mcp_common import BaseServiceSettings, TransportMode, run_service


def test_run_service_defaults_to_stdio() -> None:
    settings = BaseServiceSettings()
    mcp = Mock(spec=FastMCP)
    mcp_factory = cast(Callable[[BaseServiceSettings], FastMCP], Mock(return_value=mcp))
    app_factory = cast(Callable[[BaseServiceSettings], Starlette], Mock())

    run_service(lambda: settings, mcp_factory, app_factory, argv=[])

    mcp.run.assert_called_once_with(transport="stdio", show_banner=False)
    cast(Mock, app_factory).assert_not_called()


def test_run_service_cli_http_overrides_environment_default() -> None:
    settings = BaseServiceSettings(MCP_TRANSPORT=TransportMode.STDIO)
    mcp_factory = cast(Callable[[BaseServiceSettings], FastMCP], Mock())
    app = Starlette()
    app_factory = cast(Callable[[BaseServiceSettings], Starlette], Mock(return_value=app))

    with patch("mcp_common.runtime.uvicorn.run") as run_mock:
        run_service(lambda: settings, mcp_factory, app_factory, argv=["--transport", "http"])

    run_mock.assert_called_once_with(app, host=settings.host, port=settings.port)
    cast(Mock, mcp_factory).assert_not_called()
