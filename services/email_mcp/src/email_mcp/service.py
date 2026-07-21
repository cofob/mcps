import base64
import re
from datetime import date
from email.utils import formataddr, getaddresses
from urllib.parse import quote

from mcp.types import BlobResourceContents, EmbeddedResource
from pydantic import AnyUrl

from email_mcp.client import EmailClient
from email_mcp.config import EmailSettings
from email_mcp.formatters import (
    format_accounts,
    format_folders,
    format_message,
    format_messages,
    format_reply_sent,
    format_sent,
    format_thread,
)
from email_mcp.mime import (
    MESSAGE_ID_PATTERN,
    PreparedMessage,
    build_body,
    build_message,
    decode_attachments,
    prepare_addresses,
    serialize_body,
)
from email_mcp.models import OutgoingAttachment, ParsedMessage
from email_mcp.signing import GpgSigner
from mcp_common import UpstreamValidationError

REPLY_SUBJECT_PATTERN = re.compile(r"^\s*re\s*:", re.IGNORECASE)


def _parsed_addresses(value: str) -> list[tuple[str, str]]:
    addresses: list[tuple[str, str]] = []
    for name, address in getaddresses([value]):
        stripped = address.strip()
        if not stripped or "@" not in stripped or stripped.startswith("@") or stripped.endswith("@"):
            continue
        addresses.append((formataddr((name, stripped)), stripped.casefold()))
    return addresses


def _unique_addresses(
    candidates: list[tuple[str, str]],
    *,
    excluded: set[str],
) -> list[tuple[str, str]]:
    unique: list[tuple[str, str]] = []
    seen = set(excluded)
    for header, address in candidates:
        if address not in seen:
            seen.add(address)
            unique.append((header, address))
    return unique


def _reply_recipients(
    message: ParsedMessage,
    own_addresses: set[str],
    *,
    reply_all: bool,
) -> tuple[list[str], list[str]]:
    reply_targets = _parsed_addresses(message.reply_to) if message.reply_to else []
    if not reply_targets:
        reply_targets = _parsed_addresses(message.summary.sender)
    reply_targets = _unique_addresses(reply_targets, excluded=own_addresses)
    original_to = _unique_addresses(_parsed_addresses(message.summary.recipients), excluded=own_addresses)
    original_cc = _unique_addresses(_parsed_addresses(message.cc), excluded=own_addresses)

    if reply_targets:
        to_pairs = reply_targets
        other_pairs = original_to + original_cc if reply_all else []
    else:
        to_pairs = original_to
        other_pairs = original_cc if reply_all else []
    if not to_pairs:
        raise UpstreamValidationError("The source message does not contain a valid external reply recipient.")
    to_addresses = {address for _, address in to_pairs}
    cc_pairs = _unique_addresses(other_pairs, excluded=own_addresses | to_addresses)
    return [header for header, _ in to_pairs], [header for header, _ in cc_pairs]


def _reply_subject(subject: str) -> str:
    if REPLY_SUBJECT_PATTERN.match(subject):
        return subject
    return f"Re: {subject}" if subject else "Re:"


