import httpx

from mcp_common import HttpQueryParams, JsonObject, expect_object, request_json
from navidrome_mcp.auth import build_subsonic_auth_params
from navidrome_mcp.config import NavidromeSettings


class NavidromeClient:
    def __init__(self, settings: NavidromeSettings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client

    async def call(
        self,
        endpoint: str,
        *,
        params: HttpQueryParams | None = None,
    ) -> JsonObject:
        auth_params = build_subsonic_auth_params(
            username=self._settings.navidrome_username,
            password=self._settings.navidrome_password,
            client_name=self._settings.navidrome_client_name,
            api_version=self._settings.navidrome_api_version,
        )
        merged_params: dict[
            str,
            str | int | float | bool | None | tuple[str | int | float | bool | None, ...],
        ] = dict(auth_params)
        if params is not None:
            merged_params.update(
                {
                    key: (
                        tuple(value)
                        if not isinstance(value, str | int | float | bool) and value is not None
                        else value
                    )
                    for key, value in params.items()
                    if value is not None
                }
            )
        payload = await request_json(
            self._http,
            "GET",
            f"/rest/{endpoint}",
            params=merged_params,
        )
        return expect_object(payload, context=f"/rest/{endpoint}")
