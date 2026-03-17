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
