from mcp_common import get_object, get_object_list
from navidrome_mcp.client import NavidromeClient
from navidrome_mcp.formatters import format_search_results
from navidrome_mcp.normalize import normalize_album, normalize_artist, normalize_track


class SearchTools:
    def __init__(self, client: NavidromeClient) -> None:
        self._client = client

    async def search(self, query: str, search_type: str = "all", limit: int = 10) -> str:
        """Search Navidrome artists, albums, or tracks by keyword."""
        payload = await self._client.call(
            "search3",
            params={
                "query": query,
                "artistCount": limit,
                "albumCount": limit,
                "songCount": limit,
            },
        )
        response = get_object(payload, "subsonic-response", context="search3")
        result = get_object(response, "searchResult3", context="search3")
        artists = [
            normalize_artist(item)
            for item in get_object_list(result, "artist", context="search3.searchResult3")
        ]
        albums = [
            normalize_album(item)
            for item in get_object_list(result, "album", context="search3.searchResult3")
        ]
        tracks = [
            normalize_track(item)
            for item in get_object_list(result, "song", context="search3.searchResult3")
        ]
        if search_type == "artists":
            albums = []
            tracks = []
        elif search_type == "albums":
            artists = []
            tracks = []
        elif search_type == "tracks":
            artists = []
            albums = []
        return format_search_results(
            query=query,
            artists=artists,
            albums=albums,
            tracks=tracks,
            limit=limit,
        )
