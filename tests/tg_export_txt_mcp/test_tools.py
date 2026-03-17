from pathlib import Path
from unittest.mock import patch

import pytest

from tg_export_txt_mcp.config import TgExportTxtSettings
from tg_export_txt_mcp.models import (
    ExportChatEntry,
    ExportFileEntry,
    ExportReadResult,
    ExportSearchMatch,
    ExportTopicEntry,
)
from tg_export_txt_mcp.service import TgExportTxtService
from tg_export_txt_mcp.tools import ChatTools, FileTools, ReadTools, SearchTools, TopicTools


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


@pytest.mark.asyncio
async def test_search_tool_forwards_date_filters(tmp_path: Path) -> None:
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

    with patch.object(service, "search_exports", return_value=(matches, False)) as search_mock:
        await SearchTools(service).search_exports(
            "chats/123",
            "hello",
            start_date="2026-03-01",
            end_date="2026-03-17",
        )

    search_mock.assert_called_once_with(
        "chats/123",
        "hello",
        max_results=200,
        start_date="2026-03-01",
        end_date="2026-03-17",
    )


@pytest.mark.asyncio
async def test_file_tool_formats_file_list(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    chats_dir = tmp_path / "chats"
    chats_dir.mkdir()
    files = [
        ExportFileEntry(
            path="chats/123/2026-03-w3.txt",
            absolute_path=str(tmp_path / "chats" / "123" / "2026-03-w3.txt"),
            size_bytes=12,
        )
    ]

    with patch.object(service, "list_export_files", return_value=(files, False)):
        text = await FileTools(service).list_export_files("chats")

    assert "TXT files under chats: 1 file(s)" in text
    assert "chats/123/2026-03-w3.txt (12 bytes)" in text


@pytest.mark.asyncio
async def test_chat_tools_format_chat_results(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    chats = [ExportChatEntry(chat_id="123", chat_name="Alice")]

    with patch.object(service, "list_chats", return_value=(chats, False)):
        list_text = await ChatTools(service).list_chats()

    with patch.object(service, "search_chats", return_value=(chats, False)):
        search_text = await ChatTools(service).search_chats("alce")

    assert "Chats: 1 match(es)" in list_text
    assert "123\tAlice" in list_text
    assert 'Search chats for "alce": 1 match(es)' in search_text
    assert "123\tAlice" in search_text


@pytest.mark.asyncio
async def test_topic_tools_format_topic_results(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    topics = [ExportTopicEntry(topic_id="42", topic_name="Release notes")]

    with patch.object(service, "list_topics", return_value=(topics, False)):
        text = await TopicTools(service).list_topics("123")

    assert "Topics for chat 123: 1 topic(s)" in text
    assert "42\tRelease notes" in text


@pytest.mark.asyncio
async def test_topic_search_tool_formats_topic_results(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    topics = [ExportTopicEntry(topic_id="42", topic_name="Release notes")]

    with patch.object(service, "search_topics", return_value=(topics, False)):
        text = await TopicTools(service).search_topics("123", "relase")

    assert 'Search topics in chat 123 for "relase": 1 match(es)' in text
    assert "42\tRelease notes" in text
