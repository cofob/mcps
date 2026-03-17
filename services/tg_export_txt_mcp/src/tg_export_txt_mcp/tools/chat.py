from tg_export_txt_mcp.formatters import format_chat_list, format_chat_search_results
from tg_export_txt_mcp.service import TgExportTxtService


class ChatTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def list_chats(self, max_results: int = 200) -> str:
        """List chats from the exported chats.txt mapping file."""
        chats, limited = self._service.list_chats(max_results=max_results)
        return format_chat_list(chats, limited=limited)

    async def search_chats(self, query: str, max_results: int = 200) -> str:
        """Search chat ids and names from the exported chats.txt mapping file."""
        chats, limited = self._service.search_chats(query, max_results=max_results)
        return format_chat_search_results(query, chats, limited=limited)
