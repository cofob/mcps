from slskd_mcp.client import SlskdClient
from slskd_mcp.formatters import format_simple_summary


class UserTools:
    def __init__(self, client: SlskdClient) -> None:
        self._client = client

    async def get_user(self, action: str, username: str, directory: str | None = None) -> str:
        """Inspect one Soulseek user in slskd."""
        if action == "status":
            payload = await self._client.request("GET", f"/api/v0/users/{username}/status")
        elif action == "info":
            payload = await self._client.request("GET", f"/api/v0/users/{username}/info")
        elif action == "endpoint":
            payload = await self._client.request("GET", f"/api/v0/users/{username}/endpoint")
        elif action == "directory":
            payload = await self._client.request(
                "POST",
                f"/api/v0/users/{username}/directory",
                json_body={"directory": directory or ""},
            )
        else:
            raise ValueError("action must be one of: status, info, endpoint, directory")
        return format_simple_summary(f"{action.title()} for {username}:\n{payload}")

    async def browse_user(self, username: str) -> str:
        """Browse the shared folders of one Soulseek user."""
        payload = await self._client.request("GET", f"/api/v0/users/{username}/browse")
        return format_simple_summary(f"Browse tree for {username}:\n{payload}")
