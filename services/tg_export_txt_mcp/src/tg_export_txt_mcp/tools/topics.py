from tg_export_txt_mcp.formatters import format_topic_list
from tg_export_txt_mcp.service import TgExportTxtService


class TopicTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def list_topics(self, chat_id: str, max_results: int = 200) -> str:
        """List topics for one exported forum chat.

        How it works:
        - Reads ``chats/<chat_id>/topics.txt`` from the configured Telegram TXT export
          root.
        - Each source line is expected to be ``topic_id<TAB>topic_name``.
        - Returns at most ``max_results`` topics for that forum chat.

        How to call it:
        - Pass the forum chat id exactly as it appears in ``chats.txt``.
        - Example: ``list_topics(chat_id="-1001234567890")``
        - Use this before reading topic-specific transcript files under that chat.

        What it returns:
        - A plain-text list like ``<index>. <topic_id><TAB><topic_name>``.
        - The header reports the chat id and number of topics returned.
        - If more topics exist than returned, the output includes a truncation note.
        """
        topics, limited = self._service.list_topics(chat_id, max_results=max_results)
        return format_topic_list(chat_id, topics, limited=limited)
