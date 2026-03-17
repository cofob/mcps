from tg_export_txt_mcp.formatters import format_search_results
from tg_export_txt_mcp.service import TgExportTxtService


class SearchTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def search_exports(self, path: str, query: str, max_results: int = 200) -> str:
        """Search TXT export files with ripgrep under one path inside the configured export root."""
        resolved = self._service.resolve_path(path)
        matches, limited = self._service.search_exports(path, query, max_results=max_results)
        return format_search_results(self._service.display_path(resolved), query, matches, limited=limited)
