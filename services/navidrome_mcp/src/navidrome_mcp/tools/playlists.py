from mcp_common import get_object, get_object_list
from navidrome_mcp.client import NavidromeClient
from navidrome_mcp.formatters import format_mutation_summary, format_share_link
from navidrome_mcp.normalize import normalize_playlist, normalize_share_link


class PlaylistTools:
    def __init__(self, client: NavidromeClient) -> None:
        self._client = client

    async def create_playlist(self, name: str, song_ids: list[str] | None = None) -> str:
        """Create a Navidrome playlist, optionally with initial tracks."""
        params: dict[str, str | bool | int | float | None | list[str] | list[int]] = {"name": name}
        if song_ids:
            params["songId"] = song_ids
        payload = await self._client.call("createPlaylist", params=params)
        response = get_object(payload, "subsonic-response", context="createPlaylist")
        playlist = normalize_playlist(get_object(response, "playlist", context="createPlaylist"))
        return format_mutation_summary(f"Created playlist {playlist.name} ({playlist.id}).")

    async def update_playlist(
        self,
        playlist_id: str,
        name: str | None = None,
        comment: str | None = None,
        public: bool | None = None,
        song_ids_to_add: list[str] | None = None,
        song_indexes_to_remove: list[int] | None = None,
    ) -> str:
        """Update Navidrome playlist metadata or tracks."""
        params: dict[str, str | bool | int | float | None | list[str] | list[int]] = {"playlistId": playlist_id}
        if name is not None:
            params["name"] = name
        if comment is not None:
            params["comment"] = comment
        if public is not None:
            params["public"] = str(public).lower()
        if song_ids_to_add:
            params["songIdToAdd"] = song_ids_to_add
        if song_indexes_to_remove:
            params["songIndexToRemove"] = song_indexes_to_remove
        await self._client.call("updatePlaylist", params=params)
        return format_mutation_summary(f"Updated playlist {playlist_id}.")

    async def delete_playlist(self, playlist_id: str) -> str:
        """Delete a Navidrome playlist by id."""
        await self._client.call("deletePlaylist", params={"id": playlist_id})
        return format_mutation_summary(f"Deleted playlist {playlist_id}.")

    async def get_public_share_link(
        self,
        item_ids: list[str],
        description: str | None = None,
        expires: str | None = None,
    ) -> str:
        """Create a public Navidrome share link for one or more item ids."""
        if not item_ids:
            raise ValueError("item_ids must contain at least one id")
        params: dict[str, str | bool | int | float | None | list[str] | list[int]] = {"id": item_ids}
        if description is not None:
            params["description"] = description
        if expires is not None:
            params["expires"] = expires
        payload = await self._client.call("createShare", params=params)
        response = get_object(payload, "subsonic-response", context="createShare")
        share_payload = get_object(response, "share", context="createShare")
        if share_payload:
            return format_share_link(normalize_share_link(share_payload))
        shares_payload = get_object(response, "shares", context="createShare")
        share_items = get_object_list(shares_payload, "share", context="createShare.shares")
        if not share_items:
            raise ValueError("createShare response is missing share details.")
        return format_share_link(normalize_share_link(share_items[0]))
