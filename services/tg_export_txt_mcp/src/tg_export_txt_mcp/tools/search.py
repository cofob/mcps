from tg_export_txt_mcp.formatters import format_search_results
from tg_export_txt_mcp.service import TgExportTxtService


class SearchTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def search_exports(  # noqa: PLR0913
        self,
        path: str,
        query: str,
        max_results: int = 200,
        start_date: str | None = None,
        end_date: str | None = None,
        chat_id: str | None = None,
        topic_id: str | None = None,
        path_prefix: str | None = None,
        filename_glob: str | None = None,
        case_sensitive: bool = False,
        whole_word: bool = False,
    ) -> str:
        """Search exported TXT files with ripgrep under one path.

        How it works:
        - Resolves ``path`` relative to the configured Telegram TXT export root.
        - Carries structured metadata for each hit, including chat id, topic id, weekly
          bucket, and an internal rank score.
        - Supports optional filtering by date range, chat id, topic id, path prefix,
          and filename glob before results are ranked.
        - Runs ``rg --json`` with optional case-sensitive and whole-word matching.
        - Ranks the candidate hits so stronger textual matches and newer buckets appear
          first.

        How to call it:
        - Use a chat-specific path to keep searches focused and fast.
        - Example within one chat:
          ``search_exports(path="chats/-1001234567890", query="refund", max_results=20)``
        - Example with date bounds:
          ``search_exports(path="chats/-1001234567890", query="refund",
          start_date="2026-03-01", end_date="2026-03-17")``
        - Example with structured filters:
          ``search_exports(path=".", query="release", chat_id="-1001234567890",
          topic_id="42", filename_glob="2026-03-*.txt", whole_word=True)``
        - Example across the whole export:
          ``search_exports(path=".", query="exception")``

        What it returns:
        - A plain-text list like
          ``<index>. <relative_path>:<line_number>: <line_text> [score=..., chat=..., topic=..., bucket=...]``.
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
            chat_id=chat_id,
            topic_id=topic_id,
            path_prefix=path_prefix,
            filename_glob=filename_glob,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
        )
        return format_search_results(self._service.display_path(resolved), query, matches, limited=limited)
