from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tg_export_txt_mcp.config import TgExportTxtSettings
from tg_export_txt_mcp.service import TgExportTxtService
from tg_export_txt_mcp.tools import CliTools


def make_service(tmp_path: Path) -> TgExportTxtService:
    return TgExportTxtService(TgExportTxtSettings(TG_EXPORT_TXT_ROOT_DIR=tmp_path))


def test_run_cli_executes_command_via_bash(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    completed = Mock(return_value=None)
    completed.stdout = "hello\n"
    completed.stderr = ""
    completed.returncode = 0

    with patch("tg_export_txt_mcp.service.subprocess.run", return_value=completed) as run_mock:
        result = service.run_cli("cat chats.txt")

    assert result.exit_code == 0
    assert result.stdout == "hello\n"
    assert result.cwd == "."
    run_mock.assert_called_once()
    assert run_mock.call_args.args[0] == ["bash", "-lc", "cat chats.txt"]


def test_run_cli_allows_shell_operators(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    completed = Mock(return_value=None)
    completed.stdout = "hello\n"
    completed.stderr = ""
    completed.returncode = 0

    with patch("tg_export_txt_mcp.service.subprocess.run", return_value=completed) as run_mock:
        result = service.run_cli("rg foo chats | head")

    assert result.exit_code == 0
    assert run_mock.call_args.args[0] == ["bash", "-lc", "rg foo chats | head"]


@pytest.mark.asyncio
async def test_run_cli_tool_formats_output(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with patch.object(service, "run_cli") as run_cli_mock:
        run_cli_mock.return_value.command = "cat chats.txt"
        run_cli_mock.return_value.cwd = "."
        run_cli_mock.return_value.exit_code = 0
        run_cli_mock.return_value.stdout = "hello"
        run_cli_mock.return_value.stderr = ""
        run_cli_mock.return_value.truncated = False
        text = await CliTools(service).run_cli("cat chats.txt")

    assert "Command: cat chats.txt" in text
    assert "Exit code: 0" in text
    assert "Stdout" in text
