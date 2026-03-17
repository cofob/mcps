from tg_export_txt_mcp.formatters import format_file_list
from tg_export_txt_mcp.service import TgExportTxtService


class FileTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def list_export_files(self, path: str = ".", max_results: int = 200) -> str:
        """List transcript and metadata TXT files under one export path.

        How it works:
        - Resolves ``path`` relative to the configured Telegram TXT export root.
        - If ``path`` is a directory, recursively lists ``*.txt`` files below it.
        - If ``path`` is a single ``.txt`` file, returns just that file.
        - Returns at most ``max_results`` items.

        How to call it:
        - Use ``path="."`` to scan the whole export tree.
        - Use a narrower prefix such as ``path="chats/-1001234567890"`` to focus on
          one chat.
        - Example: ``list_export_files(path="chats/-1001234567890", max_results=50)``

        What it returns:
        - A plain-text list like ``<index>. <relative_path> (<size> bytes)``.
        - Paths are always shown relative to the export root.
        - If more files exist than returned, the output includes a truncation note.
        """
        resolved = self._service.resolve_path(path)
        files, limited = self._service.list_export_files(path, max_results=max_results)
        return format_file_list(self._service.display_path(resolved), files, limited=limited)
