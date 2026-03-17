from pathlib import Path

import pytest

from filesystem_mcp.config import FilesystemSettings
from filesystem_mcp.service import FilesystemService


def make_service(tmp_path: Path) -> FilesystemService:
    settings = FilesystemSettings(FILESYSTEM_ROOT_DIR=tmp_path)
    return FilesystemService(settings)


def make_service_with_ignores(tmp_path: Path, patterns: list[str]) -> FilesystemService:
    settings = FilesystemSettings(
        FILESYSTEM_ROOT_DIR=tmp_path,
        FILESYSTEM_IGNORE_PATTERNS=patterns,
    )
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
    assert [match.match_type for match in matches] == ["content", "content"]


def test_search_within_files_also_finds_matching_filenames(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "world-notes.txt").write_text("hello\n", encoding="utf-8")

    matches, limited = service.search_within_files("docs", "world", max_results=10)

    assert not limited
    assert len(matches) == 1
    assert matches[0].path == "docs/world-notes.txt"
    assert matches[0].line_number is None
    assert matches[0].line_content == "world-notes.txt"
    assert matches[0].match_type == "filename"


def test_excluded_paths_are_rejected_for_direct_access(tmp_path: Path) -> None:
    service = make_service_with_ignores(tmp_path, ["secret/", "*.log"])
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "plan.txt").write_text("hidden\n", encoding="utf-8")
    (tmp_path / "events.log").write_text("hidden\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"Access denied for excluded path: secret/plan\.txt"):
        service.read_file("secret/plan.txt")

    with pytest.raises(ValueError, match=r"Access denied for excluded path: events\.log"):
        service.get_file_info("events.log")


def test_excluded_paths_are_hidden_from_directory_views(tmp_path: Path) -> None:
    service = make_service_with_ignores(tmp_path, ["secret/", "*.log"])
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "plan.txt").write_text("hidden\n", encoding="utf-8")
    (tmp_path / "events.log").write_text("hidden\n", encoding="utf-8")

    entries = service.list_directory(".")
    assert [entry.path for entry in entries] == ["src"]

    tree = service.build_tree(".")
    assert [child.path for child in tree.children] == ["src"]


def test_excluded_paths_are_pruned_from_searches(tmp_path: Path) -> None:
    service = make_service_with_ignores(tmp_path, ["secret/", "*.log"])
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "release.txt").write_text("release notes\n", encoding="utf-8")
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "release.txt").write_text("release notes\n", encoding="utf-8")
    (tmp_path / "service.log").write_text("release notes\n", encoding="utf-8")

    file_matches = service.search_files(".", "*.txt")
    assert [match.path for match in file_matches] == ["docs/release.txt"]

    content_matches, limited = service.search_within_files(".", "release", max_results=10)
    assert not limited
    assert [match.path for match in content_matches] == ["docs/release.txt", "docs/release.txt"]
    assert [match.match_type for match in content_matches] == ["filename", "content"]


def test_root_gitignore_excludes_paths_from_all_tools(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / ".gitignore").write_text("secret/\n*.log\n", encoding="utf-8")
    (tmp_path / "visible.txt").write_text("release\n", encoding="utf-8")
    (tmp_path / "hidden.log").write_text("release\n", encoding="utf-8")
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "notes.txt").write_text("release\n", encoding="utf-8")

    entries = service.list_directory(".")
    assert [entry.path for entry in entries] == [".gitignore", "visible.txt"]

    with pytest.raises(ValueError, match=r"Access denied for excluded path: secret/notes\.txt"):
        service.read_file("secret/notes.txt")

    matches = service.search_files(".", "*.txt")
    assert [match.path for match in matches] == ["visible.txt"]


def test_nested_gitignore_applies_within_its_directory(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / ".gitignore").write_text("drafts/\nsecret*.txt\n", encoding="utf-8")
    (tmp_path / "docs" / "public.txt").write_text("visible\n", encoding="utf-8")
    (tmp_path / "docs" / "secret-plan.txt").write_text("hidden\n", encoding="utf-8")
    (tmp_path / "docs" / "drafts").mkdir()
    (tmp_path / "docs" / "drafts" / "chapter.txt").write_text("hidden\n", encoding="utf-8")

    entries = service.list_directory("docs")
    assert [entry.path for entry in entries] == ["docs/.gitignore", "docs/public.txt"]

    with pytest.raises(ValueError, match=r"Access denied for excluded path: docs/secret-plan\.txt"):
        service.get_file_info("docs/secret-plan.txt")
