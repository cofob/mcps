from typing import cast

import httpx
import pytest
from pydantic import AnyHttpUrl

from navidrome_mcp.client import NavidromeClient
from navidrome_mcp.config import NavidromeSettings


@pytest.mark.asyncio
async def test_navidrome_client_merges_auth_and_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_path: str | None = None
    seen_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path, seen_params
        seen_path = request.url.path
        seen_params = dict(request.url.params.multi_items())
        return httpx.Response(
            200,
            request=request,
            json={"subsonic-response": {"status": "ok"}},
        )

    monkeypatch.setattr("navidrome_mcp.auth.secrets.token_hex", lambda _: "salted")
    settings = NavidromeSettings(
        NAVIDROME_URL=cast(AnyHttpUrl, "https://navidrome.example.com"),
        NAVIDROME_USERNAME="alice",
        NAVIDROME_PASSWORD="secret",
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://navidrome.example.com",
    )
    try:
        api = NavidromeClient(settings, client)
        payload = await api.call(
            "getAlbum",
            params={"id": "album-1", "musicFolderId": None},
        )
    finally:
        await client.aclose()

    assert payload == {"subsonic-response": {"status": "ok"}}
    assert seen_path == "/rest/getAlbum"
    assert seen_params["u"] == "alice"
    assert seen_params["id"] == "album-1"
    assert "musicFolderId" not in seen_params
