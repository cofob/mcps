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
    async def text(self, message: str, *, default: str = "", secret: bool = False) -> str: ...

    async def confirm(self, message: str, *, default: bool = False) -> bool: ...

    async def select(self, message: str, choices: list[tuple[str, str]]) -> str: ...

    async def checkbox(self, message: str, choices: list[tuple[str, str]]) -> list[str]: ...

    def message(self, text: str) -> None: ...


class QuestionaryPrompt:
    async def text(self, message: str, *, default: str = "", secret: bool = False) -> str:
        question = (
            questionary.password(message, default=default) if secret else questionary.text(message, default=default)
        )
        answer = cast(str | None, await question.ask_async())
        if answer is None:
            raise InstallerCancelledError("Installation cancelled.")
        return answer.strip()

    async def confirm(self, message: str, *, default: bool = False) -> bool:
        answer = cast(bool | None, await questionary.confirm(message, default=default).ask_async())
        if answer is None:
            raise InstallerCancelledError("Installation cancelled.")
        return answer

    async def select(self, message: str, choices: list[tuple[str, str]]) -> str:
        rendered = [questionary.Choice(title=title, value=value) for title, value in choices]
        answer = cast(str | None, await questionary.select(message, choices=rendered).ask_async())
        if answer is None:
            raise InstallerCancelledError("Installation cancelled.")
        return answer

    async def checkbox(self, message: str, choices: list[tuple[str, str]]) -> list[str]:
        rendered = [questionary.Choice(title=title, value=value) for title, value in choices]
        answer = cast(list[str] | None, await questionary.checkbox(message, choices=rendered).ask_async())
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


def _expanded_path(value: str) -> str:
    return str(Path(value).expanduser())


async def _required(prompt: PromptIO, message: str, *, default: str = "", secret: bool = False) -> str:
    while True:
        value = await prompt.text(message, default=default, secret=secret)
        if value:
            return value
        prompt.message("A value is required.")


async def _integer(prompt: PromptIO, message: str, default: int) -> int:
    while True:
        value = await prompt.text(message, default=str(default))
        try:
            parsed = int(value)
        except ValueError:
            prompt.message("Enter a valid port number.")
            continue
        if 1 <= parsed <= 65535:
            return parsed
        prompt.message("Port must be between 1 and 65535.")


async def _profile_name(prompt: PromptIO) -> str:
    while True:
        value = (await _required(prompt, "Profile name", default="default")).lower()
        if PROFILE_PATTERN.fullmatch(value) is not None:
            return value
        prompt.message("Use lowercase letters, digits, underscores, and hyphens; start with a letter or digit.")


async def _account_name(prompt: PromptIO, existing: set[str]) -> str:
    while True:
        value = await _required(prompt, "Account name", default="personal")
        if ACCOUNT_NAME_PATTERN.fullmatch(value) is None:
            prompt.message("Use letters, digits, '.', '_', and '-'.")
        elif value in existing:
            prompt.message("That account name is already used in this profile.")
        else:
            return value


async def choose_services(prompt: PromptIO) -> list[ServiceKind]:
    selected = await prompt.checkbox(
        "Select MCP services to configure",
        [(service.display_name, service.value) for service in ServiceKind],
    )
    return [ServiceKind(value) for value in selected]


async def choose_agents(prompt: PromptIO, detected: list[AgentKind]) -> list[AgentKind]:
    selected = await prompt.checkbox(
        "Select agents to register",
        [(agent.display_name, agent.value) for agent in detected],
    )
    return [AgentKind(value) for value in selected]


async def _tls_mode(prompt: PromptIO, label: str, default: str) -> str:
    choices = [("Implicit TLS", "implicit"), ("STARTTLS", "starttls")]
    if default == "starttls":
        choices.reverse()
    return await prompt.select(f"{label} TLS mode", choices)


async def _email_endpoint(prompt: PromptIO, preset_name: str) -> EmailPreset:
    if preset_name in EMAIL_PRESETS:
        return EMAIL_PRESETS[preset_name]
    return EmailPreset(
        imap_host=await _required(prompt, "IMAP host"),
        imap_port=await _integer(prompt, "IMAP port", 993),
        imap_tls=await _tls_mode(prompt, "IMAP", "implicit"),
        smtp_host=await _required(prompt, "SMTP host"),
        smtp_port=await _integer(prompt, "SMTP port", 587),
        smtp_tls=await _tls_mode(prompt, "SMTP", "starttls"),
    )


