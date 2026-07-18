import asyncio
import base64
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path
from typing import cast

import pytest
from pydantic import SecretStr

from email_mcp.config import EmailAccountSettings, EmailSettings
from email_mcp.mime import build_body, build_message, decode_attachments, prepare_addresses, serialize_body
from email_mcp.models import OutgoingAttachment
from email_mcp.signing import GpgSigner
from mcp_common import UpstreamValidationError


def make_settings(*, gpg_key_fingerprint: str | None = None, gpg_home: str | None = None) -> EmailSettings:
    account = EmailAccountSettings(
        imap_host="imap.example.com",
        smtp_host="smtp.example.com",
        username="alice@example.com",
        password=SecretStr("secret"),
        default_from_address="alice@example.com",
        gpg_key_fingerprint=gpg_key_fingerprint,
        gpg_home=Path(gpg_home) if gpg_home is not None else None,
    )
    return EmailSettings(EMAIL_ACCOUNTS={"work": account})


@pytest.fixture
def short_gpg_home() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="mcp-gpg-", dir="/tmp") as directory:
        path = Path(directory)
        path.chmod(0o700)
        gpgconf = shutil.which("gpgconf")
        if gpgconf is not None:
            subprocess.run(  # noqa: S603
                [gpgconf, "--homedir", str(path), "--launch", "gpg-agent"],
                check=False,
                capture_output=True,
            )
        try:
            yield path
        finally:
            if gpgconf is not None:
                subprocess.run(  # noqa: S603
                    [gpgconf, "--homedir", str(path), "--kill", "gpg-agent"],
                    check=False,
                    capture_output=True,
                )


def test_unsigned_message_has_mime_attachment_and_no_bcc_header() -> None:
    settings = make_settings()
    attachments = decode_attachments(
        [
            OutgoingAttachment(
                filename="note.txt",
                content_type="text/plain",
                content_base64=base64.b64encode(b"attachment body").decode(),
            )
        ],
        settings,
    )
    body = build_body("plain body", "<p>HTML body</p>", attachments, max_body_chars=1000)
    addresses = prepare_addresses(
        ["Bob <bob@example.com>"],
        ["copy@example.com"],
        ["hidden@example.com"],
        max_recipients=10,
    )

    prepared = build_message(settings.account("work"), addresses, "Subject", None, body, attachments, None)
    parsed = BytesParser(policy=policy.default).parsebytes(prepared.raw)

    assert parsed["Bcc"] is None
    assert parsed["From"] == "alice@example.com"
    assert prepared.sender == "alice@example.com"
    assert prepared.recipients == ("bob@example.com", "copy@example.com", "hidden@example.com")
    attachment = next(part for part in parsed.walk() if part.get_filename() == "note.txt")
    assert attachment.get_payload(decode=True) == b"attachment body"


def test_message_can_override_default_from_address() -> None:
    settings = make_settings()
    body = build_body("body", None, (), max_body_chars=1000)
    addresses = prepare_addresses(["bob@example.com"], None, None, max_recipients=10)

    prepared = build_message(
        settings.account("work"),
        addresses,
        "Subject",
        None,
        body,
        (),
        None,
        from_address="support@example.com",
    )
    parsed = BytesParser(policy=policy.default).parsebytes(prepared.raw)

    assert parsed["From"] == "support@example.com"
    assert prepared.sender == "support@example.com"


def test_message_rejects_non_bare_from_override() -> None:
    settings = make_settings()
    body = build_body("body", None, (), max_body_chars=1000)
    addresses = prepare_addresses(["bob@example.com"], None, None, max_recipients=10)

    with pytest.raises(UpstreamValidationError, match="bare email address"):
        build_message(
            settings.account("work"),
            addresses,
            "Subject",
            None,
            body,
            (),
            None,
            from_address="Support <support@example.com>",
        )


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("RUN_GPG_INTEGRATION") != "1",
    reason="set RUN_GPG_INTEGRATION=1 to run the external GPG integration test",
)
async def test_openpgp_mime_signature_verifies(tmp_path: Path, short_gpg_home: Path) -> None:
    gpg = shutil.which("gpg")
    if gpg is None:
        pytest.fail("RUN_GPG_INTEGRATION=1 requires gpg to be installed")
    gpg_home = short_gpg_home
    keygen = await asyncio.to_thread(
        subprocess.run,
        [
            gpg,
            "--batch",
            "--homedir",
            str(gpg_home),
            "--passphrase",
            "",
            "--quick-generate-key",
            "MCP Test <mcp@example.com>",
            "ed25519",
            "sign",
            "0",
        ],
        check=False,
        capture_output=True,
    )
    if keygen.returncode != 0:
        pytest.fail(f"gpg key generation failed: {keygen.stderr.decode(errors='replace').strip()}")
    listing_result = await asyncio.to_thread(
        subprocess.run,
        [gpg, "--batch", "--homedir", str(gpg_home), "--with-colons", "--list-secret-keys"],
        check=True,
        capture_output=True,
    )
    listing = listing_result.stdout.decode()
    fingerprint = next(line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr:"))
    settings = make_settings(gpg_key_fingerprint=fingerprint, gpg_home=str(gpg_home))
    body = build_body("signed body", None, (), max_body_chars=1000)

    signature = await GpgSigner(settings).sign(settings.account("work"), serialize_body(body))
    prepared = build_message(
        settings.account("work"),
        prepare_addresses(["bob@example.com"], None, None, max_recipients=10),
        "Signed subject",
        None,
        body,
        (),
        signature,
    )
    parsed = BytesParser(policy=policy.SMTP).parsebytes(prepared.raw)
    payload = parsed.get_payload()
    assert isinstance(payload, list)
    parts = cast(list[EmailMessage], payload)
    signed_part = parts[0].as_bytes(policy=policy.SMTP.clone(max_line_length=78))
    detached_signature = parts[1].get_payload(decode=True)
    assert isinstance(detached_signature, bytes)
    body_path = tmp_path / "signed-body.mime"
    signature_path = tmp_path / "signature.asc"
    body_path.write_bytes(signed_part)
    signature_path.write_bytes(detached_signature)

    verified = await asyncio.to_thread(
        subprocess.run,
        [gpg, "--batch", "--homedir", str(gpg_home), "--verify", str(signature_path), str(body_path)],
        check=False,
        capture_output=True,
    )

    assert parsed.get_content_type() == "multipart/signed"
    assert verified.returncode == 0, verified.stderr.decode()
