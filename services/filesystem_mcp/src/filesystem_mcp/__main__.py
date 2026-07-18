from filesystem_mcp.app import create_app, create_mcp
from filesystem_mcp.config import FilesystemSettings
from mcp_common import run_service


def main() -> None:
    run_service(FilesystemSettings.from_env, create_mcp, create_app)
