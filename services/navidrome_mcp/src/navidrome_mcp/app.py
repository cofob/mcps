from collections.abc import Awaitable, Callable
from typing import cast

from fastmcp import FastMCP
from starlette.applications import Starlette

from mcp_common import (
    SupportsToolRegistration,
    ToolSpec,
    build_auth_provider,
    build_tool_annotations,
    build_tool_tags,
    build_http_app,
    create_async_client,
    register_enabled_tools,
)
from mcp_common.logging import configure_logging
from navidrome_mcp import __version__
from navidrome_mcp.client import NavidromeClient
from navidrome_mcp.config import NavidromeSettings
from navidrome_mcp.tools import GetTools, ListTools, MutationTools, PlaylistTools, SearchTools


def _tool_spec(method: Callable[..., Awaitable[str]], name: str, *groups: str) -> ToolSpec:
    group_set = frozenset(groups)
    tags = build_tool_tags(name, group_set)
    annotations = build_tool_annotations(name, group_set)

    def register_tool(mcp: SupportsToolRegistration) -> None:
        mcp.tool(method, name=name, tags=set(tags), annotations=annotations)

    return ToolSpec(
        name=name,
        groups=group_set,
        tags=tags,
        annotations=annotations,
        register=register_tool,
    )


def _make_tool_specs(client: NavidromeClient) -> list[ToolSpec]:
    search_tools = SearchTools(client)
    get_tools = GetTools(client)
    list_tools = ListTools(client)
    mutation_tools = MutationTools(client)
    playlist_tools = PlaylistTools(client)
    return [
        _tool_spec(search_tools.search, "navidrome_search", "read", "search"),
        _tool_spec(get_tools.get_artist, "navidrome_get_artist", "read"),
        _tool_spec(get_tools.get_album, "navidrome_get_album", "read"),
        _tool_spec(get_tools.get_track, "navidrome_get_track", "read"),
        _tool_spec(
            get_tools.get_playlist,
            "navidrome_get_playlist",
            "read",
            "playlist",
        ),
        _tool_spec(list_tools.list_artists, "navidrome_list_artists", "read"),
        _tool_spec(list_tools.list_albums, "navidrome_list_albums", "read"),
        _tool_spec(
            list_tools.list_playlists,
            "navidrome_list_playlists",
            "read",
            "playlist",
        ),
        _tool_spec(list_tools.list_starred, "navidrome_list_starred", "read"),
        _tool_spec(
            list_tools.list_random_tracks,
            "navidrome_list_random_tracks",
            "read",
        ),
        _tool_spec(
            list_tools.list_tracks_by_genre,
            "navidrome_list_tracks_by_genre",
            "read",
        ),
        _tool_spec(mutation_tools.rate, "navidrome_rate", "mutate"),
        _tool_spec(mutation_tools.like, "navidrome_like", "mutate"),
        _tool_spec(mutation_tools.unlike, "navidrome_unlike", "mutate"),
        _tool_spec(
            playlist_tools.create_playlist,
            "navidrome_create_playlist",
            "mutate",
            "playlist",
        ),
        _tool_spec(
            playlist_tools.update_playlist,
            "navidrome_update_playlist",
            "mutate",
            "playlist",
        ),
        _tool_spec(
            playlist_tools.delete_playlist,
            "navidrome_delete_playlist",
            "mutate",
            "playlist",
        ),
        _tool_spec(
            playlist_tools.get_public_share_link,
            "navidrome_get_public_share_link",
            "mutate",
            "share",
        ),
    ]


def create_mcp(settings: NavidromeSettings) -> FastMCP:
    auth = (
        build_auth_provider(settings.oauth2)
        if settings.mcp_auth_mode.value == "oauth2"
        else None
    )
    mcp = FastMCP(name="navidrome-mcp", auth=auth)
    http_client = create_async_client(
        base_url=str(settings.navidrome_url),
        timeout_seconds=settings.timeout_seconds,
    )
    client = NavidromeClient(settings, http_client)
    register_enabled_tools(
        cast(SupportsToolRegistration, mcp),
        _make_tool_specs(client),
        settings.tools,
    )
    return mcp


def create_app(settings: NavidromeSettings | None = None) -> Starlette:
    resolved = settings or NavidromeSettings.from_env()
    configure_logging(resolved.log_level)
    mcp = create_mcp(resolved)
    mcp_app = mcp.http_app(path="/mcp")
    return build_http_app(mcp_app, service_name="navidrome-mcp", version=__version__)
