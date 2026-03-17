from tg_export_txt_mcp.formatters import format_read_result
from tg_export_txt_mcp.service import TgExportTxtService


class ReadTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def read_export_file(self, path: str, start_line: int = 1, max_lines: int = 400) -> str:
        """Read one TXT export file under the configured Telegram TXT export root."""
        result = self._service.read_export_file(path, start_line=start_line, max_lines=max_lines)
        return format_read_result(result)
