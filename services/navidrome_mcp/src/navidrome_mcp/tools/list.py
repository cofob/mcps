from mcp_common import get_object, get_object_list
from navidrome_mcp.client import NavidromeClient
from navidrome_mcp.formatters import format_playlist_list, format_search_results
from navidrome_mcp.normalize import normalize_album, normalize_artist, normalize_playlist, normalize_track


class ListTools:
    def __init__(self, client: NavidromeClient) -> None:
        self._client = client

    async def list_artists(self, music_folder_id: str | None = None) -> str:
        """List Navidrome artists for browse-style discovery."""
        payload = await self._client.call("getArtists", params={"musicFolderId": music_folder_id})
        response = get_object(payload, "subsonic-response", context="getArtists")
        artists_container = get_object(response, "artists", context="getArtists")
        indexes = get_object_list(artists_container, "index", context="getArtists.artists")
        artists = [
            normalize_artist(artist)
            for group in indexes
            for artist in get_object_list(group, "artist", context="getArtists.index")
        ]
        return format_search_results(
            query="artists",
            artists=artists,
            albums=[],
            tracks=[],
            limit=len(artists),
        )

    async def list_albums(
        self,
        list_type: str,
        genre: str | None = None,
        from_year: int | None = None,
        to_year: int | None = None,
        size: int = 10,
        offset: int = 0,
    ) -> str:
        """List Navidrome albums using one album-list mode."""
        payload = await self._client.call(
            "getAlbumList2",
            params={
                "type": list_type,
                "genre": genre,
                "fromYear": from_year,
                "toYear": to_year,
                "size": size,
                "offset": offset,
            },
        )
        response = get_object(payload, "subsonic-response", context="getAlbumList2")
        albums_container = get_object(response, "albumList2", context="getAlbumList2")
        albums = [
            normalize_album(item)
            for item in get_object_list(albums_container, "album", context="getAlbumList2.albumList2")
        ]
        return format_search_results(
            query=f"albums:{list_type}",
            artists=[],
            albums=albums,
            tracks=[],
            limit=size,
        )

    async def list_playlists(self) -> str:
        """List Navidrome playlists."""
        payload = await self._client.call("getPlaylists")
        response = get_object(payload, "subsonic-response", context="getPlaylists")
        playlists_container = get_object(response, "playlists", context="getPlaylists")
        playlists = [
            normalize_playlist(item)
            for item in get_object_list(playlists_container, "playlist", context="getPlaylists.playlists")
        ]
        return format_playlist_list(playlists)

    async def list_starred(self, music_folder_id: str | None = None) -> str:
        """List starred Navidrome artists, albums, and tracks."""
        payload = await self._client.call("getStarred2", params={"musicFolderId": music_folder_id})
        response = get_object(payload, "subsonic-response", context="getStarred2")
        starred = get_object(response, "starred2", context="getStarred2")
        artists = [
            normalize_artist(item)
            for item in get_object_list(starred, "artist", context="getStarred2.starred2")
        ]
        albums = [
            normalize_album(item)
            for item in get_object_list(starred, "album", context="getStarred2.starred2")
        ]
        tracks = [
            normalize_track(item)
            for item in get_object_list(starred, "song", context="getStarred2.starred2")
        ]
        return format_search_results(
            query="starred",
            artists=artists,
            albums=albums,
            tracks=tracks,
            limit=50,
        )

    async def list_random_tracks(self, size: int = 10, genre: str | None = None) -> str:
        """List random Navidrome tracks."""
        payload = await self._client.call("getRandomSongs", params={"size": size, "genre": genre})
        response = get_object(payload, "subsonic-response", context="getRandomSongs")
        songs = get_object(response, "randomSongs", context="getRandomSongs")
        tracks = [
            normalize_track(item)
            for item in get_object_list(songs, "song", context="getRandomSongs.randomSongs")
        ]
        return format_search_results(
            query="random tracks",
            artists=[],
            albums=[],
            tracks=tracks,
            limit=size,
        )

    async def list_tracks_by_genre(self, genre: str, count: int = 10, offset: int = 0) -> str:
        """List Navidrome tracks for one genre."""
        payload = await self._client.call(
            "getSongsByGenre",
            params={"genre": genre, "count": count, "offset": offset},
        )
        response = get_object(payload, "subsonic-response", context="getSongsByGenre")
        songs = get_object(response, "songsByGenre", context="getSongsByGenre")
        tracks = [
            normalize_track(item)
            for item in get_object_list(songs, "song", context="getSongsByGenre.songsByGenre")
        ]
        return format_search_results(
            query=f"genre:{genre}",
            artists=[],
            albums=[],
            tracks=tracks,
            limit=count,
        )
