import uvicorn

from filesystem_mcp.app import create_app
from filesystem_mcp.config import FilesystemSettings


def main() -> None:
    settings = FilesystemSettings.from_env()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
