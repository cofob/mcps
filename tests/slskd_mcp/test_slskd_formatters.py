from slskd_mcp.formatters import format_search_results
from slskd_mcp.models import SlskdSearchFile


def test_slskd_search_formatter_mentions_download_tool() -> None:
    result = SlskdSearchFile(
        username="alice",
        filename="Music/song.flac",
        directory="Music",
        size=123,
    )
    text = format_search_results(
        "1234",
        [result],
        limit=10,
    )
    assert "slskd_request_downloads" in text
