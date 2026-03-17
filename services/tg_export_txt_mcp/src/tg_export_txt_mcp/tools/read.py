from tg_export_txt_mcp.formatters import format_read_result
from tg_export_txt_mcp.service import TgExportTxtService


class ReadTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def read_export_file(self, path: str, start_line: int = 1, max_lines: int = 400) -> str:
        """Read a slice of one exported TXT file.

        How it works:
        - Resolves ``path`` relative to the configured Telegram TXT export root.
        - Only ``.txt`` files are allowed; directories are rejected.
        - Reads from ``start_line`` and returns up to ``max_lines`` lines.

        How to call it:
        - Pass a path relative to the export root, usually under ``chats/...``.
        - Example: ``read_export_file(path="chats/-1001234567890/2026-03-w3.txt")``
        - To continue reading later in the file:
          ``read_export_file(path="chats/-1001234567890/2026-03-w3.txt", start_line=401, max_lines=400)``

        What it returns:
        - A plain-text block with the relative path, absolute path, covered line range,
          total line count, and the selected content.
        - This is best used after ``list_export_files`` or ``search_exports`` identifies
          the file you want.
        """
        result = self._service.read_export_file(path, start_line=start_line, max_lines=max_lines)
        return format_read_result(result)
