from slskd_mcp.client import SlskdClient
from slskd_mcp.formatters import format_simple_summary


class UploadTools:
    def __init__(self, client: SlskdClient) -> None:
        self._client = client

    async def list_uploads(self, include_removed: bool = False) -> str:
        """List slskd uploads."""
        payload = await self._client.request(
            "GET",
            "/api/v0/transfers/uploads",
            params={"includeRemoved": include_removed},
        )
        return format_simple_summary(f"Uploads:\n{payload}")

    async def get_upload(self, username: str, transfer_id: str) -> str:
        """Get one slskd upload by username and transfer id."""
        payload = await self._client.request(
            "GET",
            f"/api/v0/transfers/uploads/{username}/{transfer_id}",
        )
        return format_simple_summary(f"Upload {transfer_id}:\n{payload}")
