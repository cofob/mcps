from email_mcp.app import create_app, create_mcp
from email_mcp.config import EmailSettings
from mcp_common import run_service


def main() -> None:
    run_service(EmailSettings.from_env, create_mcp, create_app)
