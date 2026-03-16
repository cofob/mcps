
import httpx

from mcp_common import HttpQueryParams, JsonArray, JsonObject, JsonValue, request_json
from slskd_mcp.auth import SlskdAuth
from slskd_mcp.config import SlskdSettings


class SlskdClient:
    def __init__(self, settings: SlskdSettings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client
        self._auth = SlskdAuth(settings, http_client)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: HttpQueryParams | None = None,
        json_body: JsonValue | None = None,
    ) -> JsonObject | JsonArray:
        headers = await self._auth.get_headers()
        return await request_json(
            self._http,
            method,
            path,
            params=params,
            json_body=json_body,
            headers=headers,
        )
