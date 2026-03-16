from pathlib import Path

import pytest

from filesystem_mcp.config import FilesystemSettings
from filesystem_mcp.service import FilesystemService


def make_service(tmp_path: Path) -> FilesystemService:
    settings = FilesystemSettings(FILESYSTEM_ROOT_DIR=tmp_path)
    return FilesystemService(settings)


def test_write_and_read_relative_path_stay_under_root(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    written = service.write_file("notes/todo.txt", "hello")
    assert written == tmp_path / "notes" / "todo.txt"

    read = service.read_file("notes/todo.txt")
    assert read.path == "notes/todo.txt"
    assert read.text == "hello"


def test_symlink_escape_is_rejected_for_write(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    outside_dir = tmp_path.parent / "outside-dir"
    outside_dir.mkdir(exist_ok=True)
    (tmp_path / "escape").symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(ValueError, match="Access denied outside root directory"):
        service.write_file("escape/secret.txt", "blocked")


def test_patch_file_applies_unified_diff(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    target = tmp_path / "app.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    resolved, changed_lines = service.patch_file(
        "app.txt",
        (
            "--- app.txt\n"
            "+++ app.txt\n"
            "@@ -1,3 +1,3 @@\n"
            " alpha\n"
            "-beta\n"
            "+delta\n"
            " gamma\n"
        ),
    )

    assert resolved == target
    assert changed_lines == 2
    assert target.read_text(encoding="utf-8") == "alpha\ndelta\ngamma\n"


def test_patch_file_rejects_outside_root(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("hello\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Access denied outside root directory"):
        service.patch_file(str(outside), "@@ -1 +1 @@\n-hello\n+bye\n")


def test_list_directory_and_tree_use_relative_paths(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")

    entries = service.list_directory(".")
    assert entries[0].path == "src"

    tree = service.build_tree(".")
    assert tree.path == "."
    assert tree.children[0].path == "src"


def test_search_within_files_finds_matching_lines(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.txt").write_text("hello\nworld\n", encoding="utf-8")
    (tmp_path / "docs" / "b.txt").write_text("world again\n", encoding="utf-8")

    matches, limited = service.search_within_files("docs", "world", max_results=10)

    assert not limited
    assert [match.path for match in matches] == ["docs/a.txt", "docs/b.txt"]
    assert [match.line_number for match in matches] == [2, 1]
