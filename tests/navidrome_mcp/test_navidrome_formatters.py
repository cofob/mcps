from navidrome_mcp.formatters import format_search_results
from navidrome_mcp.models import CatalogItem


def test_search_formatter_mentions_real_tool_names() -> None:
    album = CatalogItem(
        entity_type="album",
        id="al-1",
        name="Abbey Road",
        artist_name="The Beatles",
        year=1969,
    )
    text = format_search_results(
        query="Abbey Road",
        artists=[],
        albums=[album],
        tracks=[],
        limit=10,
    )
    assert "Abbey Road" in text
