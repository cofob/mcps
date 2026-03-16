import httpx

from mcp_common import expect_object, get_str
from slskd_mcp.config import SlskdSettings


class SlskdAuth:
    def __init__(self, settings: SlskdSettings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client
        self._jwt: str | None = None

    async def get_headers(self) -> dict[str, str]:
        if self._settings.slskd_api_key:
            return {"Authorization": f"Bearer {self._settings.slskd_api_key}"}
        if self._jwt is None:
            response = await self._client.post(
                "/api/v0/session",
                json={
                    "username": self._settings.slskd_username,
                    "password": self._settings.slskd_password,
                },
            )
            response.raise_for_status()
            payload = expect_object(response.json(), context="slskd session")
            token = get_str(payload, "token")
            if token is None:
                raise ValueError("slskd session response is missing token.")
            self._jwt = token
        return {"Authorization": f"Bearer {self._jwt}"}
