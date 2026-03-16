from filesystem_mcp.formatters import format_file_info
from filesystem_mcp.service import FilesystemService


class InfoTools:
    def __init__(self, service: FilesystemService) -> None:
        self._service = service

    async def get_file_info(self, path: str) -> str:
        """Get metadata for one file or directory."""
        return format_file_info(self._service.get_file_info(path))
