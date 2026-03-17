from slskd_mcp.normalize import normalize_search_results


def test_normalize_search_results_flattens_files() -> None:
    items = normalize_search_results(
        [
            {
                "Username": "alice",
                "Files": [
                    {"Filename": "Music/Album/song1.flac", "Size": 123},
                    {"Filename": "Music/Album/song2.flac", "Size": 456},
                ],
            }
        ]
    )
    assert [item.username for item in items] == ["alice", "alice"]
    assert [item.directory for item in items] == ["Music/Album", "Music/Album"]
    assert [item.size for item in items] == [123, 456]
