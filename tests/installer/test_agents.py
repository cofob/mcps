import json
import subprocess
from pathlib import Path

import pytest

from mcps_workspace import agents
from mcps_workspace.agents import AgentRegistrationError, NativeAgentAdapter, OpenCodeAdapter, uvx_command
from mcps_workspace.models import AgentKind, ProfileRecord, ServiceKind


def _record() -> ProfileRecord:
    return ProfileRecord(service=ServiceKind.EMAIL, name="personal")


def test_uvx_command_uses_latest_git_main() -> None:
    assert uvx_command(_record()) == [
        "uvx",
        "--from",
        "git+https://github.com/cofob/mcps.git",
        "mcps-run",
        "email",
        "--profile",
        "personal",
    ]


@pytest.mark.parametrize(
    ("kind", "prefix", "expected"),
    [
        (
            AgentKind.CODEX,
            ("codex", "mcp", "add"),
            ["codex", "mcp", "add", "mcps-email-personal", "--"],
        ),
        (
            AgentKind.CLAUDE,
            ("claude", "mcp", "add", "--transport", "stdio", "--scope", "user"),
            [
                "claude",
                "mcp",
                "add",
                "--transport",
                "stdio",
                "--scope",
                "user",
                "mcps-email-personal",
                "--",
            ],
        ),
        (
            AgentKind.GEMINI,
            ("gemini", "mcp", "add", "--scope", "user", "--transport", "stdio"),
            [
                "gemini",
                "mcp",
                "add",
                "--scope",
                "user",
                "--transport",
                "stdio",
                "mcps-email-personal",
            ],
        ),
    ],
)
def test_native_agent_add_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    kind: AgentKind,
    prefix: tuple[str, ...],
    expected: list[str],
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str] | tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(agents, "_run", fake_run)
    adapter = NativeAgentAdapter(
        kind,
        kind.value,
        (tmp_path / "config",),
        prefix,
        (kind.value, "mcp", "remove"),
        None,
    )

    adapter.register(_record(), replace=False)

    assert commands[0][: len(expected)] == expected
    assert commands[0][-7:] == uvx_command(_record())


def test_native_adapter_restores_config_when_add_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.toml"
    config.write_text("original", encoding="utf-8")

    def fake_run(command: list[str] | tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        config.write_text("changed", encoding="utf-8")
        return subprocess.CompletedProcess(command, 1, "", "failure")

    monkeypatch.setattr(agents, "_run", fake_run)
    adapter = NativeAgentAdapter(
        AgentKind.CODEX,
        "codex",
        (config,),
        ("codex", "mcp", "add"),
        ("codex", "mcp", "remove"),
        None,
    )

    with pytest.raises(AgentRegistrationError, match="failure"):
        adapter.register(_record(), replace=False)

    assert config.read_text(encoding="utf-8") == "original"


def test_opencode_overlay_preserves_jsonc_and_merges_json(tmp_path: Path) -> None:
    config_dir = tmp_path / "opencode"
    config_dir.mkdir()
    jsonc = config_dir / "opencode.jsonc"
    jsonc.write_text('{\n  // keep this comment\n  "model": "example/model"\n}\n', encoding="utf-8")
    config = config_dir / "opencode.json"
    config.write_text('{"theme":"dark"}', encoding="utf-8")
    adapter = OpenCodeAdapter(config)

    result = adapter.register(_record(), replace=False)

    payload = json.loads(config.read_text(encoding="utf-8"))
    assert payload["theme"] == "dark"
    assert payload["mcp"]["mcps-email-personal"] == {
        "command": uvx_command(_record()),
        "enabled": True,
        "type": "local",
    }
    assert "keep this comment" in jsonc.read_text(encoding="utf-8")
    assert len(result.backup_paths) == 1
