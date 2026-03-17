from typing import cast

import pytest

from mcp_common import JsonObject
from navidrome_mcp.client import NavidromeClient
from navidrome_mcp.tools import GetTools, MutationTools, PlaylistTools


class FakeNavidromeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str | bool | int | float | None | list[str] | list[int]] | None]] = []

    async def call(
        self,
        endpoint: str,
        *,
        params: dict[str, str | bool | int | float | None | list[str] | list[int]] | None = None,
    ) -> JsonObject:
        self.calls.append((endpoint, params))
        if endpoint == "getAlbum":
            return {
                "subsonic-response": {
                    "album": {
                        "id": "al-1",
                        "name": "Abbey Road",
                        "artist": "The Beatles",
                        "year": 1969,
                    }
                }
            }
        if endpoint == "createPlaylist":
            return {
                "subsonic-response": {
                    "playlist": {"id": "pl-1", "name": "Road Trip"}
                }
            }
        if endpoint == "createShare":
            return {
                "subsonic-response": {
                    "share": {
                        "id": "sh-1",
                        "url": "https://navidrome.example.com/share/sh-1",
                        "description": "Road Trip mix",
                    }
                }
            }
        return {"subsonic-response": {}}


@pytest.mark.asyncio
async def test_get_album_formats_normalized_album() -> None:
    client = FakeNavidromeClient()
    text = await GetTools(cast(NavidromeClient, client)).get_album("al-1")
    assert "Album" in text
    assert "- name: Abbey Road" in text
    assert client.calls == [("getAlbum", {"id": "al-1"})]


@pytest.mark.asyncio
async def test_create_playlist_sends_song_ids() -> None:
    client = FakeNavidromeClient()
    text = await PlaylistTools(cast(NavidromeClient, client)).create_playlist(
        "Road Trip",
        song_ids=["s1", "s2"],
    )
    assert text == "Created playlist Road Trip (pl-1)."
    assert client.calls == [
        ("createPlaylist", {"name": "Road Trip", "songId": ["s1", "s2"]})
    ]


@pytest.mark.asyncio
async def test_rate_rejects_out_of_range_value() -> None:
    with pytest.raises(ValueError, match="rating must be between 0 and 5"):
        await MutationTools(cast(NavidromeClient, FakeNavidromeClient())).rate(
            "track",
            "track-1",
            6,
        )


@pytest.mark.asyncio
async def test_get_public_share_link_returns_share_url() -> None:
    client = FakeNavidromeClient()
    text = await PlaylistTools(cast(NavidromeClient, client)).get_public_share_link(
        ["pl-1"],
        description="Road Trip mix",
    )
    assert "Public share link" in text
    assert "- url: https://navidrome.example.com/share/sh-1" in text
    assert client.calls == [
        ("createShare", {"id": ["pl-1"], "description": "Road Trip mix"})
    ]
