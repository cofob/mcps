import uvicorn

from slskd_mcp.app import create_app
from slskd_mcp.config import SlskdSettings


def main() -> None:
    settings = SlskdSettings.from_env()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
