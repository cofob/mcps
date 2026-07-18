import base64
from datetime import date
from urllib.parse import quote

from mcp.types import BlobResourceContents, EmbeddedResource
from pydantic import AnyUrl

from email_mcp.client import EmailClient
from email_mcp.config import EmailSettings
from email_mcp.formatters import format_accounts, format_folders, format_message, format_messages, format_sent
from email_mcp.mime import build_body, build_message, decode_attachments, prepare_addresses, serialize_body
from email_mcp.models import OutgoingAttachment
from email_mcp.signing import GpgSigner
from mcp_common import UpstreamValidationError


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
        try:
            account_settings = self._settings.account(account)
        except ValueError as exc:
            raise UpstreamValidationError(str(exc)) from exc
        addresses = prepare_addresses(
            to,
            cc,
            bcc,
            max_recipients=self._settings.email_max_recipients,
        )
        decoded_attachments = decode_attachments(attachments, self._settings)
        body = build_body(
            text_body,
            html_body,
            decoded_attachments,
            max_body_chars=self._settings.email_max_body_chars,
        )
        should_sign = account_settings.gpg_key_fingerprint is not None if sign is None else sign
        signature = await self._signer.sign(account_settings, serialize_body(body)) if should_sign else None
        prepared = build_message(
            account_settings,
            addresses,
            subject,
            reply_to,
            body,
            decoded_attachments,
            signature,
            from_address=from_address,
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
