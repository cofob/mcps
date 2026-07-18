import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import questionary

from email_mcp.config import ACCOUNT_NAME_PATTERN
from mcp_common import JsonObject
from mcps_workspace.models import (
    PROFILE_PATTERN,
    AgentKind,
    CollectedProfile,
    ProfileRecord,
    SecretStoreKind,
    ServiceKind,
)


class InstallerCancelledError(RuntimeError):
    pass


class PromptIO(Protocol):
    def text(self, message: str, *, default: str = "", secret: bool = False) -> str: ...

    def confirm(self, message: str, *, default: bool = False) -> bool: ...

    def select(self, message: str, choices: list[tuple[str, str]]) -> str: ...

    def checkbox(self, message: str, choices: list[tuple[str, str]]) -> list[str]: ...

    def message(self, text: str) -> None: ...


class QuestionaryPrompt:
    def text(self, message: str, *, default: str = "", secret: bool = False) -> str:
        question = (
            questionary.password(message, default=default) if secret else questionary.text(message, default=default)
        )
        answer = cast(str | None, question.ask())
        if answer is None:
            raise InstallerCancelledError("Installation cancelled.")
        return answer.strip()

    def confirm(self, message: str, *, default: bool = False) -> bool:
        answer = cast(bool | None, questionary.confirm(message, default=default).ask())
        if answer is None:
            raise InstallerCancelledError("Installation cancelled.")
        return answer

    def select(self, message: str, choices: list[tuple[str, str]]) -> str:
        rendered = [questionary.Choice(title=title, value=value) for title, value in choices]
        answer = cast(str | None, questionary.select(message, choices=rendered).ask())
        if answer is None:
            raise InstallerCancelledError("Installation cancelled.")
        return answer

    def checkbox(self, message: str, choices: list[tuple[str, str]]) -> list[str]:
        rendered = [questionary.Choice(title=title, value=value) for title, value in choices]
        answer = cast(list[str] | None, questionary.checkbox(message, choices=rendered).ask())
        if answer is None:
            raise InstallerCancelledError("Installation cancelled.")
        return answer

    def message(self, text: str) -> None:
        sys.stdout.write(text.rstrip() + "\n")


@dataclass(frozen=True)
class EmailPreset:
    imap_host: str
    imap_port: int
    imap_tls: str
    smtp_host: str
    smtp_port: int
    smtp_tls: str


EMAIL_PRESETS: dict[str, EmailPreset] = {
    "gmail": EmailPreset("imap.gmail.com", 993, "implicit", "smtp.gmail.com", 587, "starttls"),
    "outlook": EmailPreset("outlook.office365.com", 993, "implicit", "smtp-mail.outlook.com", 587, "starttls"),
    "icloud": EmailPreset("imap.mail.me.com", 993, "implicit", "smtp.mail.me.com", 587, "starttls"),
    "fastmail": EmailPreset("imap.fastmail.com", 993, "implicit", "smtp.fastmail.com", 465, "implicit"),
}


def _required(prompt: PromptIO, message: str, *, default: str = "", secret: bool = False) -> str:
    while True:
        value = prompt.text(message, default=default, secret=secret)
        if value:
            return value
        prompt.message("A value is required.")


def _integer(prompt: PromptIO, message: str, default: int) -> int:
    while True:
        value = prompt.text(message, default=str(default))
        try:
            parsed = int(value)
        except ValueError:
            prompt.message("Enter a valid port number.")
            continue
        if 1 <= parsed <= 65535:
            return parsed
        prompt.message("Port must be between 1 and 65535.")


def _profile_name(prompt: PromptIO) -> str:
    while True:
        value = _required(prompt, "Profile name", default="default").lower()
        if PROFILE_PATTERN.fullmatch(value) is not None:
            return value
        prompt.message("Use lowercase letters, digits, underscores, and hyphens; start with a letter or digit.")


def _account_name(prompt: PromptIO, existing: set[str]) -> str:
    while True:
        value = _required(prompt, "Account name", default="personal")
        if ACCOUNT_NAME_PATTERN.fullmatch(value) is None:
            prompt.message("Use letters, digits, '.', '_', and '-'.")
        elif value in existing:
            prompt.message("That account name is already used in this profile.")
        else:
            return value


def choose_services(prompt: PromptIO) -> list[ServiceKind]:
    selected = prompt.checkbox(
        "Select MCP services to configure",
        [(service.display_name, service.value) for service in ServiceKind],
    )
    return [ServiceKind(value) for value in selected]


def choose_agents(prompt: PromptIO, detected: list[AgentKind]) -> list[AgentKind]:
    selected = prompt.checkbox(
        "Select agents to register",
        [(agent.display_name, agent.value) for agent in detected],
    )
    return [AgentKind(value) for value in selected]


def _tls_mode(prompt: PromptIO, label: str, default: str) -> str:
    choices = [("Implicit TLS", "implicit"), ("STARTTLS", "starttls")]
    if default == "starttls":
        choices.reverse()
    return prompt.select(f"{label} TLS mode", choices)


def _email_endpoint(prompt: PromptIO, preset_name: str) -> EmailPreset:
    if preset_name in EMAIL_PRESETS:
        return EMAIL_PRESETS[preset_name]
    return EmailPreset(
        imap_host=_required(prompt, "IMAP host"),
        imap_port=_integer(prompt, "IMAP port", 993),
        imap_tls=_tls_mode(prompt, "IMAP", "implicit"),
        smtp_host=_required(prompt, "SMTP host"),
        smtp_port=_integer(prompt, "SMTP port", 587),
        smtp_tls=_tls_mode(prompt, "SMTP", "starttls"),
    )


