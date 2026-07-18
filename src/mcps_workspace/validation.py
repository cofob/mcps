import asyncio
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx

from email_mcp.client import EmailClient
from email_mcp.config import EmailSettings
from email_mcp.signing import GpgSigner
from filesystem_mcp.config import FilesystemSettings
from mcp_common import create_async_client, get_object, get_str
from mcps_workspace.models import CollectedProfile, ServiceKind
from navidrome_mcp.client import NavidromeClient
from navidrome_mcp.config import NavidromeSettings
from slskd_mcp.client import SlskdClient
from slskd_mcp.config import SlskdSettings
from tg_export_txt_mcp.config import TgExportTxtSettings


class ProfileValidationError(RuntimeError):
    pass


@contextmanager
def _temporary_environment(values: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _combined_environment(collected: CollectedProfile) -> dict[str, str]:
    return (
        collected.record.environment
        | collected.secret_values
        | {
            "MCP_TRANSPORT": "stdio",
            "MCP_AUTH_MODE": "none",
        }
    )


async def _validate_email(collected: CollectedProfile) -> None:
    with _temporary_environment(_combined_environment(collected)):
        settings = EmailSettings.from_env()
    client = EmailClient(settings)
    signer = GpgSigner(settings)
    for account_name, account in settings.email_accounts.items():
        await client.validate_account(account_name)
        if account.gpg_key_fingerprint is not None:
            await signer.sign(account, b"mcps installer signing validation\r\n")


async def _validate_navidrome(collected: CollectedProfile) -> None:
    with _temporary_environment(_combined_environment(collected)):
        settings = NavidromeSettings.from_env()
    async with create_async_client(
        base_url=str(settings.navidrome_url),
        timeout_seconds=settings.timeout_seconds,
    ) as http_client:
        payload = await NavidromeClient(settings, http_client).call("ping")
    response = get_object(payload, "subsonic-response", context="Subsonic ping")
    if get_str(response, "status") != "ok":
        message = get_str(get_object(response, "error", context="Subsonic ping"), "message")
        raise ProfileValidationError(message or "Navidrome rejected the Subsonic credentials.")


async def _validate_slskd(collected: CollectedProfile) -> None:
    with _temporary_environment(_combined_environment(collected)):
        settings = SlskdSettings.from_env()
    async with create_async_client(
        base_url=str(settings.slskd_url),
        timeout_seconds=settings.timeout_seconds,
    ) as http_client:
        await SlskdClient(settings, http_client).request("GET", "/api/v0/application")


def _validate_filesystem(collected: CollectedProfile) -> None:
    with _temporary_environment(_combined_environment(collected)):
        settings = FilesystemSettings.from_env()
    if not os.access(settings.filesystem_root_dir, os.R_OK):
        raise ProfileValidationError(f"Directory is not readable: {settings.filesystem_root_dir}")


def _validate_tg_export_txt(collected: CollectedProfile) -> list[str]:
    with _temporary_environment(_combined_environment(collected)):
        settings = TgExportTxtSettings.from_env()
    if not os.access(settings.export_root_dir, os.R_OK):
        raise ProfileValidationError(f"Directory is not readable: {settings.export_root_dir}")
    rg_path = Path(settings.rg_path)
    if rg_path.parent != Path():
        if not rg_path.is_file() or not os.access(rg_path, os.X_OK):
            raise ProfileValidationError(f"rg executable is unavailable: {settings.rg_path}")
    elif shutil.which(settings.rg_path) is None:
        raise ProfileValidationError(f"rg executable is unavailable: {settings.rg_path}")
    if not any(settings.export_root_dir.rglob("*.txt")):
        return [f"No .txt exports were found under {settings.export_root_dir}."]
    return []


async def validate_profile(collected: CollectedProfile) -> list[str]:
    try:
        if collected.record.service is ServiceKind.EMAIL:
            await _validate_email(collected)
        elif collected.record.service is ServiceKind.NAVIDROME:
            await _validate_navidrome(collected)
        elif collected.record.service is ServiceKind.SLSKD:
            await _validate_slskd(collected)
        elif collected.record.service is ServiceKind.FILESYSTEM:
            await asyncio.to_thread(_validate_filesystem, collected)
        else:
            return await asyncio.to_thread(_validate_tg_export_txt, collected)
    except ProfileValidationError:
        raise
    except (ValueError, OSError, TimeoutError, httpx.HTTPError) as exc:
        raise ProfileValidationError(_sanitize_error(exc)) from exc
    except Exception as exc:
        raise ProfileValidationError(_sanitize_error(exc)) from exc
    return []


def _sanitize_error(error: Exception) -> str:
    text = str(error).strip().replace("\r", " ").replace("\n", " ")
    return text[:500] or error.__class__.__name__
