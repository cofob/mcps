from pathlib import Path

import pytest

from filesystem_mcp.config import FilesystemSettings
from filesystem_mcp.service import FilesystemService
from filesystem_mcp.tools import DirectoryTools, ReadTools, SearchTools, WriteTools


def make_service(tmp_path: Path) -> FilesystemService:
    return FilesystemService(FilesystemSettings(FILESYSTEM_ROOT_DIR=tmp_path))


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
