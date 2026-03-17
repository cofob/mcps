from mcp_common import get_object
from navidrome_mcp.client import NavidromeClient
from navidrome_mcp.formatters import format_catalog_item, format_playlist
from navidrome_mcp.normalize import normalize_album, normalize_artist, normalize_playlist, normalize_track


class GetTools:
    def __init__(self, client: NavidromeClient) -> None:
        self._client = client

    async def get_artist(self, artist_id: str) -> str:
        """Get one Navidrome artist by id."""
        payload = await self._client.call("getArtist", params={"id": artist_id})
        response = get_object(payload, "subsonic-response", context="getArtist")
        item = normalize_artist(get_object(response, "artist", context="getArtist"))
        return format_catalog_item(item)

    async def get_album(self, album_id: str) -> str:
        """Get one Navidrome album by id."""
        payload = await self._client.call("getAlbum", params={"id": album_id})
        response = get_object(payload, "subsonic-response", context="getAlbum")
        item = normalize_album(get_object(response, "album", context="getAlbum"))
        return format_catalog_item(item)

    async def get_track(self, track_id: str) -> str:
        """Get one Navidrome track by id."""
        payload = await self._client.call("getSong", params={"id": track_id})
        response = get_object(payload, "subsonic-response", context="getSong")
        item = normalize_track(get_object(response, "song", context="getSong"))
        return format_catalog_item(item)

    async def get_playlist(self, playlist_id: str) -> str:
        """Get one Navidrome playlist by id."""
        payload = await self._client.call("getPlaylist", params={"id": playlist_id})
        response = get_object(payload, "subsonic-response", context="getPlaylist")
        item = normalize_playlist(get_object(response, "playlist", context="getPlaylist"))
        return format_playlist(item)
