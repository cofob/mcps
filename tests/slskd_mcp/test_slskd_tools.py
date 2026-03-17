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
        self.timeout_seconds = 20.0
        self.search_poll_interval_seconds = 0.0
        self.search_status_calls = 0
        self.search_response_calls = 0

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
            return {"id": "search-1", "isComplete": False}
        if path == "/api/v0/searches/search-1":
            self.search_status_calls += 1
            return {"id": "search-1", "isComplete": True}
        if path.endswith("/responses"):
            self.search_response_calls += 1
            if self.search_response_calls == 1:
                return []
            return [
                {
                    "username": "alice",
                    "files": [{"filename": "Music/song.flac", "size": 123}],
                }
            ]
        return {"ok": True}


@pytest.mark.asyncio
async def test_create_search_waits_for_results_and_formats_output() -> None:
    client = FakeSlskdClient()
    text = await SearchTools(cast(SlskdClient, client)).create_search("beatles")
    assert "Search search-1 returned 1 matching files." in text
    assert "Music/song.flac" in text
    assert client.calls[0][0] == "POST"
    assert client.calls[0][1] == "/api/v0/searches"
    assert client.calls[0][3] == {
        "searchText": "beatles",
        "responseLimit": 100,
        "fileLimit": 10000,
        "searchTimeout": 15000,
        "filterResponses": True,
        "minimumResponseFileCount": 1,
        "maximumPeerQueueLength": 1000000,
        "minimumPeerUploadSpeed": 0,
    }
    assert client.calls[1][1] == "/api/v0/searches/search-1/responses"
    assert client.calls[2][1] == "/api/v0/searches/search-1"
    assert client.calls[3][1] == "/api/v0/searches/search-1/responses"


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