class EmailService:
    def __init__(
        self,
        settings: EmailSettings,
        client: EmailClient | None = None,
        signer: GpgSigner | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or EmailClient(settings)
        self._signer = signer or GpgSigner(settings)

    def list_accounts(self) -> str:
        return format_accounts(self._settings)

    async def list_folders(self, account: str) -> str:
        folders = await self._client.list_folders(account)
        return format_folders(account, folders)

    async def list_messages(
        self,
        account: str,
        folder: str,
        limit: int,
        offset: int,
    ) -> str:
        messages = await self._client.list_messages(account, folder, limit=limit, offset=offset)
        return format_messages(account, folder, messages)

    async def search_messages(  # noqa: PLR0913
        self,
        account: str,
        folder: str,
        *,
        sender: str | None,
        recipient: str | None,
        subject: str | None,
        text: str | None,
        since: date | None,
        before: date | None,
        unread_only: bool,
        limit: int,
        offset: int,
    ) -> str:
        messages = await self._client.search_messages(
            account,
            folder,
            sender=sender,
            recipient=recipient,
            subject=subject,
            text=text,
            since=since,
            before=before,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )
        return format_messages(account, folder, messages)

    async def get_message(self, account: str, folder: str, uid: int) -> str:
        message = await self._client.get_message(account, folder, uid)
        return format_message(account, folder, message)

    async def get_thread(self, account: str, folder: str, uid: int, limit: int) -> str:
        messages = await self._client.get_thread(account, folder, uid, limit=limit)
        return format_thread(account, folder, uid, messages)

    async def get_attachment(
        self,
        account: str,
        folder: str,
        uid: int,
        attachment_index: int,
    ) -> EmbeddedResource:
        message = await self._client.get_message(account, folder, uid)
        try:
            attachment = next(item for item in message.attachments if item.index == attachment_index)
        except StopIteration as exc:
            raise UpstreamValidationError(
                f"Attachment index {attachment_index} was not found on message UID {uid}.",
            ) from exc
        if attachment.size_bytes > self._settings.email_max_attachment_bytes:
            raise UpstreamValidationError(
                f"Attachment is {attachment.size_bytes} bytes; "
                f"limit is {self._settings.email_max_attachment_bytes} bytes.",
            )
        uri = (
            f"email://{quote(account, safe='')}/{quote(folder, safe='')}/{uid}/"
            f"attachments/{attachment.index}/{quote(attachment.filename, safe='')}"
        )
        return EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(
                uri=AnyUrl(uri),
                mimeType=attachment.content_type,
                blob=base64.b64encode(attachment.data).decode("ascii"),
            ),
        )

    async def send_message(  # noqa: PLR0913
        self,
        account: str,
        to: list[str],
        subject: str,
        text_body: str,
        *,
        cc: list[str] | None,
        bcc: list[str] | None,
        html_body: str | None,
        from_address: str | None,
        reply_to: str | None,
        attachments: list[OutgoingAttachment] | None,
        sign: bool | None,
    ) -> str:
        prepared = await self._prepare_message(
            account,
            to,
            subject,
            text_body,
            cc=cc,
            bcc=bcc,
            html_body=html_body,
            from_address=from_address,
            reply_to=reply_to,
            attachments=attachments,
            sign=sign,
        )
        await self._client.send_raw(account, prepared.sender, prepared.raw, prepared.recipients)
        return format_sent(
            account,
            prepared.sender,
            prepared.message_id,
            prepared.recipients,
            signed=prepared.signed,
            attachment_count=prepared.attachment_count,
        )

    async def reply_message(  # noqa: PLR0913
        self,
        account: str,
        folder: str,
        uid: int,
        text_body: str,
        *,
        reply_all: bool,
        bcc: list[str] | None,
        html_body: str | None,
        from_address: str | None,
        reply_to: str | None,
        attachments: list[OutgoingAttachment] | None,
        sign: bool | None,
    ) -> str:
        try:
            account_settings = self._settings.account(account)
        except ValueError as exc:
            raise UpstreamValidationError(str(exc)) from exc
        source = await self._client.get_message(account, folder, uid)
        source_message_id = (source.summary.message_id or "").strip()
        if MESSAGE_ID_PATTERN.fullmatch(source_message_id) is None:
            raise UpstreamValidationError(
                f"Message UID {uid} has no valid Message-ID header and cannot be sent as a threaded reply.",
            )
        own_addresses = {
            account_settings.default_from_address.casefold(),
            account_settings.username.casefold(),
        }
        if from_address is not None:
            own_addresses.add(from_address.strip().casefold())
        to, cc = _reply_recipients(source, own_addresses, reply_all=reply_all)
        prior_references = source.references or source.in_reply_to
        references = tuple(dict.fromkeys((*prior_references, source_message_id)))
        prepared = await self._prepare_message(
            account,
            to,
            _reply_subject(source.summary.subject),
            text_body,
            cc=cc,
            bcc=bcc,
            html_body=html_body,
            from_address=from_address,
            reply_to=reply_to,
            attachments=attachments,
            sign=sign,
            in_reply_to=source_message_id,
            references=references,
        )
        await self._client.send_raw(account, prepared.sender, prepared.raw, prepared.recipients)
        return format_reply_sent(
            account,
            folder,
            uid,
            source_message_id,
            prepared.sender,
            prepared.message_id,
            prepared.recipients,
            signed=prepared.signed,
            attachment_count=prepared.attachment_count,
        )

    async def _prepare_message(  # noqa: PLR0913
        self,
        account: str,
        to: list[str],
        subject: str,
        text_body: str,
        *,
        cc: list[str] | None,
        bcc: list[str] | None,
        html_body: str | None,
        from_address: str | None,
        reply_to: str | None,
        attachments: list[OutgoingAttachment] | None,
        sign: bool | None,
        in_reply_to: str | None = None,
        references: tuple[str, ...] = (),
    ) -> PreparedMessage:
        try:
            account_settings = self._settings.account(account)
        except ValueError as exc:
            raise UpstreamValidationError(str(exc)) from exc
        addresses = prepare_addresses(to, cc, bcc, max_recipients=self._settings.email_max_recipients)
        decoded_attachments = decode_attachments(attachments, self._settings)
        body = build_body(
            text_body,
            html_body,
            decoded_attachments,
            max_body_chars=self._settings.email_max_body_chars,
        )
        should_sign = account_settings.gpg_key_fingerprint is not None if sign is None else sign
        signature = await self._signer.sign(account_settings, serialize_body(body)) if should_sign else None
        return build_message(
            account_settings,
            addresses,
            subject,
            reply_to,
            body,
            decoded_attachments,
            signature,
            from_address=from_address,
            in_reply_to=in_reply_to,
            references=references,
        )
