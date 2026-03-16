from collections.abc import Sequence

from mcp_common.formatters import truncation_suffix
from navidrome_mcp.models import CatalogItem, PlaylistItem


def _format_catalog_items(title: str, items: Sequence[CatalogItem], *, limit: int) -> str:
    shown_items = list(items[:limit])
    lines = [f"{title}{truncation_suffix(len(shown_items), len(items))}"]
    for index, item in enumerate(shown_items, start=1):
        lines.append(f"{index}. {item.name}")
        lines.append(f"   id: {item.id}")
        if item.artist_name:
            lines.append(f"   artist: {item.artist_name}")
        if item.album_name:
            lines.append(f"   album: {item.album_name}")
        if item.year is not None:
            lines.append(f"   year: {item.year}")
    return "\n".join(lines)


def format_search_results(
    *,
    query: str,
    artists: Sequence[CatalogItem],
    albums: Sequence[CatalogItem],
    tracks: Sequence[CatalogItem],
    limit: int,
) -> str:
    total = len(artists) + len(albums) + len(tracks)
    lines = [f'Found {total} results for "{query}".']
    if artists:
        lines.extend(["", _format_catalog_items("Artists", artists, limit=limit)])
    if albums:
        lines.extend(["", _format_catalog_items("Albums", albums, limit=limit)])
    if tracks:
        lines.extend(["", _format_catalog_items("Tracks", tracks, limit=limit)])
    return "\n".join(lines)


def format_catalog_item(item: CatalogItem) -> str:
    lines = [f"{item.entity_type.title()}", f"- id: {item.id}", f"- name: {item.name}"]
    if item.artist_name:
        lines.append(f"- artist: {item.artist_name}")
    if item.album_name:
        lines.append(f"- album: {item.album_name}")
    if item.year is not None:
        lines.append(f"- year: {item.year}")
    return "\n".join(lines)


def format_playlist(item: PlaylistItem) -> str:
    lines = ["Playlist", f"- id: {item.id}", f"- name: {item.name}"]
    if item.song_count is not None:
        lines.append(f"- songs: {item.song_count}")
    if item.public is not None:
        lines.append(f"- public: {str(item.public).lower()}")
    if item.owner:
        lines.append(f"- owner: {item.owner}")
    return "\n".join(lines)


def format_playlist_list(playlists: Sequence[PlaylistItem]) -> str:
    lines = [f"Found {len(playlists)} playlists."]
    for index, playlist in enumerate(playlists, start=1):
        lines.append(f"{index}. {playlist.name}")
        lines.append(f"   id: {playlist.id}")
    return "\n".join(lines)


def format_mutation_summary(summary: str) -> str:
    return summary
