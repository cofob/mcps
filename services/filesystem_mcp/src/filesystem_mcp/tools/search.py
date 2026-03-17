from filesystem_mcp.formatters import format_search_files, format_search_within_files
from filesystem_mcp.service import FilesystemService


class SearchTools:
    def __init__(self, service: FilesystemService) -> None:
        self._service = service

    async def search_files(self, path: str, pattern: str) -> str:
        """Recursively search for file and directory names matching a pattern."""
        resolved = self._service.resolve_path(path)
        matches = self._service.search_files(path, pattern)
        return format_search_files(self._service.display_path(resolved), pattern, matches)

    async def search_within_files(
        self,
        path: str,
        substring: str,
        depth: int = 0,
        max_results: int = 1000,
    ) -> str:
        """Search for plain text matches inside files under one directory."""
        resolved = self._service.resolve_path(path)
        matches, limited = self._service.search_within_files(
            path,
            substring,
            depth=depth,
            max_results=max_results,
        )
        return format_search_within_files(
            self._service.display_path(resolved),
            substring,
            matches,
            limited=limited,
        )
