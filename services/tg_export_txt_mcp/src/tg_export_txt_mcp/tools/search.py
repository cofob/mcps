from tg_export_txt_mcp.formatters import format_search_results
from tg_export_txt_mcp.service import TgExportTxtService


class SearchTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def search_exports(self, path: str, query: str, max_results: int = 200) -> str:
        """Search exported TXT files with ripgrep under one path.

        How it works:
        - Resolves ``path`` relative to the configured Telegram TXT export root.
        - Runs ``rg --json`` under that path with ``--smart-case`` and ``*.txt`` glob
          filtering.
        - Streams matches and stops after ``max_results`` results.

        How to call it:
        - Use a chat-specific path to keep searches focused and fast.
        - Example within one chat:
          ``search_exports(path="chats/-1001234567890", query="refund", max_results=20)``
        - Example across the whole export:
          ``search_exports(path=".", query="exception")``

        What it returns:
        - A plain-text list like ``<index>. <relative_path>:<line_number>: <line_text>``.
        - The header reports the searched path, query, and match count returned.
        - If more matches exist than returned, the output includes a truncation note.
        """
        resolved = self._service.resolve_path(path)
        matches, limited = self._service.search_exports(path, query, max_results=max_results)
        return format_search_results(self._service.display_path(resolved), query, matches, limited=limited)
