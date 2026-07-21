from datetime import date

from mcp.types import EmbeddedResource

from email_mcp.service import EmailService


class MessageTools:
    def __init__(self, service: EmailService) -> None:
        self._service = service

    async def list_messages(
        self,
        account: str,
        folder: str = "INBOX",
        limit: int = 20,
        offset: int = 0,
    ) -> str:
        """List recent messages only when directly requested, without marking them read."""
        return await self._service.list_messages(account, folder, limit, offset)

    async def search_messages(  # noqa: PLR0913
        self,
        account: str,
        folder: str = "INBOX",
        sender: str | None = None,
        recipient: str | None = None,
        subject: str | None = None,
        text: str | None = None,
        since: date | None = None,
        before: date | None = None,
        unread_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> str:
        """Search mail only when directly requested, using portable filters without changing read state."""
        return await self._service.search_messages(
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

    async def get_message(self, account: str, uid: int, folder: str = "INBOX") -> str:
        """Read one message by stable folder-scoped IMAP UID without marking it read."""
        return await self._service.get_message(account, folder, uid)

    async def get_thread(
        self,
        account: str,
        uid: int,
        folder: str = "INBOX",
        limit: int = 20,
    ) -> str:
        """Read the RFC-header-linked thread containing one directly requested message without changing read state."""
        return await self._service.get_thread(account, folder, uid, limit)

    async def get_attachment(
        self,
        account: str,
        uid: int,
        attachment_index: int,
        folder: str = "INBOX",
    ) -> EmbeddedResource:
        """Read one message attachment as an MCP binary resource without marking the message read."""
        return await self._service.get_attachment(account, folder, uid, attachment_index)
