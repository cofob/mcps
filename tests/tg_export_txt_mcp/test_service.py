import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tg_export_txt_mcp.config import TgExportTxtSettings
from tg_export_txt_mcp.service import TgExportTxtService


def make_service(tmp_path: Path) -> TgExportTxtService:
    return TgExportTxtService(TgExportTxtSettings(TG_EXPORT_TXT_ROOT_DIR=tmp_path))


def test_read_export_file_reads_selected_lines(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    export_file = tmp_path / "chats" / "123" / "2026-03-w3.txt"
    export_file.parent.mkdir(parents=True)
    export_file.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")

    result = service.read_export_file("chats/123/2026-03-w3.txt", start_line=2, max_lines=2)

    assert result.path == "chats/123/2026-03-w3.txt"
    assert result.start_line == 2
    assert result.end_line == 3
    assert result.total_lines == 4
    assert result.content == "line2\nline3"


def test_read_export_file_rejects_non_txt_files(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    mapping_file = tmp_path / "chats.json"
    mapping_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match=r"Only \.txt export files"):
        service.read_export_file("chats.json")


def test_list_export_files_lists_txt_files_under_directory(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    chat_dir = tmp_path / "chats" / "123"
    chat_dir.mkdir(parents=True)
    first_file = chat_dir / "2026-03-w3.txt"
    second_file = chat_dir / "2026-03-w4.txt"
    first_file.write_text("hello\n", encoding="utf-8")
    second_file.write_text("world\n", encoding="utf-8")

    files, limited = service.list_export_files("chats", max_results=10)

    assert not limited
    assert [file.path for file in files] == [
        "chats/123/2026-03-w3.txt",
        "chats/123/2026-03-w4.txt",
    ]
    assert files[0].size_bytes == len(b"hello\n")


def test_list_export_files_applies_limit(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    chat_dir = tmp_path / "chats" / "123"
    chat_dir.mkdir(parents=True)
    for index in range(3):
        (chat_dir / f"2026-03-w{index + 1}.txt").write_text("x\n", encoding="utf-8")

    files, limited = service.list_export_files("chats", max_results=2)

    assert limited
    assert len(files) == 2


def test_list_chats_reads_chat_mapping_file(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / "chats.txt").write_text("123\tAlice\n456\tBob\n", encoding="utf-8")

    chats, limited = service.list_chats(max_results=10)

    assert not limited
    assert [(chat.chat_id, chat.chat_name) for chat in chats] == [("123", "Alice"), ("456", "Bob")]


def test_search_chats_filters_by_id_or_name(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (tmp_path / "chats.txt").write_text("123\tAlice Example\n456\tBob\n", encoding="utf-8")

    by_name, limited_by_name = service.search_chats("alice", max_results=10)
    by_id, limited_by_id = service.search_chats("456", max_results=10)

    assert not limited_by_name
    assert not limited_by_id
    assert [(chat.chat_id, chat.chat_name) for chat in by_name] == [("123", "Alice Example")]
    assert [(chat.chat_id, chat.chat_name) for chat in by_id] == [("456", "Bob")]


def test_list_topics_reads_per_chat_topic_mapping_file(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    topic_dir = tmp_path / "chats" / "123"
    topic_dir.mkdir(parents=True)
    (topic_dir / "topics.txt").write_text("1\tGeneral\n42\tRelease notes\n", encoding="utf-8")

    topics, limited = service.list_topics("123", max_results=10)

    assert not limited
    assert [(topic.topic_id, topic.topic_name) for topic in topics] == [("1", "General"), ("42", "Release notes")]


def test_search_exports_uses_rg_json_output(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    export_file = tmp_path / "chats" / "123" / "2026-03-w3.txt"
    export_file.parent.mkdir(parents=True)
    export_file.write_text("hello\nmatch me\n", encoding="utf-8")
    rg_stdout = "\n".join(
        [
            json.dumps(
                {
                    "type": "match",
                    "data": {
                        "path": {"text": str(export_file)},
                        "line_number": 2,
                        "lines": {"text": "match me\n"},
                    },
                }
            )
        ]
    )
    process = Mock()
    process.stdout = iter([f"{rg_stdout}\n"])
    process.stderr = Mock(read=Mock(return_value=""))
    process.wait = Mock(return_value=0)
    process.poll = Mock(return_value=0)

    with patch("tg_export_txt_mcp.service.subprocess.Popen", return_value=process) as popen_mock:
        matches, limited = service.search_exports(".", "match", max_results=10)

    assert not limited
    assert len(matches) == 1
    assert matches[0].path == "chats/123/2026-03-w3.txt"
    assert matches[0].line_number == 2
    assert matches[0].line_text == "match me"
    popen_mock.assert_called_once()


def test_search_exports_stops_after_max_results(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    export_file = tmp_path / "chats" / "123" / "2026-03-w3.txt"
    export_file.parent.mkdir(parents=True)
    export_file.write_text("match 1\nmatch 2\nmatch 3\n", encoding="utf-8")
    rg_lines = [
        json.dumps(
            {
                "type": "match",
                "data": {
                    "path": {"text": str(export_file)},
                    "line_number": index,
                    "lines": {"text": f"match {index}\n"},
                },
            }
        )
        for index in range(1, 4)
    ]
    process = Mock()
    process.stdout = iter(f"{line}\n" for line in rg_lines)
    process.stderr = Mock(read=Mock(return_value=""))
    process.wait = Mock(return_value=-15)
    process.poll = Mock(side_effect=[None, -15])

    with patch("tg_export_txt_mcp.service.subprocess.Popen", return_value=process):
        matches, limited = service.search_exports(".", "match", max_results=2)

    assert limited
    assert [match.line_number for match in matches] == [1, 2]
    process.terminate.assert_called_once()
    process.kill.assert_not_called()


def test_search_exports_rejects_missing_rg(tmp_path: Path) -> None:
    settings = TgExportTxtSettings(TG_EXPORT_TXT_ROOT_DIR=tmp_path, TG_EXPORT_TXT_RG_PATH="missing-rg")
    service = TgExportTxtService(settings)

    with (
        patch("tg_export_txt_mcp.service.subprocess.Popen", side_effect=FileNotFoundError),
        pytest.raises(ValueError, match="rg executable not found"),
    ):
        service.search_exports(".", "match")
