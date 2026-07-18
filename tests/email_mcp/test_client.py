import imaplib
import smtplib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import cast
from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from email_mcp.client import EmailClient
from email_mcp.config import EmailAccountSettings, EmailSettings


def make_client() -> EmailClient:
    return EmailClient(
        EmailSettings(
            EMAIL_ACCOUNTS={
                "work": EmailAccountSettings(
                    imap_host="imap.example.com",
                    smtp_host="smtp.example.com",
                    username="alice@example.com",
                    password=SecretStr("secret"),
                    default_from_address="alice@example.com",
                )
            }
        )
    )


@contextmanager
def mocked_imap(connection: imaplib.IMAP4) -> Iterator[imaplib.IMAP4]:
    yield connection


@contextmanager
def mocked_smtp(connection: smtplib.SMTP) -> Iterator[smtplib.SMTP]:
    yield connection


def test_validate_account_checks_readonly_inbox_and_smtp_noop_without_sending() -> None:
    client = make_client()
    imap_mock = Mock(spec=imaplib.IMAP4)
    imap_mock.select.return_value = ("OK", [b"1"])
    smtp_mock = Mock(spec=smtplib.SMTP)
    smtp_mock.noop.return_value = (250, b"OK")
    imap_connection = cast(imaplib.IMAP4, imap_mock)
    smtp_connection = cast(smtplib.SMTP, smtp_mock)

    with (
        patch.object(client, "_imap", side_effect=lambda _: mocked_imap(imap_connection)),
        patch.object(client, "_smtp", side_effect=lambda _: mocked_smtp(smtp_connection)),
    ):
        client._validate_account("work")

    imap_mock.select.assert_called_once_with('"INBOX"', readonly=True)
    smtp_mock.noop.assert_called_once_with()
    smtp_mock.sendmail.assert_not_called()


def test_send_raw_uses_resolved_sender_as_smtp_envelope_from() -> None:
    client = make_client()
    smtp_mock = Mock(spec=smtplib.SMTP)
    smtp_mock.sendmail.return_value = {}
    smtp_connection = cast(smtplib.SMTP, smtp_mock)

    with patch.object(client, "_smtp", side_effect=lambda _: mocked_smtp(smtp_connection)):
        client._send_raw("work", "support@example.com", b"message", ("bob@example.com",))

    smtp_mock.sendmail.assert_called_once_with("support@example.com", ["bob@example.com"], b"message")


def test_list_messages_selects_readonly_and_fetches_peek_headers() -> None:
    client = make_client()
    connection_mock = Mock(spec=imaplib.IMAP4)
    connection_mock.select.return_value = ("OK", [b"2"])
    headers = b"Subject: Latest\r\nFrom: sender@example.com\r\nTo: alice@example.com\r\n\r\n"
    connection_mock.uid.side_effect = [
        ("OK", [b"1 2"]),
        ("OK", [(b"2 (UID 2 FLAGS (\\Seen) RFC822.SIZE 123)", headers), b")"]),
    ]
    connection = cast(imaplib.IMAP4, connection_mock)

    with patch.object(client, "_imap", side_effect=lambda _: mocked_imap(connection)):
        messages = client._search_and_fetch("work", "INBOX", ("ALL",), 20, 0)

    assert [message.uid for message in messages] == [2]
    connection_mock.select.assert_called_once_with('"INBOX"', readonly=True)
    assert connection_mock.uid.call_args_list[0].args == ("SEARCH", "ALL")
    assert "BODY.PEEK[HEADER.FIELDS" in connection_mock.uid.call_args_list[1].args[2]


def test_get_message_fetches_body_with_peek_from_readonly_mailbox() -> None:
    client = make_client()
    connection_mock = Mock(spec=imaplib.IMAP4)
    connection_mock.select.return_value = ("OK", [b"1"])
    connection_mock.uid.return_value = (
        "OK",
        [(b"1 (UID 7 FLAGS () RFC822.SIZE 18)", b"Subject: Test\r\n\r\n")],
    )
    connection = cast(imaplib.IMAP4, connection_mock)

    with patch.object(client, "_imap", side_effect=lambda _: mocked_imap(connection)):
        raw, _ = client._fetch_message("work", "INBOX", 7)

    assert raw == b"Subject: Test\r\n\r\n"
    connection_mock.select.assert_called_once_with('"INBOX"', readonly=True)
    connection_mock.uid.assert_called_once_with("FETCH", "7", "(UID FLAGS RFC822.SIZE BODY.PEEK[])")


@pytest.mark.asyncio
async def test_search_compiles_structured_filters() -> None:
    client = make_client()
    with patch.object(client, "_search_and_fetch", return_value=[]) as search_mock:
        await client.search_messages(
            "work",
            "INBOX",
            sender="sender@example.com",
            recipient=None,
            subject="release",
            text=None,
            since=date(2026, 7, 1),
            before=date(2026, 8, 1),
            unread_only=True,
            limit=10,
            offset=5,
        )

    assert search_mock.call_args.args == (
        "work",
        "INBOX",
        (
            "FROM",
            '"sender@example.com"',
            "SUBJECT",
            '"release"',
            "SINCE",
            "01-Jul-2026",
            "BEFORE",
            "01-Aug-2026",
            "UNSEEN",
        ),
        10,
        5,
    )
