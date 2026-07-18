from email_mcp.service import EmailService


class AccountTools:
    def __init__(self, service: EmailService) -> None:
        self._service = service

    async def list_accounts(self) -> str:
        """List configured email account names and non-secret identities."""
        return self._service.list_accounts()

    async def list_folders(self, account: str) -> str:
        """List IMAP folders for a configured email account."""
        return await self._service.list_folders(account)
