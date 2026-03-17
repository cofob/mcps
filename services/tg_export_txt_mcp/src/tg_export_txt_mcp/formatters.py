from collections.abc import Sequence

from tg_export_txt_mcp.models import ExportReadResult, ExportSearchMatch


def format_read_result(result: ExportReadResult) -> str:
    lines = [
        f"Path: {result.path}",
        f"Absolute path: {result.absolute_path}",
        f"Lines: {result.start_line}-{result.end_line} of {result.total_lines}",
        "",
        "Content",
        result.content,
    ]
    return "\n".join(lines)


def format_search_results(
    base_path: str,
    query: str,
    matches: Sequence[ExportSearchMatch],
    *,
    limited: bool,
) -> str:
    lines = [f'Search for "{query}" under {base_path}: {len(matches)} match(es)']
    for index, match in enumerate(matches, start=1):
        lines.append(f"{index}. {match.path}:{match.line_number}: {match.line_text}")
    if limited:
        lines.extend(["", "Results were truncated at the configured max_search_results limit."])
    return "\n".join(lines)
