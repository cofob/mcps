import httpx
import pytest

from mcp_common.errors import (
    UpstreamAuthError,
    UpstreamNotFoundError,
    UpstreamRateLimitError,
    UpstreamServerError,
    UpstreamValidationError,
)
from mcp_common.http import request_json


@pytest.mark.asyncio
async def test_request_json_returns_payload() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                request=request,
                json={"ok": True},
            )
        ),
        base_url="https://example.com",
    )
    try:
        payload = await request_json(client, "GET", "/status")
    finally:
        await client.aclose()
    assert payload == {"ok": True}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, UpstreamAuthError),
        (404, UpstreamNotFoundError),
        (409, UpstreamValidationError),
        (429, UpstreamRateLimitError),
        (500, UpstreamServerError),
    ],
)
async def test_request_json_maps_upstream_errors(
    status_code: int,
    expected_error: type[RuntimeError],
) -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status_code,
                request=request,
                text="boom",
            )
        ),
        base_url="https://example.com",
    )
    try:
        with pytest.raises(expected_error):
            await request_json(client, "GET", "/status")
    finally:
        await client.aclose()
