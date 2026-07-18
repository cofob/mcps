import argparse
from collections.abc import Callable, Sequence
from typing import cast

import uvicorn
from fastmcp import FastMCP
from starlette.applications import Starlette

from mcp_common.config import BaseServiceSettings, TransportMode
from mcp_common.logging import configure_logging


def _parse_transport(argv: Sequence[str] | None) -> TransportMode | None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport",
        choices=[mode.value for mode in TransportMode],
        default=None,
        help="MCP transport to run (default: MCP_TRANSPORT or stdio).",
    )
    parsed = parser.parse_args(argv)
    value = cast(str | None, parsed.transport)
    return TransportMode(value) if value is not None else None


def run_service[SettingsT: BaseServiceSettings](
    settings_factory: Callable[[], SettingsT],
    mcp_factory: Callable[[SettingsT], FastMCP],
    http_app_factory: Callable[[SettingsT], Starlette],
    argv: Sequence[str] | None = None,
) -> None:
    cli_transport = _parse_transport(argv)
    settings = settings_factory()
    transport = cli_transport or settings.mcp_transport
    configure_logging(settings.log_level)

    if transport is TransportMode.STDIO:
        mcp_factory(settings).run(transport="stdio", show_banner=False)
        return

    uvicorn.run(http_app_factory(settings), host=settings.host, port=settings.port)
