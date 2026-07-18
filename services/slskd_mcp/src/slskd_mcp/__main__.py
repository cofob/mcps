from mcp_common import run_service
from slskd_mcp.app import create_app, create_mcp
from slskd_mcp.config import SlskdSettings


def main() -> None:
    run_service(SlskdSettings.from_env, create_mcp, create_app)
