import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import respx
from httpx import Response

from mcps_workspace import validation
from mcps_workspace.models import CollectedProfile, ProfileRecord, ServiceKind


@pytest.mark.asyncio
async def test_email_validation_checks_imap_and_smtp_without_sending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validate_account = AsyncMock()

    class FakeEmailClient:
        def __init__(self, settings: validation.EmailSettings) -> None:
            del settings

        async def validate_account(self, account_name: str) -> None:
            await validate_account(account_name)

    monkeypatch.setattr(validation, "EmailClient", FakeEmailClient)
    accounts = {
        "personal": {
            "imap_host": "imap.example.com",
            "smtp_host": "smtp.example.com",
            "username": "alice@example.com",
            "password": "secret",
            "default_from_address": "alice@example.com",
        }
    }
    collected = CollectedProfile(
        record=ProfileRecord(service=ServiceKind.EMAIL, name="personal"),
        secret_values={"EMAIL_ACCOUNTS": json.dumps(accounts)},
    )

    await validation.validate_profile(collected)

    validate_account.assert_awaited_once_with("personal")


@pytest.mark.asyncio
@respx.mock
async def test_navidrome_validation_uses_authenticated_ping() -> None:
    route = respx.get("https://music.example/rest/ping").mock(
        return_value=Response(200, json={"subsonic-response": {"status": "ok"}})
    )
    collected = CollectedProfile(
        record=ProfileRecord(
            service=ServiceKind.NAVIDROME,
            name="home",
            environment={"NAVIDROME_URL": "https://music.example", "NAVIDROME_USERNAME": "alice"},
        ),
        secret_values={"NAVIDROME_PASSWORD": "secret"},
    )

    await validation.validate_profile(collected)

    assert route.called
    assert "u=alice" in str(route.calls.last.request.url)


@pytest.mark.asyncio
@respx.mock
async def test_slskd_validation_uses_read_only_application_endpoint() -> None:
    route = respx.get("https://slskd.example/api/v0/application").mock(return_value=Response(200, json={}))
    collected = CollectedProfile(
        record=ProfileRecord(
            service=ServiceKind.SLSKD,
            name="home",
            environment={"SLSKD_URL": "https://slskd.example"},
        ),
        secret_values={"SLSKD_API_KEY": "key"},
    )

    await validation.validate_profile(collected)

    assert route.calls.last.request.headers["Authorization"] == "Bearer key"


@pytest.mark.asyncio
async def test_telegram_validation_warns_when_no_txt_files(tmp_path: Path) -> None:
    collected = CollectedProfile(
        record=ProfileRecord(
            service=ServiceKind.TG_EXPORT_TXT,
            name="empty",
            environment={"TG_EXPORT_TXT_ROOT_DIR": str(tmp_path), "TG_EXPORT_TXT_RG_PATH": "rg"},
        )
    )

    warnings = await validation.validate_profile(collected)

    assert warnings == [f"No .txt exports were found under {tmp_path}."]
