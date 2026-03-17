from tg_export_txt_mcp.formatters import format_chat_list, format_chat_search_results
from tg_export_txt_mcp.service import TgExportTxtService


class ChatTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def list_chats(self, max_results: int = 200) -> str:
        """List exported chats from the top-level ``chats.txt`` mapping file.

        How it works:
        - Reads ``chats.txt`` from the configured Telegram TXT export root.
        - Each source line is expected to be ``chat_id<TAB>chat_name``.
        - Returns at most ``max_results`` chats in the same id-to-name form.

        How to call it:
        - Use it when you need to discover available chats before reading files.
        - Typical call: ``list_chats()``
        - Larger sample: ``list_chats(max_results=500)``

        What it returns:
        - A plain-text list like ``<index>. <chat_id><TAB><chat_name>``.
        - The first line reports how many chats were returned.
        - If the result set was cut off, the output ends with a truncation note.
        """
        chats, limited = self._service.list_chats(max_results=max_results)
        return format_chat_list(chats, limited=limited)

    async def search_chats(self, query: str, max_results: int = 200) -> str:
        """Fuzzy-search exported chats by chat id or chat name.

        How it works:
        - Reads chat entries from the top-level ``chats.txt`` mapping file.
        - Scores both ids and names with fuzzy matching, while still prioritizing direct
          substring hits.
        - Returns at most ``max_results`` matches.

        How to call it:
        - Pass a non-empty id or name fragment, even if it is incomplete or misspelled.
        - By id: ``search_chats(query="-1001234567890")``
        - By name: ``search_chats(query="suport")``

        What it returns:
        - A plain-text result list like ``<index>. <chat_id><TAB><chat_name>``.
        - The best fuzzy matches are listed first.
        - If more matches exist than returned, the output includes a truncation note.
        """
        chats, limited = self._service.search_chats(query, max_results=max_results)
        return format_chat_search_results(query, chats, limited=limited)
