from pathlib import Path

import pytest

from filesystem_mcp.config import FilesystemSettings
from filesystem_mcp.service import FilesystemService
from filesystem_mcp.tools import DirectoryTools, ReadTools, SearchTools, WriteTools


def make_service(tmp_path: Path) -> FilesystemService:
    return FilesystemService(FilesystemSettings(FILESYSTEM_ROOT_DIR=tmp_path))


def make_service_with_ignores(tmp_path: Path, patterns: list[str]) -> FilesystemService:
    return FilesystemService(
        FilesystemSettings(
            FILESYSTEM_ROOT_DIR=tmp_path,
            FILESYSTEM_IGNORE_PATTERNS=patterns,
        )
    )


@pytest.mark.asyncio
async def test_read_tool_formats_text_content(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / "note.txt").write_text("hello\n", encoding="utf-8")

    text = await ReadTools(service).read_file("note.txt")

    assert "Path: note.txt" in text
    assert "Content" in text
    assert "hello" in text


@pytest.mark.asyncio
async def test_patch_tool_formats_summary(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / "note.txt").write_text("before\n", encoding="utf-8")

    text = await WriteTools(service).patch_file(
        "note.txt",
        "@@ -1 +1 @@\n-before\n+after\n",
    )

    assert "Applied patch to note.txt." in text
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "after\n"


@pytest.mark.asyncio
async def test_directory_tool_lists_allowed_root(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    text = await DirectoryTools(service).list_allowed_directories()
    assert str(service.root_dir) in text


@pytest.mark.asyncio
async def test_search_tool_formats_file_matches(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('x')\n", encoding="utf-8")

    text = await SearchTools(service).search_files(".", "*.py")

    assert 'Search results for "*.py" under .' in text
    assert "src/main.py" in text


@pytest.mark.asyncio
async def test_search_within_files_tool_includes_filename_matches(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "release-notes.txt").write_text("no keyword here\n", encoding="utf-8")

    text = await SearchTools(service).search_within_files("docs", "release")

    assert 'Search within files for "release" under docs' in text
    assert "File: docs/release-notes.txt" in text
    assert "Filename match: release-notes.txt" in text


@pytest.mark.asyncio
async def test_list_directory_tool_hides_ignored_entries(tmp_path: Path) -> None:
    service = make_service_with_ignores(tmp_path, ["secret/", "*.log"])
    (tmp_path / "visible").mkdir()
    (tmp_path / "secret").mkdir()
    (tmp_path / "trace.log").write_text("hidden\n", encoding="utf-8")

    text = await DirectoryTools(service).list_directory(".")

    assert "visible" in text
    assert "secret" not in text
    assert "trace.log" not in text
