from filesystem_mcp.formatters import format_summary
from filesystem_mcp.service import FilesystemService


class WriteTools:
    def __init__(self, service: FilesystemService) -> None:
        self._service = service

    async def write_file(self, path: str, content: str) -> str:
        """Create or overwrite one text file."""
        resolved = self._service.write_file(path, content)
        return format_summary(
            f"Wrote {len(content.encode('utf-8'))} bytes to "
            f"{self._service.display_path(resolved)}."
        )

    async def copy_file(self, source: str, destination: str) -> str:
        """Copy one file or directory to another path."""
        resolved = self._service.copy_file(source, destination)
        return format_summary(f"Copied content to {self._service.display_path(resolved)}.")

    async def move_file(self, source: str, destination: str) -> str:
        """Move or rename one file or directory."""
        resolved = self._service.move_file(source, destination)
        return format_summary(f"Moved content to {self._service.display_path(resolved)}.")

    async def delete_file(self, path: str, recursive: bool = False) -> str:
        """Delete one file or directory."""
        resolved = self._service.delete_file(path, recursive=recursive)
        return format_summary(f"Deleted {self._service.display_path(resolved)}.")

    async def modify_file(
        self,
        path: str,
        find: str,
        replace: str,
        all_occurrences: bool = True,
        regex: bool = False,
    ) -> str:
        """Update a file using plain-text or regex find/replace."""
        resolved, replacements = self._service.modify_file(
            path,
            find=find,
            replace=replace,
            all_occurrences=all_occurrences,
            regex=regex,
        )
        return format_summary(
            f"Modified {self._service.display_path(resolved)} with {replacements} "
            "replacement(s)."
        )

    async def patch_file(self, path: str, patch: str) -> str:
        """Apply a unified diff patch to one file."""
        resolved, changed_lines = self._service.patch_file(path, patch)
        return format_summary(
            f"Applied patch to {self._service.display_path(resolved)}. "
            f"Changed lines: {changed_lines}."
        )
