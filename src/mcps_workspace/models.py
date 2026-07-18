import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

PROFILE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ServiceKind(StrEnum):
    EMAIL = "email"
    FILESYSTEM = "filesystem"
    NAVIDROME = "navidrome"
    SLSKD = "slskd"
    TG_EXPORT_TXT = "tg-export-txt"

    @property
    def display_name(self) -> str:
        return {
            ServiceKind.EMAIL: "Email",
            ServiceKind.FILESYSTEM: "Filesystem",
            ServiceKind.NAVIDROME: "Navidrome",
            ServiceKind.SLSKD: "slskd",
            ServiceKind.TG_EXPORT_TXT: "Telegram TXT export",
        }[self]


class AgentKind(StrEnum):
    CODEX = "codex"
    CLAUDE = "claude"
    OPENCODE = "opencode"
    GEMINI = "gemini"

    @property
    def display_name(self) -> str:
        return {
            AgentKind.CODEX: "Codex",
            AgentKind.CLAUDE: "Claude Code",
            AgentKind.OPENCODE: "OpenCode",
            AgentKind.GEMINI: "Gemini CLI",
        }[self]


class SecretStoreKind(StrEnum):
    KEYRING = "keyring"
    FILE = "file"


class ProfileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: ServiceKind
    name: str
    environment: dict[str, str] = Field(default_factory=dict)
    secret_environment: dict[str, str] = Field(default_factory=dict)
    secret_store: SecretStoreKind = SecretStoreKind.KEYRING
    verified: bool = False
    verified_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if PROFILE_PATTERN.fullmatch(normalized) is None:
            raise ValueError("Use lowercase letters, digits, underscores, and hyphens; start with a letter or digit.")
        return normalized

    @property
    def key(self) -> str:
        return f"{self.service.value}:{self.name}"

    @property
    def server_name(self) -> str:
        return f"mcps-{self.service.value}-{self.name}"

    def mark_verified(self) -> Self:
        self.verified = True
        self.verified_at = datetime.now(tz=UTC)
        return self


class InstallerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    profiles: dict[str, ProfileRecord] = Field(default_factory=dict)


class CollectedProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: ProfileRecord
    secret_values: dict[str, str] = Field(default_factory=dict)
