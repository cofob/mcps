from mcp_common import run_service
from tg_export_txt_mcp.app import create_app, create_mcp
from tg_export_txt_mcp.config import TgExportTxtSettings


def main() -> None:
    run_service(TgExportTxtSettings.from_env, create_mcp, create_app)
