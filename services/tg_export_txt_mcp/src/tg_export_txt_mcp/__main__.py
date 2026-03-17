import uvicorn

from tg_export_txt_mcp.app import create_app
from tg_export_txt_mcp.config import TgExportTxtSettings


def main() -> None:
    settings = TgExportTxtSettings.from_env()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
