from typing import cast

import pytest

from mcp_common import JsonArray, JsonObject, JsonValue
from slskd_mcp.client import SlskdClient
from slskd_mcp.models import SlskdDownloadRequest
from slskd_mcp.tools import DownloadTools, FileTools, SearchTools, UserTools


class FakeSlskdClient:
    def __init__(self) -> None:
        self.calls: list[
            tuple[
                str,
                str,
                dict[str, str | bool | int | float | None | list[str] | list[int]] | None,
                JsonValue | None,
            ]
        ] = []

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | bool | int | float | None | list[str] | list[int]] | None = None,
        json_body: JsonValue | None = None,
    ) -> JsonObject | JsonArray:
        self.calls.append((method, path, params, json_body))
        if path == "/api/v0/searches":
            return {"id": "search-1"}
        if path.endswith("/responses"):
            return [
                {
                    "username": "alice",
                    "files": [{"filename": "Music/song.flac", "size": 123}],
                }
            ]
        return {"ok": True}


@pytest.mark.asyncio
async def test_create_search_sends_expected_payload() -> None:
    client = FakeSlskdClient()
    text = await SearchTools(cast(SlskdClient, client)).create_search("beatles")
    assert text == "Started search search-1."
    assert client.calls[0][0] == "POST"
    assert client.calls[0][1] == "/api/v0/searches"


@pytest.mark.asyncio
async def test_request_downloads_formats_summary() -> None:
    client = FakeSlskdClient()
    text = await DownloadTools(cast(SlskdClient, client)).request_downloads(
        "alice",
        [SlskdDownloadRequest(filename="Music/song.flac", size=123)],
    )
    assert "Download request submitted for 1 file(s) from alice." in text
    assert client.calls[0][1] == "/api/v0/transfers/downloads/alice"


@pytest.mark.asyncio
async def test_get_user_rejects_unknown_action() -> None:
    with pytest.raises(ValueError, match="action must be one of"):
        await UserTools(cast(SlskdClient, FakeSlskdClient())).get_user("bogus", "alice")


@pytest.mark.asyncio
async def test_list_files_encodes_subdirectory() -> None:
    client = FakeSlskdClient()
    text = await FileTools(cast(SlskdClient, client)).list_files(
        "downloads",
        subdirectory="Album Name",
        recursive=True,
    )
    assert text.startswith("Downloads files:")
    assert client.calls == [
        (
            "GET",
            "/api/v0/files/downloads/directories/QWxidW0gTmFtZQ==",
            {"recursive": True},
            None,
        )
    ]
