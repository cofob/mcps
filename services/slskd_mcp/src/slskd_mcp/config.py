from typing import Self

from pydantic import AnyHttpUrl, Field, model_validator

from mcp_common import BaseServiceSettings, ToolSettings


class SlskdSettings(BaseServiceSettings):
    slskd_url: AnyHttpUrl = Field(alias="SLSKD_URL")
    slskd_api_key: str | None = Field(default=None, alias="SLSKD_API_KEY")
    slskd_username: str | None = Field(default=None, alias="SLSKD_USERNAME")
    slskd_password: str | None = Field(default=None, alias="SLSKD_PASSWORD")
    tools: ToolSettings = Field(default_factory=ToolSettings)

    @model_validator(mode="after")
    def validate_auth(self) -> Self:
        if self.slskd_api_key:
            return self
        if self.slskd_username and self.slskd_password:
            return self
        raise ValueError("Provide SLSKD_API_KEY or both SLSKD_USERNAME and SLSKD_PASSWORD")

    @classmethod
    def from_env(cls) -> Self:
        return cls()  # type: ignore[call-arg]