def _collect_email_account(prompt: PromptIO, existing: set[str]) -> tuple[str, JsonObject]:
    name = _account_name(prompt, existing)
    preset_name = prompt.select(
        "Mail provider",
        [
            ("Gmail", "gmail"),
            ("Outlook.com", "outlook"),
            ("iCloud Mail", "icloud"),
            ("Fastmail", "fastmail"),
            ("Custom IMAP/SMTP", "custom"),
        ],
    )
    if preset_name == "outlook":
        prompt.message("Outlook.com normally requires OAuth2/Modern Auth; password validation may be rejected.")
    endpoint = _email_endpoint(prompt, preset_name)
    address = _required(prompt, "Email/from address")
    username_default = address.split("@", maxsplit=1)[0] if preset_name == "icloud" else address
    username = _required(prompt, "IMAP username", default=username_default)
    password = _required(prompt, "IMAP password or app password", secret=True)
    account: JsonObject = {
        "imap_host": endpoint.imap_host,
        "imap_port": endpoint.imap_port,
        "imap_tls": endpoint.imap_tls,
        "smtp_host": endpoint.smtp_host,
        "smtp_port": endpoint.smtp_port,
        "smtp_tls": endpoint.smtp_tls,
        "username": username,
        "password": password,
        "from_address": address,
    }
    from_name = prompt.text("Display name (optional)")
    if from_name:
        account["from_name"] = from_name
    if prompt.confirm("Use different SMTP credentials?", default=False):
        account["smtp_username"] = _required(prompt, "SMTP username", default=address)
        account["smtp_password"] = _required(prompt, "SMTP password or app password", secret=True)
    if prompt.confirm("Configure OpenPGP/MIME signing?", default=False):
        account["gpg_key_fingerprint"] = _required(prompt, "Full GPG key fingerprint")
        gpg_home = prompt.text("GPG home directory (optional)")
        if gpg_home:
            account["gpg_home"] = str(Path(gpg_home).expanduser())
    return name, account


def _collect_email(prompt: PromptIO, name: str, secret_store: SecretStoreKind) -> CollectedProfile:
    accounts: dict[str, JsonObject] = {}
    while True:
        account_name, account = _collect_email_account(prompt, set(accounts))
        accounts[account_name] = account
        if not prompt.confirm("Add another email account?", default=False):
            break
    value = json.dumps(accounts, separators=(",", ":"), sort_keys=True)
    record = ProfileRecord(service=ServiceKind.EMAIL, name=name, secret_store=secret_store)
    return CollectedProfile(record=record, secret_values={"EMAIL_ACCOUNTS": value})


def _collect_filesystem(prompt: PromptIO, name: str, secret_store: SecretStoreKind) -> CollectedProfile:
    root = _required(prompt, "Filesystem root directory")
    record = ProfileRecord(
        service=ServiceKind.FILESYSTEM,
        name=name,
        environment={"FILESYSTEM_ROOT_DIR": str(Path(root).expanduser())},
        secret_store=secret_store,
    )
    return CollectedProfile(record=record)


def _collect_navidrome(prompt: PromptIO, name: str, secret_store: SecretStoreKind) -> CollectedProfile:
    record = ProfileRecord(
        service=ServiceKind.NAVIDROME,
        name=name,
        environment={
            "NAVIDROME_URL": _required(prompt, "Navidrome URL", default="http://localhost:4533"),
            "NAVIDROME_USERNAME": _required(prompt, "Navidrome username"),
        },
        secret_store=secret_store,
    )
    password = _required(prompt, "Navidrome password", secret=True)
    return CollectedProfile(record=record, secret_values={"NAVIDROME_PASSWORD": password})


def _collect_slskd(prompt: PromptIO, name: str, secret_store: SecretStoreKind) -> CollectedProfile:
    auth_mode = prompt.select("slskd authentication", [("API key", "api-key"), ("Username/password", "password")])
    record = ProfileRecord(
        service=ServiceKind.SLSKD,
        name=name,
        environment={"SLSKD_URL": _required(prompt, "slskd URL", default="http://localhost:5030")},
        secret_store=secret_store,
    )
    if auth_mode == "api-key":
        secrets = {"SLSKD_API_KEY": _required(prompt, "slskd API key", secret=True)}
    else:
        record.environment["SLSKD_API_KEY"] = ""
        record.environment["SLSKD_USERNAME"] = _required(prompt, "slskd username")
        secrets = {"SLSKD_PASSWORD": _required(prompt, "slskd password", secret=True)}
    return CollectedProfile(record=record, secret_values=secrets)


def _collect_tg_export_txt(prompt: PromptIO, name: str, secret_store: SecretStoreKind) -> CollectedProfile:
    root = _required(prompt, "Telegram TXT export root directory")
    rg_path = _required(prompt, "ripgrep executable", default="rg")
    record = ProfileRecord(
        service=ServiceKind.TG_EXPORT_TXT,
        name=name,
        environment={"TG_EXPORT_TXT_ROOT_DIR": str(Path(root).expanduser()), "TG_EXPORT_TXT_RG_PATH": rg_path},
        secret_store=secret_store,
    )
    return CollectedProfile(record=record)


def collect_profile(
    prompt: PromptIO,
    service: ServiceKind,
    secret_store: SecretStoreKind,
    *,
    profile_name: str | None = None,
) -> CollectedProfile:
    name = profile_name or _profile_name(prompt)
    if service is ServiceKind.EMAIL:
        return _collect_email(prompt, name, secret_store)
    if service is ServiceKind.FILESYSTEM:
        return _collect_filesystem(prompt, name, secret_store)
    if service is ServiceKind.NAVIDROME:
        return _collect_navidrome(prompt, name, secret_store)
    if service is ServiceKind.SLSKD:
        return _collect_slskd(prompt, name, secret_store)
    return _collect_tg_export_txt(prompt, name, secret_store)
