import base64
import binascii
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, getaddresses, make_msgid

from email_mcp.config import EmailAccountSettings, EmailSettings
from email_mcp.models import DecodedAttachment, OutgoingAttachment
from mcp_common import UpstreamValidationError

SMTP_POLICY = policy.SMTP.clone(max_line_length=78)
MESSAGE_ID_PATTERN = re.compile(r"^<[^<>\s]+>$")


@dataclass(frozen=True)
class PreparedAddresses:
    to_headers: tuple[str, ...]
    cc_headers: tuple[str, ...]
    bcc_headers: tuple[str, ...]
    envelope: tuple[str, ...]


@dataclass(frozen=True)
class PreparedMessage:
    raw: bytes
    sender: str
    message_id: str
    recipients: tuple[str, ...]
    attachment_count: int
    signed: bool


def _validate_address(value: str) -> tuple[str, str]:
    if "\r" in value or "\n" in value or "\x00" in value:
        raise UpstreamValidationError("Email addresses must not contain control characters.")
    parsed = getaddresses([value])
    if len(parsed) != 1:
        raise UpstreamValidationError(f"Expected one email address, got {value!r}.")
    name, address = parsed[0]
    if not address or "@" not in address or address.startswith("@") or address.endswith("@"):
        raise UpstreamValidationError(f"Invalid email address: {value!r}.")
    return formataddr((name, address)), address


