from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_common.auth import AuthMode, OAuth2Settings


class ToolSettings(BaseModel):
    enabled_tools: set[str] | None = None
    disabled_tools: set[str] = Field(default_factory=set)
    disabled_tool_groups: set[str] = Field(default_factory=set)


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8080, alias="PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    timeout_seconds: float = Field(default=20.0, alias="TIMEOUT_SECONDS")
    mcp_auth_mode: AuthMode = Field(default=AuthMode.NONE, alias="MCP_AUTH_MODE")
    oauth2: OAuth2Settings | None = None
    tools: ToolSettings = Field(default_factory=ToolSettings)
