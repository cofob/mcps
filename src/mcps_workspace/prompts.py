import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import questionary
from pydantic import TypeAdapter

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
EMAIL_ACCOUNTS_ADAPTER = TypeAdapter(dict[str, JsonObject])


def _expanded_path(value: str) -> str:
    return str(Path(value).expanduser())


async def _required(prompt: PromptIO, message: str, *, default: str = "", secret: bool = False) -> str:
    while True:
        value = await prompt.text(message, default=default, secret=secret)
        if value:
            return value
        prompt.message("A value is required.")


async def _retained_secret(prompt: PromptIO, message: str, existing: str | None) -> str:
    if existing is not None and await prompt.confirm(f"Keep existing {message}?", default=True):
        return existing
    return await _required(prompt, message, secret=True)


def _string_value(values: JsonObject, key: str, default: str = "") -> str:
    value = values.get(key)
    return value if isinstance(value, str) else default


def _integer_value(values: JsonObject, key: str, default: int) -> int:
    value = values.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else default


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


async def choose_profile_to_reconfigure(
    prompt: PromptIO,
    profiles: dict[str, ProfileRecord],
) -> ProfileRecord | None:
    if not profiles:
        return None
    action = await prompt.select(
        "Choose installation action",
        [("Reconfigure an existing profile", "reconfigure"), ("Add a new profile", "add")],
    )
    if action == "add":
        return None
    key = await prompt.select(
        "Select profile to reconfigure",
        [(f"{record.server_name} ({record.service.display_name})", key) for key, record in sorted(profiles.items())],
    )
    return profiles[key]


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
    address = await _required(prompt, "Default From address")
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
        "default_from_address": address,
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


async def _reconfigure_email_account(prompt: PromptIO, name: str, current: JsonObject) -> JsonObject:
    prompt.message(f"Reconfiguring email account {name}; press Enter to keep shown non-secret defaults.")
    imap_host = await _required(prompt, "IMAP host", default=_string_value(current, "imap_host"))
    imap_port = await _integer(prompt, "IMAP port", _integer_value(current, "imap_port", 993))
    imap_tls = await _tls_mode(prompt, "IMAP", _string_value(current, "imap_tls", "implicit"))
    smtp_host = await _required(prompt, "SMTP host", default=_string_value(current, "smtp_host"))
    smtp_port = await _integer(prompt, "SMTP port", _integer_value(current, "smtp_port", 587))
    smtp_tls = await _tls_mode(prompt, "SMTP", _string_value(current, "smtp_tls", "starttls"))
    default_from = _string_value(
        current,
        "default_from_address",
        _string_value(current, "from_address"),
    )
    address = await _required(prompt, "Default From address", default=default_from)
    username = await _required(prompt, "IMAP username", default=_string_value(current, "username", address))
    password = await _retained_secret(
        prompt, "IMAP password or app password", _string_value(current, "password") or None
    )
    account: JsonObject = {
        "imap_host": imap_host,
        "imap_port": imap_port,
        "imap_tls": imap_tls,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_tls": smtp_tls,
        "username": username,
        "password": password,
        "default_from_address": address,
    }
    from_name = await prompt.text("Display name (optional)", default=_string_value(current, "from_name"))
    if from_name:
        account["from_name"] = from_name
    sent_folder = _string_value(current, "sent_folder")
    if sent_folder:
        account["sent_folder"] = sent_folder
    existing_smtp_username = _string_value(current, "smtp_username") or None
    existing_smtp_password = _string_value(current, "smtp_password") or None
    if await prompt.confirm("Use different SMTP credentials?", default=existing_smtp_username is not None):
        account["smtp_username"] = await _required(
            prompt,
            "SMTP username",
            default=existing_smtp_username or address,
        )
        account["smtp_password"] = await _retained_secret(
            prompt,
            "SMTP password or app password",
            existing_smtp_password,
        )
    existing_fingerprint = _string_value(current, "gpg_key_fingerprint") or None
    if await prompt.confirm("Configure OpenPGP/MIME signing?", default=existing_fingerprint is not None):
        account["gpg_key_fingerprint"] = await _required(
            prompt,
            "Full GPG key fingerprint",
            default=existing_fingerprint or "",
        )
        gpg_home = await prompt.text("GPG home directory (optional)", default=_string_value(current, "gpg_home"))
        if gpg_home:
            account["gpg_home"] = _expanded_path(gpg_home)
    return account


