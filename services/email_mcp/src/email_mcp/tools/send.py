from email_mcp.models import OutgoingAttachment
from email_mcp.service import EmailService


class SendTools:
    def __init__(self, service: EmailService) -> None:
        self._service = service

    async def send_message(  # noqa: PLR0913
        self,
        account: str,
        to: list[str],
        subject: str,
        text_body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        html_body: str | None = None,
        from_address: str | None = None,
        reply_to: str | None = None,
        attachments: list[OutgoingAttachment] | None = None,
        sign: bool | None = None,
    ) -> str:
        """Send from an optional bare address only after explicit confirmation of recipients and complete bodies."""
        return await self._service.send_message(
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

    async def reply_message(  # noqa: PLR0913
        self,
        account: str,
        uid: int,
        text_body: str,
        folder: str = "INBOX",
        reply_all: bool = False,
        bcc: list[str] | None = None,
        html_body: str | None = None,
        from_address: str | None = None,
        reply_to: str | None = None,
        attachments: list[OutgoingAttachment] | None = None,
        sign: bool | None = None,
    ) -> str:
        """Reply with RFC threading headers only after explicit confirmation of the resolved recipients and bodies."""
        return await self._service.reply_message(
            account,
            folder,
            uid,
            text_body,
            reply_all=reply_all,
            bcc=bcc,
            html_body=html_body,
            from_address=from_address,
            reply_to=reply_to,
            attachments=attachments,
            sign=sign,
        )
