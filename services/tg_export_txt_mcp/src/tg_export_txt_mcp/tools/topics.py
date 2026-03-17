from tg_export_txt_mcp.formatters import format_topic_list
from tg_export_txt_mcp.service import TgExportTxtService


class TopicTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def list_topics(self, chat_id: str, max_results: int = 200) -> str:
        """List topics for one exported forum chat from chats/<chat_id>/topics.txt."""
        topics, limited = self._service.list_topics(chat_id, max_results=max_results)
        return format_topic_list(chat_id, topics, limited=limited)
