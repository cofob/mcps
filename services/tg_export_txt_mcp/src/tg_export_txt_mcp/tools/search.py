from tg_export_txt_mcp.formatters import format_search_results
from tg_export_txt_mcp.service import TgExportTxtService


class SearchTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def search_exports(
        self,
        path: str,
        query: str,
        max_results: int = 200,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Search exported TXT files with ripgrep under one path.

        How it works:
        - Resolves ``path`` relative to the configured Telegram TXT export root.
        - Builds a newest-first list of matching ``.txt`` files under that path.
        - Optionally filters weekly export buckets by ``start_date`` and ``end_date``
          using ``YYYY-MM-DD`` ISO dates.
        - Runs ``rg --json`` against the remaining files with ``--smart-case``.
        - Streams matches and stops after ``max_results`` results.

        How to call it:
        - Use a chat-specific path to keep searches focused and fast.
        - Example within one chat:
          ``search_exports(path="chats/-1001234567890", query="refund", max_results=20)``
        - Example with date bounds:
          ``search_exports(path="chats/-1001234567890", query="refund",
          start_date="2026-03-01", end_date="2026-03-17")``
        - Example across the whole export:
          ``search_exports(path=".", query="exception")``

        What it returns:
        - A plain-text list like ``<index>. <relative_path>:<line_number>: <line_text>``.
        - The header reports the searched path, query, and match count returned.
        - If more matches exist than returned, the output includes a truncation note.
        """
        resolved = self._service.resolve_path(path)
        matches, limited = self._service.search_exports(
            path,
            query,
            max_results=max_results,
            start_date=start_date,
            end_date=end_date,
        )
        return format_search_results(self._service.display_path(resolved), query, matches, limited=limited)
