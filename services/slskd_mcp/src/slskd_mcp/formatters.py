from collections.abc import Sequence

from mcp_common import JsonObject
from mcp_common.formatters import truncation_suffix
from slskd_mcp.models import SlskdSearchFile


def format_search_list(searches: Sequence[JsonObject]) -> str:
    lines = [f"Found {len(searches)} searches."]
    for index, search in enumerate(searches, start=1):
        lines.append(f"{index}. {search.get('searchText', search.get('SearchText', 'search'))}")
        lines.append(f"   id: {search.get('id', search.get('Id', 'unknown'))}")
    return "\n".join(lines)


def format_search_results(search_id: str, results: Sequence[SlskdSearchFile], *, limit: int) -> str:
    shown = list(results[:limit])
    lines = [
        (
            f"Search {search_id} returned {len(results)} matching files."
            f"{truncation_suffix(len(shown), len(results))}"
        )
    ]
    if shown:
        lines.extend(["", "Top results"])
    for index, item in enumerate(shown, start=1):
        lines.append(f"{index}. user: {item.username}")
        lines.append(f"   file: {item.filename}")
        lines.append(f"   size: {item.size}")
    lines.extend(
        [
            "",
            (
                "Use `slskd_request_downloads` with the selected username, "
                "filename, and size values to queue a download."
            ),
        ]
    )
    return "\n".join(lines)


def format_simple_summary(summary: str) -> str:
    return summary
