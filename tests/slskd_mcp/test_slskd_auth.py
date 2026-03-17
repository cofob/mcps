from typing import cast

import httpx
import pytest
from pydantic import AnyHttpUrl

from slskd_mcp.auth import SlskdAuth
from slskd_mcp.config import SlskdSettings


@pytest.mark.asyncio
async def test_slskd_auth_uses_api_key_without_session_request() -> None:
    settings = SlskdSettings(
        SLSKD_URL=cast(AnyHttpUrl, "https://slskd.example.com"),
        SLSKD_API_KEY="secret",
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500, request=request)
        ),
        base_url="https://slskd.example.com",
    )
    try:
        headers = await SlskdAuth(settings, client).get_headers()
    finally:
        await client.aclose()
    assert headers == {"Authorization": "Bearer secret"}


@pytest.mark.asyncio
async def test_slskd_auth_fetches_and_caches_jwt() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(
            200,
            request=request,
            json={"token": "jwt-token"},
        )

    settings = SlskdSettings(
        SLSKD_URL=cast(AnyHttpUrl, "https://slskd.example.com"),
        SLSKD_USERNAME="alice",
        SLSKD_PASSWORD="secret",
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://slskd.example.com",
    )
    try:
        auth = SlskdAuth(settings, client)
        first = await auth.get_headers()
        second = await auth.get_headers()
    finally:
        await client.aclose()

    assert first == {"Authorization": "Bearer jwt-token"}
    assert second == {"Authorization": "Bearer jwt-token"}
    assert calls == ["/api/v0/session"]
