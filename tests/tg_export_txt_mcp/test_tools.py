from pathlib import Path
from unittest.mock import patch

import pytest

from tg_export_txt_mcp.config import TgExportTxtSettings
from tg_export_txt_mcp.models import ExportReadResult, ExportSearchMatch
from tg_export_txt_mcp.service import TgExportTxtService
from tg_export_txt_mcp.tools import ReadTools, SearchTools


def make_service(tmp_path: Path) -> TgExportTxtService:
    return TgExportTxtService(TgExportTxtSettings(TG_EXPORT_TXT_ROOT_DIR=tmp_path))


@pytest.mark.asyncio
async def test_read_tool_formats_export_content(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    result = ExportReadResult(
        path="chats/123/2026-03-w3.txt",
        absolute_path=str(tmp_path / "chats" / "123" / "2026-03-w3.txt"),
        start_line=1,
        end_line=2,
        total_lines=2,
        content="hello\nworld",
    )

    with patch.object(service, "read_export_file", return_value=result):
        text = await ReadTools(service).read_export_file("chats/123/2026-03-w3.txt")

    assert "Path: chats/123/2026-03-w3.txt" in text
    assert "Lines: 1-2 of 2" in text
    assert "hello" in text


@pytest.mark.asyncio
async def test_search_tool_formats_matches(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    export_file = tmp_path / "chats" / "123" / "2026-03-w3.txt"
    export_file.parent.mkdir(parents=True)
    export_file.write_text("hello\n", encoding="utf-8")
    matches = [
        ExportSearchMatch(
            path="chats/123/2026-03-w3.txt",
            absolute_path=str(export_file),
            line_number=1,
            line_text="hello",
        )
    ]

    with patch.object(service, "search_exports", return_value=(matches, False)):
        text = await SearchTools(service).search_exports(".", "hello")

    assert 'Search for "hello" under .' in text
    assert "chats/123/2026-03-w3.txt:1: hello" in text
