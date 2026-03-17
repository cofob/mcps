from tg_export_txt_mcp.formatters import format_file_list
from tg_export_txt_mcp.service import TgExportTxtService


class FileTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def list_export_files(self, path: str = ".", max_results: int = 200) -> str:
        """List TXT export files under one path inside the configured export root."""
        resolved = self._service.resolve_path(path)
        files, limited = self._service.list_export_files(path, max_results=max_results)
        return format_file_list(self._service.display_path(resolved), files, limited=limited)
