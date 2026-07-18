from mcp_common import run_service
from navidrome_mcp.app import create_app, create_mcp
from navidrome_mcp.config import NavidromeSettings


def main() -> None:
    run_service(NavidromeSettings.from_env, create_mcp, create_app)
