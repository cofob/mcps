import json

import pytest
from pydantic import SecretStr, ValidationError

from email_mcp.config import EmailAccountSettings, EmailSettings, TlsMode
from mcp_common import TransportMode


def test_email_settings_parse_named_accounts_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "EMAIL_ACCOUNTS",
        json.dumps(
            {
                "personal": {
                    "imap_host": "imap.example.com",
                    "smtp_host": "smtp.example.com",
                    "username": "alice@example.com",
                    "password": "secret",
                    "from_address": "alice@example.com",
                }
            }
        ),
    )

    settings = EmailSettings.from_env()

    account = settings.account("personal")
    assert account.imap_tls is TlsMode.IMPLICIT
    assert account.smtp_tls is TlsMode.STARTTLS
    assert account.resolved_smtp_username == "alice@example.com"
    assert account.resolved_smtp_password.get_secret_value() == "secret"
    assert settings.mcp_transport is TransportMode.STDIO


def test_email_settings_require_paired_smtp_credentials() -> None:
    with pytest.raises(ValidationError, match="both smtp_username and smtp_password"):
        EmailAccountSettings(
            imap_host="imap.example.com",
            smtp_host="smtp.example.com",
            username="alice@example.com",
            password=SecretStr("secret"),
            smtp_username="relay-user",
            from_address="alice@example.com",
        )


def test_email_settings_reject_short_gpg_key_id() -> None:
    with pytest.raises(ValidationError, match="full 40- or 64-character"):
        EmailAccountSettings(
            imap_host="imap.example.com",
            smtp_host="smtp.example.com",
            username="alice@example.com",
            password=SecretStr("secret"),
            from_address="alice@example.com",
            gpg_key_fingerprint="DEADBEEF",
        )


def test_email_settings_hide_passwords_in_repr() -> None:
    settings = EmailSettings(
        EMAIL_ACCOUNTS={
            "work": EmailAccountSettings(
                imap_host="imap.example.com",
                smtp_host="smtp.example.com",
                username="alice@example.com",
                password=SecretStr("top-secret-value"),
                from_address="alice@example.com",
            )
        },
    )

    assert "top-secret-value" not in repr(settings)
