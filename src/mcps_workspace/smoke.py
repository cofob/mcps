import os
import sys
import tempfile
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcps_workspace.models import ProfileRecord


async def smoke_test_profile(record: ProfileRecord, config_dir: Path) -> int:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "mcps_workspace.runner",
            record.service.value,
            "--profile",
            record.name,
            "--config-dir",
            str(config_dir),
        ],
        env=dict(os.environ),
    )
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as error_log:
        with anyio.fail_after(30):
            async with stdio_client(parameters, errlog=error_log) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools = await session.list_tools()
    if not tools.tools:
        raise RuntimeError("MCP server initialized but exposed no tools.")
    return len(tools.tools)