async def _collect_email_account(prompt: PromptIO, existing: set[str]) -> tuple[str, JsonObject]:
    name = await _account_name(prompt, existing)
    preset_name = await prompt.select(
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
    endpoint = await _email_endpoint(prompt, preset_name)
    address = await _required(prompt, "Email/from address")
    username_default = address.split("@", maxsplit=1)[0] if preset_name == "icloud" else address
    username = await _required(prompt, "IMAP username", default=username_default)
    password = await _required(prompt, "IMAP password or app password", secret=True)
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
    from_name = await prompt.text("Display name (optional)")
    if from_name:
        account["from_name"] = from_name
    if await prompt.confirm("Use different SMTP credentials?", default=False):
        account["smtp_username"] = await _required(prompt, "SMTP username", default=address)
        account["smtp_password"] = await _required(prompt, "SMTP password or app password", secret=True)
    if await prompt.confirm("Configure OpenPGP/MIME signing?", default=False):
        account["gpg_key_fingerprint"] = await _required(prompt, "Full GPG key fingerprint")
        gpg_home = await prompt.text("GPG home directory (optional)")
        if gpg_home:
            account["gpg_home"] = _expanded_path(gpg_home)
    return name, account


async def _collect_email(prompt: PromptIO, name: str, secret_store: SecretStoreKind) -> CollectedProfile:
    accounts: dict[str, JsonObject] = {}
    while True:
        account_name, account = await _collect_email_account(prompt, set(accounts))
        accounts[account_name] = account
        if not await prompt.confirm("Add another email account?", default=False):
            break
    value = json.dumps(accounts, separators=(",", ":"), sort_keys=True)
    record = ProfileRecord(service=ServiceKind.EMAIL, name=name, secret_store=secret_store)
    return CollectedProfile(record=record, secret_values={"EMAIL_ACCOUNTS": value})


async def _collect_filesystem(prompt: PromptIO, name: str, secret_store: SecretStoreKind) -> CollectedProfile:
    root = await _required(prompt, "Filesystem root directory")
    record = ProfileRecord(
        service=ServiceKind.FILESYSTEM,
        name=name,
        environment={"FILESYSTEM_ROOT_DIR": _expanded_path(root)},
        secret_store=secret_store,
    )
    return CollectedProfile(record=record)


async def _collect_navidrome(prompt: PromptIO, name: str, secret_store: SecretStoreKind) -> CollectedProfile:
    record = ProfileRecord(
        service=ServiceKind.NAVIDROME,
        name=name,
        environment={
            "NAVIDROME_URL": await _required(prompt, "Navidrome URL", default="http://localhost:4533"),
            "NAVIDROME_USERNAME": await _required(prompt, "Navidrome username"),
        },
        secret_store=secret_store,
    )
    password = await _required(prompt, "Navidrome password", secret=True)
    return CollectedProfile(record=record, secret_values={"NAVIDROME_PASSWORD": password})


async def _collect_slskd(prompt: PromptIO, name: str, secret_store: SecretStoreKind) -> CollectedProfile:
    auth_mode = await prompt.select("slskd authentication", [("API key", "api-key"), ("Username/password", "password")])
    record = ProfileRecord(
        service=ServiceKind.SLSKD,
        name=name,
        environment={"SLSKD_URL": await _required(prompt, "slskd URL", default="http://localhost:5030")},
        secret_store=secret_store,
    )
    if auth_mode == "api-key":
        secrets = {"SLSKD_API_KEY": await _required(prompt, "slskd API key", secret=True)}
    else:
        record.environment["SLSKD_API_KEY"] = ""
        record.environment["SLSKD_USERNAME"] = await _required(prompt, "slskd username")
        secrets = {"SLSKD_PASSWORD": await _required(prompt, "slskd password", secret=True)}
    return CollectedProfile(record=record, secret_values=secrets)


async def _collect_tg_export_txt(prompt: PromptIO, name: str, secret_store: SecretStoreKind) -> CollectedProfile:
    root = await _required(prompt, "Telegram TXT export root directory")
    rg_path = await _required(prompt, "ripgrep executable", default="rg")
    record = ProfileRecord(
        service=ServiceKind.TG_EXPORT_TXT,
        name=name,
        environment={"TG_EXPORT_TXT_ROOT_DIR": _expanded_path(root), "TG_EXPORT_TXT_RG_PATH": rg_path},
        secret_store=secret_store,
    )
    return CollectedProfile(record=record)


async def collect_profile(
    prompt: PromptIO,
    service: ServiceKind,
    secret_store: SecretStoreKind,
    *,
    profile_name: str | None = None,
) -> CollectedProfile:
    name = profile_name or await _profile_name(prompt)
    if service is ServiceKind.EMAIL:
        return await _collect_email(prompt, name, secret_store)
    if service is ServiceKind.FILESYSTEM:
        return await _collect_filesystem(prompt, name, secret_store)
    if service is ServiceKind.NAVIDROME:
        return await _collect_navidrome(prompt, name, secret_store)
    if service is ServiceKind.SLSKD:
        return await _collect_slskd(prompt, name, secret_store)
    return await _collect_tg_export_txt(prompt, name, secret_store)
