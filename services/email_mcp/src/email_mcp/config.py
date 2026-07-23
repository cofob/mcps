import re
from email.utils import parseaddr
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from mcp_common import BaseServiceSettings, ToolSettings

ACCOUNT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
FINGERPRINT_PATTERN = re.compile(r"^(?:[0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})$")


class TlsMode(StrEnum):
    IMPLICIT = "implicit"
    STARTTLS = "starttls"


class EmailAccountSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imap_host: str
    imap_port: int = Field(default=993, ge=1, le=65535)
    imap_tls: TlsMode = TlsMode.IMPLICIT
    smtp_host: str
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_tls: TlsMode = TlsMode.STARTTLS
    username: str
    password: SecretStr
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    default_from_address: str = Field(validation_alias=AliasChoices("default_from_address", "from_address"))
    from_name: str | None = None
    sent_folder: str | None = None
    gpg_key_fingerprint: str | None = None
    gpg_home: Path | None = None

    @field_validator("imap_host", "smtp_host", "username", "default_from_address")
    @classmethod
    def validate_nonempty_header_safe(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Expected a non-empty value.")
        if "\r" in stripped or "\n" in stripped:
            raise ValueError("Header values must not contain newlines.")
        return stripped

    @field_validator("from_name", "smtp_username")
    @classmethod
    def validate_optional_header_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if "\r" in stripped or "\n" in stripped:
            raise ValueError("Header values must not contain newlines.")
        return stripped

    @field_validator("sent_folder")
    @classmethod
    def validate_sent_folder(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if "\r" in stripped or "\n" in stripped or "\x00" in stripped:
            raise ValueError("Mailbox names must not contain control characters.")
        return stripped

    @field_validator("default_from_address")
    @classmethod
    def validate_default_from_address(cls, value: str) -> str:
        display_name, address = parseaddr(value)
        if display_name or address != value or "@" not in address or address.startswith("@") or address.endswith("@"):
            raise ValueError("default_from_address must contain one bare email address.")
        return value

    @field_validator("gpg_key_fingerprint")
    @classmethod
    def validate_fingerprint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.replace(" ", "").upper()
        if FINGERPRINT_PATTERN.fullmatch(normalized) is None:
            raise ValueError("Expected a full 40- or 64-character OpenPGP fingerprint.")
        return normalized

    @field_validator("gpg_home")
    @classmethod
    def resolve_gpg_home(cls, value: Path | None) -> Path | None:
        return value.expanduser().resolve() if value is not None else None

    @model_validator(mode="after")
    def validate_smtp_credentials(self) -> Self:
        if (self.smtp_username is None) != (self.smtp_password is None):
            raise ValueError("Provide both smtp_username and smtp_password, or neither.")
        return self

    @property
    def resolved_smtp_username(self) -> str:
        return self.smtp_username or self.username

    @property
    def resolved_smtp_password(self) -> SecretStr:
        return self.smtp_password or self.password


class EmailSettings(BaseServiceSettings):
    email_accounts: dict[str, EmailAccountSettings] = Field(alias="EMAIL_ACCOUNTS")
    email_max_results: int = Field(default=100, ge=1, alias="EMAIL_MAX_RESULTS")
    email_max_body_chars: int = Field(default=100_000, ge=1, alias="EMAIL_MAX_BODY_CHARS")
    email_max_message_bytes: int = Field(default=25 * 1024 * 1024, ge=1, alias="EMAIL_MAX_MESSAGE_BYTES")
    email_max_attachment_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1,
        alias="EMAIL_MAX_ATTACHMENT_BYTES",
    )
    email_max_total_attachment_bytes: int = Field(
        default=20 * 1024 * 1024,
        ge=1,
        alias="EMAIL_MAX_TOTAL_ATTACHMENT_BYTES",
    )
    email_max_recipients: int = Field(default=50, ge=1, alias="EMAIL_MAX_RECIPIENTS")
    email_gpg_binary: str = Field(default="gpg", alias="EMAIL_GPG_BINARY")
    tools: ToolSettings = Field(default_factory=ToolSettings)

    @field_validator("email_accounts")
    @classmethod
    def validate_accounts(
        cls,
        value: dict[str, EmailAccountSettings],
    ) -> dict[str, EmailAccountSettings]:
        if not value:
            raise ValueError("Configure at least one email account.")
        invalid = [name for name in value if ACCOUNT_NAME_PATTERN.fullmatch(name) is None]
        if invalid:
            raise ValueError("Account names may contain only letters, digits, '.', '_', and '-'.")
        return value

    @field_validator("email_gpg_binary")
    @classmethod
    def validate_gpg_binary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("EMAIL_GPG_BINARY must not be empty.")
        return stripped

    def account(self, name: str) -> EmailAccountSettings:
        try:
            return self.email_accounts[name]
        except KeyError as exc:
            available = ", ".join(sorted(self.email_accounts))
            raise ValueError(f"Unknown email account {name!r}. Available accounts: {available}.") from exc

    @classmethod
    def from_env(cls) -> Self:
        return cls()  # type: ignore[call-arg]
