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
        reply_to: str | None = None,
        attachments: list[OutgoingAttachment] | None = None,
        sign: bool | None = None,
    ) -> str:
        """Send an SMTP email, optionally with HTML, attachments, and OpenPGP/MIME signing."""
        return await self._service.send_message(
            account,
            to,
            subject,
            text_body,
            cc=cc,
            bcc=bcc,
            html_body=html_body,
            reply_to=reply_to,
            attachments=attachments,
            sign=sign,
        )
