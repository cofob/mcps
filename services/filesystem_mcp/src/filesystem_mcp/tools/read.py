from filesystem_mcp.formatters import format_file_read, format_multiple_file_reads
from filesystem_mcp.service import FilesystemService


class ReadTools:
    def __init__(self, service: FilesystemService) -> None:
        self._service = service

    async def read_file(self, path: str) -> str:
        """Read one file from the configured filesystem root."""
        return format_file_read(self._service.read_file(path))

    async def read_multiple_files(self, paths: list[str]) -> str:
        """Read multiple files in one call."""
        return format_multiple_file_reads(self._service.read_multiple_files(paths))
