from typing import Self

from pydantic import AnyHttpUrl, Field

from mcp_common import BaseServiceSettings, ToolSettings


class NavidromeSettings(BaseServiceSettings):
    navidrome_url: AnyHttpUrl = Field(alias="NAVIDROME_URL")
    navidrome_username: str = Field(alias="NAVIDROME_USERNAME")
    navidrome_password: str = Field(alias="NAVIDROME_PASSWORD")
    navidrome_client_name: str = Field(default="navidrome-mcp", alias="NAVIDROME_CLIENT_NAME")
    navidrome_api_version: str = Field(default="1.16.1", alias="NAVIDROME_API_VERSION")
    tools: ToolSettings = Field(default_factory=ToolSettings)

    @classmethod
    def from_env(cls) -> Self:
        return cls()  # type: ignore[call-arg]
