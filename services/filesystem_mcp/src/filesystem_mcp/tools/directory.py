from filesystem_mcp.formatters import (
    format_allowed_directories,
    format_directory_list,
    format_summary,
    format_tree,
)
from filesystem_mcp.service import FilesystemService


class DirectoryTools:
    def __init__(self, service: FilesystemService) -> None:
        self._service = service

    async def list_directory(self, path: str) -> str:
        """List one directory under the configured filesystem root."""
        resolved = self._service.resolve_path(path)
        entries = self._service.list_directory(path)
        return format_directory_list(self._service.display_path(resolved), entries)

    async def create_directory(self, path: str) -> str:
        """Create a directory under the configured filesystem root."""
        resolved = self._service.create_directory(path)
        return format_summary(f"Created directory {self._service.display_path(resolved)}.")

    async def tree(
        self,
        path: str,
        depth: int = 3,
        follow_symlinks: bool = False,
    ) -> str:
        """Show a directory tree rooted at one path."""
        return format_tree(
            self._service.build_tree(
                path,
                depth=depth,
                follow_symlinks=follow_symlinks,
            )
        )

    async def list_allowed_directories(self) -> str:
        """Show which root directories this server can access."""
        return format_allowed_directories(self._service.list_allowed_directories())