async def _collect_email(
    prompt: PromptIO,
    name: str,
    secret_store: SecretStoreKind,
    existing: CollectedProfile | None,
) -> CollectedProfile:
    accounts: dict[str, JsonObject] = {}
    if existing is not None:
        current_accounts = EMAIL_ACCOUNTS_ADAPTER.validate_json(existing.secret_values["EMAIL_ACCOUNTS"])
        for account_name, current in sorted(current_accounts.items()):
            action = await prompt.select(
                f"Email account {account_name}",
                [("Reconfigure", "edit"), ("Keep unchanged", "keep"), ("Remove", "remove")],
            )
            if action == "edit":
                accounts[account_name] = await _reconfigure_email_account(prompt, account_name, current)
            elif action == "keep":
                accounts[account_name] = current
        if not accounts:
            prompt.message("At least one email account is required; configure a replacement account.")
    if existing is not None:
        while not accounts or await prompt.confirm("Add another email account?", default=False):
            account_name, account = await _collect_email_account(prompt, set(accounts))
            accounts[account_name] = account
    else:
        while True:
            account_name, account = await _collect_email_account(prompt, set(accounts))
            accounts[account_name] = account
            if not await prompt.confirm("Add another email account?", default=False):
                break
    value = json.dumps(accounts, separators=(",", ":"), sort_keys=True)
    record = ProfileRecord(service=ServiceKind.EMAIL, name=name, secret_store=secret_store)
    return CollectedProfile(record=record, secret_values={"EMAIL_ACCOUNTS": value})


async def _collect_filesystem(
    prompt: PromptIO,
    name: str,
    secret_store: SecretStoreKind,
    existing: CollectedProfile | None,
) -> CollectedProfile:
    default_root = existing.record.environment.get("FILESYSTEM_ROOT_DIR", "") if existing is not None else ""
    root = await _required(prompt, "Filesystem root directory", default=default_root)
    record = ProfileRecord(
        service=ServiceKind.FILESYSTEM,
        name=name,
        environment={"FILESYSTEM_ROOT_DIR": _expanded_path(root)},
        secret_store=secret_store,
    )
    return CollectedProfile(record=record)


async def _collect_navidrome(
    prompt: PromptIO,
    name: str,
    secret_store: SecretStoreKind,
    existing: CollectedProfile | None,
) -> CollectedProfile:
    environment = existing.record.environment if existing is not None else {}
    record = ProfileRecord(
        service=ServiceKind.NAVIDROME,
        name=name,
        environment={
            "NAVIDROME_URL": await _required(
                prompt,
                "Navidrome URL",
                default=environment.get("NAVIDROME_URL", "http://localhost:4533"),
            ),
            "NAVIDROME_USERNAME": await _required(
                prompt,
                "Navidrome username",
                default=environment.get("NAVIDROME_USERNAME", ""),
            ),
        },
        secret_store=secret_store,
    )
    existing_password = existing.secret_values.get("NAVIDROME_PASSWORD") if existing is not None else None
    password = await _retained_secret(prompt, "Navidrome password", existing_password)
    return CollectedProfile(record=record, secret_values={"NAVIDROME_PASSWORD": password})


async def _collect_slskd(
    prompt: PromptIO,
    name: str,
    secret_store: SecretStoreKind,
    existing: CollectedProfile | None,
) -> CollectedProfile:
    environment = existing.record.environment if existing is not None else {}
    existing_api_key = existing.secret_values.get("SLSKD_API_KEY") if existing is not None else None
    existing_password = existing.secret_values.get("SLSKD_PASSWORD") if existing is not None else None
    auth_choices = [("API key", "api-key"), ("Username/password", "password")]
    if existing_password is not None:
        auth_choices.reverse()
    auth_mode = await prompt.select("slskd authentication", auth_choices)
    record = ProfileRecord(
        service=ServiceKind.SLSKD,
        name=name,
        environment={
            "SLSKD_URL": await _required(
                prompt,
                "slskd URL",
                default=environment.get("SLSKD_URL", "http://localhost:5030"),
            )
        },
        secret_store=secret_store,
    )
    if auth_mode == "api-key":
        secrets = {"SLSKD_API_KEY": await _retained_secret(prompt, "slskd API key", existing_api_key)}
    else:
        record.environment["SLSKD_API_KEY"] = ""
        record.environment["SLSKD_USERNAME"] = await _required(
            prompt,
            "slskd username",
            default=environment.get("SLSKD_USERNAME", ""),
        )
        secrets = {"SLSKD_PASSWORD": await _retained_secret(prompt, "slskd password", existing_password)}
    return CollectedProfile(record=record, secret_values=secrets)


async def _collect_tg_export_txt(
    prompt: PromptIO,
    name: str,
    secret_store: SecretStoreKind,
    existing: CollectedProfile | None,
) -> CollectedProfile:
    environment = existing.record.environment if existing is not None else {}
    root = await _required(
        prompt,
        "Telegram TXT export root directory",
        default=environment.get("TG_EXPORT_TXT_ROOT_DIR", ""),
    )
    rg_path = await _required(
        prompt,
        "ripgrep executable",
        default=environment.get("TG_EXPORT_TXT_RG_PATH", "rg"),
    )
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
    existing: CollectedProfile | None = None,
) -> CollectedProfile:
    name = profile_name or await _profile_name(prompt)
    if service is ServiceKind.EMAIL:
        return await _collect_email(prompt, name, secret_store, existing)
    if service is ServiceKind.FILESYSTEM:
        return await _collect_filesystem(prompt, name, secret_store, existing)
    if service is ServiceKind.NAVIDROME:
        return await _collect_navidrome(prompt, name, secret_store, existing)
    if service is ServiceKind.SLSKD:
        return await _collect_slskd(prompt, name, secret_store, existing)
    return await _collect_tg_export_txt(prompt, name, secret_store, existing)
