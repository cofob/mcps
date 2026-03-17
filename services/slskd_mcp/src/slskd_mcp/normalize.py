from collections.abc import Sequence

from mcp_common import JsonObject, get_int, get_object_list, get_str
from slskd_mcp.models import SlskdSearchFile


def normalize_search_results(payload: Sequence[JsonObject]) -> list[SlskdSearchFile]:
    items: list[SlskdSearchFile] = []
    for response in payload:
        username = get_str(response, "username") or get_str(response, "Username") or "unknown"
        files = get_object_list(response, "files", context="search response") or get_object_list(
            response,
            "Files",
            context="search response",
        )
        for file_item in files:
            filename = get_str(file_item, "filename") or get_str(file_item, "Filename") or ""
            directory = filename.rsplit("/", 1)[0] if "/" in filename else ""
            size = get_int(file_item, "size") or get_int(file_item, "Size") or 0
            items.append(
                SlskdSearchFile(
                    username=username,
                    filename=filename,
                    directory=directory,
                    size=size,
                )
            )
    return items
