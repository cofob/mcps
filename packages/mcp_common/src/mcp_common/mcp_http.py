from collections.abc import Awaitable, Callable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

HealthHandler = Callable[[Request], Awaitable[JSONResponse]]


def build_http_app(mcp_app: Starlette, *, service_name: str, version: str) -> Starlette:
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": service_name, "version": version})

    return Starlette(
        lifespan=getattr(mcp_app, "lifespan", None),
        routes=[
            Route("/healthz", health),
            Mount("/", app=mcp_app),
        ],
    )
