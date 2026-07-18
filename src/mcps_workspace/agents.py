import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter

from mcp_common import JsonArray, JsonObject, get_object, is_json_object
from mcps_workspace.models import AgentKind, ProfileRecord
from mcps_workspace.storage import _atomic_write

DEFAULT_SOURCE = "git+https://github.com/cofob/mcps.git"


class AgentRegistrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistrationResult:
    agent: AgentKind
    server_name: str
    backup_paths: tuple[Path, ...] = ()


class AgentAdapter(Protocol):
    kind: AgentKind

    def detected(self) -> bool: ...

    def exists(self, server_name: str) -> bool: ...

    def register(self, record: ProfileRecord, *, replace: bool) -> RegistrationResult: ...


def uvx_command(record: ProfileRecord, source: str = DEFAULT_SOURCE) -> list[str]:
    return [
        "uvx",
        "--from",
        source,
        "mcps-run",
        record.service.value,
        "--profile",
        record.name,
    ]


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - executable names are fixed agent adapters.
        list(command),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.mcps-backup-{_timestamp()}")
    shutil.copy2(path, backup)
    return backup


def _snapshot(paths: Sequence[Path]) -> dict[Path, bytes | None]:
    return {path: path.read_bytes() if path.exists() else None for path in paths}


def _restore(snapshot: dict[Path, bytes | None]) -> None:
    for path, content in snapshot.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.restore")
            temporary.write_bytes(content)
            temporary.replace(path)


class NativeAgentAdapter:
    def __init__(
        self,
        kind: AgentKind,
        executable: str,
        config_paths: Sequence[Path],
        add_prefix: Sequence[str],
        remove_prefix: Sequence[str],
        get_prefix: Sequence[str] | None,
    ) -> None:
        self.kind = kind
        self._executable = executable
        self._config_paths = tuple(config_paths)
        self._add_prefix = tuple(add_prefix)
        self._remove_prefix = tuple(remove_prefix)
        self._get_prefix = tuple(get_prefix) if get_prefix is not None else None

    def detected(self) -> bool:
        return shutil.which(self._executable) is not None

    def exists(self, server_name: str) -> bool:
        if self._get_prefix is not None:
            return _run((*self._get_prefix, server_name)).returncode == 0
        settings_path = self._config_paths[0]
        if not settings_path.exists():
            return False
        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        servers = payload.get("mcpServers") if isinstance(payload, dict) else None
        return isinstance(servers, dict) and server_name in servers

    def register(self, record: ProfileRecord, *, replace: bool) -> RegistrationResult:
        snapshot = _snapshot(self._config_paths)
        backups = tuple(backup for path in self._config_paths if (backup := _backup(path)) is not None)
        try:
            if replace and self.exists(record.server_name):
                removed = _run((*self._remove_prefix, record.server_name))
                if removed.returncode != 0:
                    raise AgentRegistrationError(_command_error(self.kind, "remove", removed))
            added = _run(self._add_command(record))
            if added.returncode != 0:
                raise AgentRegistrationError(_command_error(self.kind, "add", added))
        except BaseException:
            _restore(snapshot)
            raise
        return RegistrationResult(agent=self.kind, server_name=record.server_name, backup_paths=backups)

    def _add_command(self, record: ProfileRecord) -> tuple[str, ...]:
        command = tuple(uvx_command(record))
        if self.kind is AgentKind.CODEX:
            return (*self._add_prefix, record.server_name, "--", *command)
        if self.kind is AgentKind.CLAUDE:
            return (*self._add_prefix, record.server_name, "--", *command)
        return (*self._add_prefix, record.server_name, *command)


def _command_error(
    kind: AgentKind,
    action: str,
    completed: subprocess.CompletedProcess[str],
) -> str:
    detail = (completed.stderr or completed.stdout).strip().replace("\n", " ")[:500]
    return f"{kind.display_name} MCP {action} failed: {detail or f'exit code {completed.returncode}'}"


class OpenCodeAdapter:
    kind = AgentKind.OPENCODE

    def __init__(self, config_path: Path | None = None) -> None:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        self.config_path = config_path or (base / "opencode" / "opencode.json")

    def detected(self) -> bool:
        return shutil.which("opencode") is not None

    def _load(self) -> JsonObject:
        if not self.config_path.exists():
            return {}
        try:
            payload: JsonObject = TypeAdapter(JsonObject).validate_json(self.config_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise AgentRegistrationError(f"OpenCode config is not valid JSON: {self.config_path}") from exc
        return payload

    def exists(self, server_name: str) -> bool:
        servers = self._load().get("mcp")
        return is_json_object(servers) and server_name in servers

    def register(self, record: ProfileRecord, *, replace: bool) -> RegistrationResult:
        payload = self._load()
        servers = get_object(payload, "mcp", context="OpenCode config")
        payload["mcp"] = servers
        if record.server_name in servers and not replace:
            raise AgentRegistrationError(f"OpenCode already contains {record.server_name!r}.")
        backup = _backup(self.config_path)
        command: JsonArray = list(uvx_command(record))
        servers[record.server_name] = {
            "type": "local",
            "command": command,
            "enabled": True,
        }
        _atomic_write(self.config_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        backups = (backup,) if backup is not None else ()
        return RegistrationResult(agent=self.kind, server_name=record.server_name, backup_paths=backups)


def agent_adapters() -> dict[AgentKind, AgentAdapter]:
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    claude_config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude"))
    claude_mcp_config = (
        claude_config_dir / ".claude.json" if "CLAUDE_CONFIG_DIR" in os.environ else home / ".claude.json"
    )
    return {
        AgentKind.CODEX: NativeAgentAdapter(
            AgentKind.CODEX,
            "codex",
            (codex_home / "config.toml",),
            ("codex", "mcp", "add"),
            ("codex", "mcp", "remove"),
            ("codex", "mcp", "get"),
        ),
        AgentKind.CLAUDE: NativeAgentAdapter(
            AgentKind.CLAUDE,
            "claude",
            (claude_mcp_config,),
            ("claude", "mcp", "add", "--transport", "stdio", "--scope", "user"),
            ("claude", "mcp", "remove", "--scope", "user"),
            None,
        ),
        AgentKind.GEMINI: NativeAgentAdapter(
            AgentKind.GEMINI,
            "gemini",
            (home / ".gemini" / "settings.json",),
            ("gemini", "mcp", "add", "--scope", "user", "--transport", "stdio"),
            ("gemini", "mcp", "remove", "--scope", "user"),
            None,
        ),
        AgentKind.OPENCODE: OpenCodeAdapter(),
    }
