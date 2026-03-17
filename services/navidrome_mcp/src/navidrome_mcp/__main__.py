import uvicorn

from navidrome_mcp.app import create_app
from navidrome_mcp.config import NavidromeSettings


def main() -> None:
    settings = NavidromeSettings.from_env()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
