import base64
from email import policy
from email.parser import BytesParser
from unittest.mock import AsyncMock

import pytest
from mcp.types import BlobResourceContents
from pydantic import SecretStr

from email_mcp.client import EmailClient
from email_mcp.config import EmailAccountSettings, EmailSettings
from email_mcp.models import Attachment, MessageSummary, ParsedMessage
from email_mcp.service import EmailService
from email_mcp.signing import GpgSigner
from mcp_common import UpstreamServerError, UpstreamValidationError


def make_settings(*, fingerprint: str | None = None) -> EmailSettings:
    account = EmailAccountSettings(
        imap_host="imap.example.com",
        smtp_host="smtp.example.com",
        username="alice@example.com",
        password=SecretStr("secret"),
        default_from_address="alice@example.com",
        gpg_key_fingerprint=fingerprint,
    )
    return EmailSettings(EMAIL_ACCOUNTS={"work": account})


@pytest.mark.asyncio
async def test_get_attachment_returns_binary_embedded_resource() -> None:
    settings = make_settings()
    client = AsyncMock(spec=EmailClient)
    client.get_message.return_value = ParsedMessage(
        summary=MessageSummary(7, "subject", "sender", "to", None, None, (), 12),
        cc="",
        body="body",
        body_format="plain",
        attachments=(Attachment(1, "data.bin", "application/octet-stream", "attachment", None, b"\x00\x01"),),
    )
    service = EmailService(settings, client=client)

    result = await service.get_attachment("work", "INBOX", 7, 1)

    assert isinstance(result.resource, BlobResourceContents)
    assert result.resource.mimeType == "application/octet-stream"
    assert result.resource.blob == base64.b64encode(b"\x00\x01").decode()


@pytest.mark.asyncio
async def test_signing_failure_prevents_smtp_submission() -> None:
    settings = make_settings(fingerprint="A" * 40)
    client = AsyncMock(spec=EmailClient)
    signer = AsyncMock(spec=GpgSigner)
    signer.sign.side_effect = UpstreamServerError("signing failed")
    service = EmailService(settings, client=client, signer=signer)

    with pytest.raises(UpstreamServerError, match="signing failed"):
        await service.send_message(
            "work",
            ["bob@example.com"],
            "subject",
            "body",
            cc=None,
            bcc=None,
            html_body=None,
            from_address=None,
            reply_to=None,
            attachments=None,
            sign=None,
        )

    client.send_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_uses_custom_from_for_header_and_smtp_envelope() -> None:
    settings = make_settings()
    client = AsyncMock(spec=EmailClient)
    service = EmailService(settings, client=client)

    await service.send_message(
        "work",
        ["bob@example.com"],
        "subject",
        "body",
        cc=None,
        bcc=None,
        html_body=None,
        from_address="support@example.com",
        reply_to=None,
        attachments=None,
        sign=None,
    )

    account, sender, raw_message, recipients = client.send_raw.await_args.args
    parsed = BytesParser(policy=policy.default).parsebytes(raw_message)
    assert account == "work"
    assert sender == "support@example.com"
    assert parsed["From"] == "support@example.com"
    assert recipients == ("bob@example.com",)


@pytest.mark.asyncio
async def test_reply_all_derives_recipients_and_serializes_thread_headers() -> None:
    settings = make_settings()
    client = AsyncMock(spec=EmailClient)
    client.get_message.return_value = ParsedMessage(
        summary=MessageSummary(
            7,
            "Re: Status",
            "Sender <sender@example.com>",
            "alice@example.com, Teammate <team@example.com>",
            None,
            "<source@example.com>",
            (),
            100,
        ),
        cc="Copy <copy@example.com>, Help <help@example.com>",
        body="source body",
        body_format="plain",
        attachments=(),
        reply_to="Help <help@example.com>",
        in_reply_to=("<root@example.com>",),
        references=("<root@example.com>",),
    )
    service = EmailService(settings, client=client)

    result = await service.reply_message(
        "work",
        "INBOX",
        7,
        "reply body",
        reply_all=True,
        bcc=None,
        html_body=None,
        from_address=None,
        reply_to=None,
        attachments=None,
        sign=None,
    )

    account, sender, raw_message, recipients = client.send_raw.await_args.args
    parsed = BytesParser(policy=policy.default).parsebytes(raw_message)
    assert account == "work"
    assert sender == "alice@example.com"
    assert parsed["To"] == "Help <help@example.com>"
    assert parsed["Cc"] == "Teammate <team@example.com>, Copy <copy@example.com>"
    assert parsed["Subject"] == "Re: Status"
    assert parsed["In-Reply-To"] == "<source@example.com>"
    assert parsed["References"] == "<root@example.com> <source@example.com>"
    assert recipients == ("help@example.com", "team@example.com", "copy@example.com")
    assert "INBOX UID 7 (<source@example.com>)" in result


@pytest.mark.asyncio
async def test_reply_requires_source_message_id_before_smtp_submission() -> None:
    settings = make_settings()
    client = AsyncMock(spec=EmailClient)
    client.get_message.return_value = ParsedMessage(
        summary=MessageSummary(7, "Subject", "sender@example.com", "alice@example.com", None, None, (), 100),
        cc="",
        body="source body",
        body_format="plain",
        attachments=(),
    )
    service = EmailService(settings, client=client)

    with pytest.raises(UpstreamValidationError, match="no valid Message-ID"):
        await service.reply_message(
            "work",
            "INBOX",
            7,
            "reply body",
            reply_all=False,
            bcc=None,
            html_body=None,
            from_address=None,
            reply_to=None,
            attachments=None,
            sign=None,
        )

    client.send_raw.assert_not_awaited()
