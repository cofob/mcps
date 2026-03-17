from mcp_common import JsonObject, get_bool, get_int, get_str
from navidrome_mcp.models import CatalogItem, PlaylistItem, ShareLinkItem


def normalize_artist(payload: JsonObject) -> CatalogItem:
    artist_id = get_str(payload, "id")
    name = get_str(payload, "name")
    if artist_id is None or name is None:
        raise ValueError("Artist payload is missing id or name.")
    return CatalogItem(entity_type="artist", id=artist_id, name=name)


def normalize_album(payload: JsonObject) -> CatalogItem:
    album_id = get_str(payload, "id")
    if album_id is None:
        raise ValueError("Album payload is missing id.")
    return CatalogItem(
        entity_type="album",
        id=album_id,
        name=get_str(payload, "name") or get_str(payload, "title") or album_id,
        artist_name=get_str(payload, "artist"),
        year=get_int(payload, "year"),
        genre=get_str(payload, "genre"),
    )


def normalize_track(payload: JsonObject) -> CatalogItem:
    track_id = get_str(payload, "id")
    if track_id is None:
        raise ValueError("Track payload is missing id.")
    return CatalogItem(
        entity_type="track",
        id=track_id,
        name=get_str(payload, "title") or get_str(payload, "name") or track_id,
        artist_name=get_str(payload, "artist"),
        album_name=get_str(payload, "album"),
        year=get_int(payload, "year"),
        genre=get_str(payload, "genre"),
    )


def normalize_playlist(payload: JsonObject) -> PlaylistItem:
    playlist_id = get_str(payload, "id")
    name = get_str(payload, "name")
    if playlist_id is None or name is None:
        raise ValueError("Playlist payload is missing id or name.")
    return PlaylistItem(
        id=playlist_id,
        name=name,
        song_count=get_int(payload, "songCount"),
        public=get_bool(payload, "public"),
        owner=get_str(payload, "owner"),
    )


def normalize_share_link(payload: JsonObject) -> ShareLinkItem:
    share_id = get_str(payload, "id")
    url = get_str(payload, "url")
    if share_id is None or url is None:
        raise ValueError("Share payload is missing id or url.")
    return ShareLinkItem(
        id=share_id,
        url=url,
        description=get_str(payload, "description"),
        expires=get_str(payload, "expires"),
    )
