import base64
import binascii
import fnmatch
import mimetypes
import os
import re
import shutil
import stat
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from filesystem_mcp.config import FilesystemSettings
from filesystem_mcp.models import (
    DirectoryEntry,
    FileMetadata,
    FileReadResult,
    SearchFileMatch,
    SearchWithinMatch,
    TreeNode,
)

_TEXT_MIME_PREFIXES = ("text/",)
_TEXT_MIME_TYPES = {
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-javascript",
    "application/typescript",
    "application/x-typescript",
    "application/x-yaml",
    "application/yaml",
    "application/toml",
    "application/x-sh",
    "application/x-shellscript",
}
_PATCH_HUNK_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


class FilesystemService:
    def __init__(self, settings: FilesystemSettings) -> None:
        self._settings = settings
        self._root_dir = settings.filesystem_root_dir

    @property
    def root_dir(self) -> Path:
        return self._root_dir

    def resolve_path(self, requested_path: str, *, allow_missing: bool = False) -> Path:
        normalized = requested_path.strip() or "."
        if normalized in {".", "./"}:
            candidate = self._root_dir
        else:
            raw_candidate = Path(normalized).expanduser()
            candidate = (
                raw_candidate
                if raw_candidate.is_absolute()
                else (self._root_dir / raw_candidate)
            )

        if allow_missing:
            resolved = candidate.resolve(strict=False)
            existing_parent = resolved
            while not existing_parent.exists():
                if existing_parent == existing_parent.parent:
                    raise ValueError(f"Parent directory does not exist: {resolved.parent}")
                existing_parent = existing_parent.parent
            self._assert_within_root(existing_parent.resolve())
            self._assert_within_root(resolved)
            return resolved

        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(f"Path does not exist: {candidate}") from exc

        self._assert_within_root(resolved)
        return resolved

    def _assert_within_root(self, path: Path) -> None:
        if not path.is_relative_to(self._root_dir):
            raise ValueError(f"Access denied outside root directory: {path}")

    def display_path(self, path: Path) -> str:
        if path == self._root_dir:
            return "."
        return str(path.relative_to(self._root_dir))

    def read_file(self, path: str) -> FileReadResult:
        resolved = self.resolve_path(path)
        if resolved.is_dir():
            raise ValueError("Cannot read a directory")
        data = resolved.read_bytes()
        mime_type = self._detect_mime_type(resolved)
        is_text = self._is_text_file(resolved, data, mime_type)
        is_image = mime_type.startswith("image/")
        if is_text and len(data) <= self._settings.max_inline_size:
            text = data.decode("utf-8")
            return FileReadResult(
                path=self.display_path(resolved),
                absolute_path=str(resolved),
                mime_type=mime_type,
                size=len(data),
                is_text=True,
                is_image=is_image,
                text=text,
            )
        if not is_text and len(data) <= self._settings.max_base64_size:
            return FileReadResult(
                path=self.display_path(resolved),
                absolute_path=str(resolved),
                mime_type=mime_type,
                size=len(data),
                is_text=False,
                is_image=is_image,
                binary_base64=base64.b64encode(data).decode("ascii"),
            )
        return FileReadResult(
            path=self.display_path(resolved),
            absolute_path=str(resolved),
            mime_type=mime_type,
            size=len(data),
            is_text=is_text,
            is_image=is_image,
        )

    def read_multiple_files(self, paths: Sequence[str]) -> list[FileReadResult]:
        return [self.read_file(path) for path in paths]

    def resource_content(self, path: str) -> str | bytes:
        result = self.read_file(path)
        if result.text is not None:
            return result.text
        if result.binary_base64 is not None:
            try:
                return base64.b64decode(result.binary_base64)
            except binascii.Error as exc:
                raise ValueError("Failed to decode binary file content") from exc
        raise ValueError("File is too large to expose as an MCP resource")

    def write_file(self, path: str, content: str) -> Path:
        resolved = self.resolve_path(path, allow_missing=True)
        if resolved.exists() and resolved.is_dir():
            raise ValueError("Cannot write to a directory")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return resolved

    def create_directory(self, path: str) -> Path:
        resolved = self.resolve_path(path, allow_missing=True)
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def copy_file(self, source: str, destination: str) -> Path:
        src = self.resolve_path(source)
        dst = self.resolve_path(destination, allow_missing=True)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return dst

    def move_file(self, source: str, destination: str) -> Path:
        src = self.resolve_path(source)
        dst = self.resolve_path(destination, allow_missing=True)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return dst

    def delete_file(self, path: str, *, recursive: bool = False) -> Path:
        resolved = self.resolve_path(path)
        if resolved.is_dir():
            if not recursive:
                raise ValueError("Refusing to delete a directory without recursive=true")
            shutil.rmtree(resolved)
        else:
            resolved.unlink()
        return resolved

    def modify_file(
        self,
        path: str,
        *,
        find: str,
        replace: str,
        all_occurrences: bool = True,
        regex: bool = False,
    ) -> tuple[Path, int]:
        resolved = self.resolve_path(path)
        if resolved.is_dir():
            raise ValueError("Cannot modify a directory")
        original = resolved.read_text(encoding="utf-8")
        if regex:
            compiled = re.compile(find)
            if all_occurrences:
                updated, count = compiled.subn(replace, original)
            elif find:
                updated, count = compiled.subn(replace, original, count=1)
            else:
                updated, count = original, 0
        elif all_occurrences:
            count = original.count(find)
            updated = original.replace(find, replace)
        else:
            count = 1 if find in original else 0
            updated = original.replace(find, replace, 1)
        resolved.write_text(updated, encoding="utf-8")
        return resolved, count

    def patch_file(self, path: str, patch: str) -> tuple[Path, int]:
        resolved = self.resolve_path(path)
        if resolved.is_dir():
            raise ValueError("Cannot patch a directory")
        original = resolved.read_text(encoding="utf-8").splitlines(keepends=True)
        updated, changed_lines = self._apply_unified_patch(original, patch)
        resolved.write_text("".join(updated), encoding="utf-8")
        return resolved, changed_lines

    def list_directory(self, path: str) -> list[DirectoryEntry]:
        resolved = self.resolve_path(path)
        if not resolved.is_dir():
            raise ValueError("Path is not a directory")
        entries: list[DirectoryEntry] = []
        for child in sorted(
            resolved.iterdir(),
            key=lambda item: (not item.is_dir(), item.name.lower()),
        ):
            info = child.stat()
            entries.append(
                DirectoryEntry(
                    name=child.name,
                    path=self.display_path(child),
                    is_dir=child.is_dir(),
                    size=info.st_size,
                    modified=datetime.fromtimestamp(info.st_mtime, tz=UTC),
                )
            )
        return entries

    def build_tree(
        self,
        path: str,
        *,
        depth: int = 3,
        follow_symlinks: bool = False,
    ) -> TreeNode:
        resolved = self.resolve_path(path)
        max_depth = max(depth, 0)

        def build(node_path: Path, current_depth: int) -> TreeNode:
            info = node_path.stat(follow_symlinks=follow_symlinks)
            node = TreeNode(
                name=node_path.name or str(node_path),
                path=self.display_path(node_path),
                is_dir=node_path.is_dir(),
                size=info.st_size,
                modified=datetime.fromtimestamp(info.st_mtime, tz=UTC),
            )
            if node.is_dir and (max_depth == 0 or current_depth < max_depth):
                children: list[TreeNode] = []
                for child in sorted(
                    node_path.iterdir(),
                    key=lambda item: (not item.is_dir(), item.name.lower()),
                ):
                    if child.is_symlink() and not follow_symlinks:
                        continue
                    try:
                        child_resolved = child.resolve(strict=True)
                    except FileNotFoundError:
                        continue
                    self._assert_within_root(child_resolved)
                    children.append(build(child, current_depth + 1))
                node.children.extend(children)
            return node

        return build(resolved, 0)

    def search_files(self, path: str, pattern: str) -> list[SearchFileMatch]:
        resolved = self.resolve_path(path)
        if not resolved.is_dir():
            raise ValueError("search_files requires a directory path")
        matches: list[SearchFileMatch] = []
        for current, dirnames, filenames in os.walk(resolved):
            current_path = Path(current)
            self._assert_within_root(current_path.resolve())
            names = [*dirnames, *filenames]
            for name in names:
                if not fnmatch.fnmatch(name.lower(), pattern.lower()):
                    continue
                matched = current_path / name
                matches.append(
                    SearchFileMatch(
                        path=self.display_path(matched),
                        absolute_path=str(matched),
                        is_dir=matched.is_dir(),
                    )
                )
                if len(matches) >= self._settings.max_search_results:
                    return matches
        return matches

    def search_within_files(
        self,
        path: str,
        substring: str,
        *,
        depth: int = 0,
        max_results: int | None = None,
    ) -> tuple[list[SearchWithinMatch], bool]:
        if not substring:
            raise ValueError("substring cannot be empty")
        resolved = self.resolve_path(path)
        if not resolved.is_dir():
            raise ValueError("search_within_files requires a directory path")
        result_limit = max_results or self._settings.max_search_results
        matches: list[SearchWithinMatch] = []
        limited = False
        for current, dirnames, filenames in os.walk(resolved):
            current_path = Path(current)
            rel_depth = (
                0
                if current_path == resolved
                else len(current_path.relative_to(resolved).parts)
            )
            dirnames.sort()
            filenames.sort()
            if depth > 0 and rel_depth >= depth:
                dirnames[:] = []
            for filename in filenames:
                file_path = current_path / filename
                self._assert_within_root(file_path.resolve())
                try:
                    info = file_path.stat()
                except OSError:
                    continue
                if info.st_size > self._settings.max_searchable_size:
                    continue
                data = file_path.read_bytes()
                mime_type = self._detect_mime_type(file_path)
                if not self._is_text_file(file_path, data, mime_type):
                    continue
                text = data.decode("utf-8")
                for index, line in enumerate(text.splitlines(), start=1):
                    if substring not in line:
                        continue
                    matches.append(
                        SearchWithinMatch(
                            path=self.display_path(file_path),
                            absolute_path=str(file_path),
                            line_number=index,
                            line_content=line,
                        )
                    )
                    if len(matches) >= result_limit:
                        limited = True
                        return matches, limited
        return matches, limited

    def get_file_info(self, path: str) -> FileMetadata:
        resolved = self.resolve_path(path)
        info = resolved.stat()
        return FileMetadata(
            path=self.display_path(resolved),
            absolute_path=str(resolved),
            size=info.st_size,
            created=datetime.fromtimestamp(info.st_ctime, tz=UTC),
            modified=datetime.fromtimestamp(info.st_mtime, tz=UTC),
            accessed=datetime.fromtimestamp(info.st_atime, tz=UTC),
            is_directory=resolved.is_dir(),
            is_file=resolved.is_file(),
            permissions=stat.filemode(info.st_mode),
        )

    def list_allowed_directories(self) -> list[str]:
        return [str(self._root_dir)]

    def _detect_mime_type(self, path: Path) -> str:
        mime_type, _ = mimetypes.guess_type(path.name)
        return mime_type or "application/octet-stream"

    def _is_text_file(self, path: Path, data: bytes, mime_type: str) -> bool:
        if mime_type.startswith(_TEXT_MIME_PREFIXES):
            return True
        if mime_type in _TEXT_MIME_TYPES:
            return True
        if any(tag in mime_type for tag in ("+json", "+xml", "+yaml")):
            return True
        if b"\x00" in data[:4096]:
            return False
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return path.suffix.lower() not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".ico",
            ".pdf",
            ".zip",
            ".gz",
            ".mp3",
            ".flac",
            ".ogg",
            ".mp4",
            ".mkv",
        }

    def _apply_unified_patch(
        self,
        original: Sequence[str],
        patch: str,
    ) -> tuple[list[str], int]:
        lines = patch.splitlines(keepends=True)
        result: list[str] = []
        cursor = 0
        changed_lines = 0
        saw_hunk = False
        index = 0
        while index < len(lines):
            line = lines[index]
            if line.startswith(("---", "+++", "diff ", "index ")):
                index += 1
                continue
            if line.startswith("@@"):
                saw_hunk = True
                hunk_start = self._parse_hunk_start(line)
                result.extend(original[cursor:hunk_start])
                cursor = hunk_start
                index, cursor, hunk_result, hunk_changed_lines = self._apply_patch_hunk(
                    original,
                    lines,
                    index + 1,
                    cursor,
                )
                result.extend(hunk_result)
                changed_lines += hunk_changed_lines
                continue
            if not line.strip():
                index += 1
                continue
            raise ValueError(f"Unexpected patch content outside hunk: {line.strip()}")
        if not saw_hunk:
            raise ValueError("Patch did not contain any hunks")
        result.extend(original[cursor:])
        return result, changed_lines

    def _parse_hunk_start(self, header_line: str) -> int:
        match = _PATCH_HUNK_RE.match(header_line.rstrip("\n"))
        if match is None:
            raise ValueError(f"Invalid patch hunk header: {header_line.strip()}")
        old_start = int(match.group("old_start"))
        return max(old_start - 1, 0)

    def _apply_patch_hunk(
        self,
        original: Sequence[str],
        patch_lines: Sequence[str],
        start_index: int,
        cursor: int,
    ) -> tuple[int, int, list[str], int]:
        hunk_result: list[str] = []
        changed_lines = 0
        index = start_index
        while index < len(patch_lines):
            hunk_line = patch_lines[index]
            if hunk_line.startswith("@@"):
                break
            if hunk_line.startswith("\\"):
                index += 1
                continue
            prefix = hunk_line[:1]
            content = hunk_line[1:]
            if prefix == " ":
                self._expect_patch_line(original, cursor, content)
                hunk_result.append(original[cursor])
                cursor += 1
            elif prefix == "-":
                self._expect_patch_line(original, cursor, content)
                cursor += 1
                changed_lines += 1
            elif prefix == "+":
                hunk_result.append(content)
                changed_lines += 1
            else:
                raise ValueError(f"Unsupported patch line: {hunk_line.strip()}")
            index += 1
        return index, cursor, hunk_result, changed_lines

    def _expect_patch_line(
        self,
        original: Sequence[str],
        cursor: int,
        expected: str,
    ) -> None:
        if cursor >= len(original):
            raise ValueError("Patch references content beyond end of file")
        if original[cursor] != expected:
            raise ValueError("Patch context does not match current file contents")
