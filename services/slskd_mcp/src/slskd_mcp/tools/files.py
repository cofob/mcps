import base64

from slskd_mcp.client import SlskdClient
from slskd_mcp.formatters import format_simple_summary


def _to_base64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


class FileTools:
    def __init__(self, client: SlskdClient) -> None:
        self._client = client

    async def list_files(
        self,
        location: str,
        subdirectory: str | None = None,
        recursive: bool = False,
    ) -> str:
        """List files and folders from slskd download or incomplete directories."""
        if location not in {"downloads", "incomplete"}:
            raise ValueError("location must be downloads or incomplete")
        path = f"/api/v0/files/{location}/directories"
        if subdirectory:
            path = f"{path}/{_to_base64(subdirectory)}"
        payload = await self._client.request("GET", path, params={"recursive": recursive})
        return format_simple_summary(f"{location.title()} files:\n{payload}")