def prepare_addresses(
    to: list[str],
    cc: list[str] | None,
    bcc: list[str] | None,
    *,
    max_recipients: int,
) -> PreparedAddresses:
    if not to:
        raise UpstreamValidationError("At least one To recipient is required.")

    def parse_many(values: list[str] | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
        pairs = tuple(_validate_address(value) for value in values or [])
        return tuple(pair[0] for pair in pairs), tuple(pair[1] for pair in pairs)

    to_headers, to_envelope = parse_many(to)
    cc_headers, cc_envelope = parse_many(cc)
    bcc_headers, bcc_envelope = parse_many(bcc)
    envelope = to_envelope + cc_envelope + bcc_envelope
    if len(envelope) > max_recipients:
        raise UpstreamValidationError(f"Recipient count exceeds the limit of {max_recipients}.")
    if len({address.casefold() for address in envelope}) != len(envelope):
        raise UpstreamValidationError("Duplicate recipients are not allowed across To, Cc, and Bcc.")
    return PreparedAddresses(to_headers, cc_headers, bcc_headers, envelope)


def decode_attachments(
    attachments: list[OutgoingAttachment] | None,
    settings: EmailSettings,
) -> tuple[DecodedAttachment, ...]:
    decoded: list[DecodedAttachment] = []
    total_size = 0
    for attachment in attachments or []:
        if "/" not in attachment.content_type:
            raise UpstreamValidationError(f"Invalid attachment content type: {attachment.content_type!r}.")
        try:
            data = base64.b64decode(attachment.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise UpstreamValidationError(f"Attachment {attachment.filename!r} is not valid base64.") from exc
        if len(data) > settings.email_max_attachment_bytes:
            raise UpstreamValidationError(
                f"Attachment {attachment.filename!r} is {len(data)} bytes; "
                f"limit is {settings.email_max_attachment_bytes} bytes.",
            )
        total_size += len(data)
        if total_size > settings.email_max_total_attachment_bytes:
            raise UpstreamValidationError(
                f"Total attachment size exceeds {settings.email_max_total_attachment_bytes} bytes.",
            )
        decoded.append(
            DecodedAttachment(
                filename=attachment.filename,
                content_type=attachment.content_type,
                disposition=attachment.disposition,
                content_id=attachment.content_id,
                data=data,
            )
        )
    return tuple(decoded)


def _populate_body(
    message: EmailMessage,
    text_body: str,
    html_body: str | None,
    attachments: tuple[DecodedAttachment, ...],
) -> None:
    message.set_content(text_body)
    if html_body is not None:
        message.add_alternative(html_body, subtype="html")
    for attachment in attachments:
        maintype, subtype = attachment.content_type.split("/", 1)
        if attachment.content_id is not None:
            message.add_attachment(
                attachment.data,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
                disposition=attachment.disposition.value,
                cid=f"<{attachment.content_id.strip('<>')}>",
            )
        else:
            message.add_attachment(
                attachment.data,
                maintype=maintype,
                subtype=subtype,
                filename=attachment.filename,
                disposition=attachment.disposition.value,
            )


def build_body(
    text_body: str,
    html_body: str | None,
    attachments: tuple[DecodedAttachment, ...],
    *,
    max_body_chars: int,
) -> EmailMessage:
    if len(text_body) > max_body_chars or (html_body is not None and len(html_body) > max_body_chars):
        raise UpstreamValidationError(f"Message body exceeds the limit of {max_body_chars} characters.")
    body = EmailMessage(policy=SMTP_POLICY)
    _populate_body(body, text_body, html_body, attachments)
    return body


def serialize_body(body: EmailMessage) -> bytes:
    return body.as_bytes(policy=SMTP_POLICY)


def _set_headers(  # noqa: PLR0913
    message: EmailMessage,
    account: EmailAccountSettings,
    from_address: str | None,
    addresses: PreparedAddresses,
    subject: str,
    reply_to: str | None,
    in_reply_to: str | None,
    references: tuple[str, ...],
) -> tuple[str, str]:
    if "\r" in subject or "\n" in subject:
        raise UpstreamValidationError("Subject must not contain newlines.")
    sender_value = from_address.strip() if from_address is not None else account.default_from_address
    sender_header, sender_address = _validate_address(sender_value)
    if sender_header != sender_address:
        raise UpstreamValidationError("from_address must contain one bare email address.")
    message_id = make_msgid()
    message["From"] = formataddr((account.from_name or "", sender_address))
    message["To"] = ", ".join(addresses.to_headers)
    if addresses.cc_headers:
        message["Cc"] = ", ".join(addresses.cc_headers)
    if reply_to is not None:
        reply_header, _ = _validate_address(reply_to)
        message["Reply-To"] = reply_header
    if in_reply_to is not None:
        _validate_message_id(in_reply_to)
        message["In-Reply-To"] = in_reply_to
    if references:
        for reference in references:
            _validate_message_id(reference)
        message["References"] = " ".join(dict.fromkeys(references))
    message["Subject"] = subject
    message["Date"] = format_datetime(datetime.now(UTC))
    message["Message-ID"] = message_id
    return message_id, sender_address


def _validate_message_id(value: str) -> None:
    if MESSAGE_ID_PATTERN.fullmatch(value) is None:
        raise UpstreamValidationError(f"Invalid RFC message identifier: {value!r}.")


def build_message(  # noqa: PLR0913
    account: EmailAccountSettings,
    addresses: PreparedAddresses,
    subject: str,
    reply_to: str | None,
    body: EmailMessage,
    attachments: tuple[DecodedAttachment, ...],
    signature: bytes | None,
    *,
    from_address: str | None = None,
    in_reply_to: str | None = None,
    references: tuple[str, ...] = (),
) -> PreparedMessage:
    if signature is None:
        message = body
        message_id, sender = _set_headers(
            message,
            account,
            from_address,
            addresses,
            subject,
            reply_to,
            in_reply_to,
            references,
        )
    else:
        message = EmailMessage(policy=SMTP_POLICY)
        message_id, sender = _set_headers(
            message,
            account,
            from_address,
            addresses,
            subject,
            reply_to,
            in_reply_to,
            references,
        )
        message.set_type("multipart/signed")
        message.set_param("protocol", "application/pgp-signature")
        message.set_param("micalg", "pgp-sha256")
        message.attach(body)
        signature_part = EmailMessage(policy=SMTP_POLICY)
        signature_part.set_type("application/pgp-signature")
        signature_part.set_param("name", "signature.asc")
        signature_part["Content-Description"] = "OpenPGP digital signature"
        signature_part["Content-Disposition"] = 'attachment; filename="signature.asc"'
        signature_part["Content-Transfer-Encoding"] = "7bit"
        signature_part.set_payload(signature.decode("ascii"))
        message.attach(signature_part)
    return PreparedMessage(
        raw=message.as_bytes(policy=SMTP_POLICY),
        sender=sender,
        message_id=message_id,
        recipients=addresses.envelope,
        attachment_count=len(attachments),
        signed=signature is not None,
    )
