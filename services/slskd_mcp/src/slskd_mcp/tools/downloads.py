from slskd_mcp.client import SlskdClient
from slskd_mcp.formatters import format_simple_summary
from slskd_mcp.models import SlskdDownloadRequest


class DownloadTools:
    def __init__(self, client: SlskdClient) -> None:
        self._client = client

    async def request_downloads(self, username: str, files: list[SlskdDownloadRequest]) -> str:
        """Queue one or more downloads from a Soulseek user."""
        payload = await self._client.request(
            "POST",
            f"/api/v0/transfers/downloads/{username}",
            json_body=[item.model_dump() for item in files],
        )
        return format_simple_summary(
            f"Download request submitted for {len(files)} "
            f"file(s) from {username}.\n{payload}"
        )

    async def list_downloads(self, include_removed: bool = False) -> str:
        """List slskd downloads."""
        payload = await self._client.request(
            "GET",
            "/api/v0/transfers/downloads",
            params={"includeRemoved": include_removed},
        )
        return format_simple_summary(f"Downloads:\n{payload}")

    async def get_download(self, username: str, transfer_id: str) -> str:
        """Get one slskd download by username and transfer id."""
        payload = await self._client.request(
            "GET",
            f"/api/v0/transfers/downloads/{username}/{transfer_id}",
        )
        return format_simple_summary(f"Download {transfer_id}:\n{payload}")

    async def get_download_queue_position(self, username: str, transfer_id: str) -> str:
        """Get the current remote queue position for one slskd download."""
        payload = await self._client.request(
            "GET",
            f"/api/v0/transfers/downloads/{username}/{transfer_id}/position",
        )
        return format_simple_summary(f"Queue position for {transfer_id}: {payload}")

    async def cancel_download(self, username: str, transfer_id: str, remove: bool = False) -> str:
        """Cancel one slskd download."""
        await self._client.request(
            "DELETE",
            f"/api/v0/transfers/downloads/{username}/{transfer_id}",
            params={"remove": remove},
        )
        return format_simple_summary(f"Cancelled download {transfer_id}.")

    async def clear_completed_downloads(self) -> str:
        """Remove completed downloads from slskd's tracked download list."""
        await self._client.request("DELETE", "/api/v0/transfers/downloads/all/completed")
        return format_simple_summary("Cleared completed downloads.")
