from collections.abc import Mapping

import httpx

from mcp_common.errors import (
    UpstreamAuthError,
    UpstreamNotFoundError,
    UpstreamRateLimitError,
    UpstreamServerError,
    UpstreamValidationError,
)
from mcp_common.types import HttpQueryParams, JsonArray, JsonObject, JsonValue


def create_async_client(*, base_url: str, timeout_seconds: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout_seconds)


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    params: HttpQueryParams | None = None,
    json_body: JsonValue | None = None,
    headers: Mapping[str, str] | None = None,
) -> JsonObject | JsonArray:
    response = await client.request(method, path, params=params, json=json_body, headers=headers)
    if response.status_code in {401, 403}:
        raise UpstreamAuthError(response.text)
    if response.status_code == 404:
        raise UpstreamNotFoundError(response.text)
    if response.status_code == 429:
        raise UpstreamRateLimitError(response.text)
    if response.status_code in {400, 409, 422}:
        raise UpstreamValidationError(response.text)
    if response.status_code >= 500:
        raise UpstreamServerError(response.text)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return payload
    raise UpstreamValidationError("Expected JSON object or array response.")
