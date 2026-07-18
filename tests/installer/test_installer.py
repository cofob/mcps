from collections import deque
from pathlib import Path

import pytest

from mcps_workspace import installer
from mcps_workspace.agents import RegistrationResult
from mcps_workspace.models import AgentKind, ProfileRecord, SecretStoreKind, ServiceKind
from mcps_workspace.prompts import PromptIO
from mcps_workspace.secrets import FileSecretBackend, store_profile_secrets
from mcps_workspace.storage import ProfileStore
from mcps_workspace.validation import ProfileValidationError


class ScriptedPrompt(PromptIO):
    def __init__(
        self,
        *,
        text: list[str],
        confirms: list[bool],
        selects: list[str] | None = None,
        checkboxes: list[list[str]] | None = None,
    ) -> None:
        self.text_answers = deque(text)
        self.confirm_answers = deque(confirms)
        self.select_answers = deque(selects or [])
        self.checkbox_answers = deque(checkboxes or [])
        self.messages: list[str] = []

    async def text(self, message: str, *, default: str = "", secret: bool = False) -> str:
        del message, default, secret
        return self.text_answers.popleft()

    async def confirm(self, message: str, *, default: bool = False) -> bool:
        del message, default
        return self.confirm_answers.popleft()

    async def select(self, message: str, choices: list[tuple[str, str]]) -> str:
        del message, choices
        return self.select_answers.popleft()

    async def checkbox(self, message: str, choices: list[tuple[str, str]]) -> list[str]:
        del message, choices
        return self.checkbox_answers.popleft()

    def message(self, text: str) -> None:
        self.messages.append(text)


class FakeAdapter:
    kind = AgentKind.CODEX

    def __init__(self) -> None:
        self.records: list[ProfileRecord] = []

    def detected(self) -> bool:
        return True

    def exists(self, server_name: str) -> bool:
        del server_name
        return False

    def register(self, record: ProfileRecord, *, replace: bool) -> RegistrationResult:
        assert not replace
        self.records.append(record)
        return RegistrationResult(agent=self.kind, server_name=record.server_name)


@pytest.mark.asyncio
async def test_full_filesystem_install_stores_smokes_and_registers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    config_dir = tmp_path / "config"
    adapter = FakeAdapter()
    monkeypatch.setattr(installer, "agent_adapters", lambda: {AgentKind.CODEX: adapter})
    prompt = ScriptedPrompt(
        text=["docs", str(root)],
        confirms=[True],
        checkboxes=[["filesystem"], ["codex"]],
    )

    await installer.install(
        prompt,
        config_dir=config_dir,
        requested_secret_store=SecretStoreKind.FILE,
    )

    stored = ProfileStore(config_dir).get("filesystem", "docs")
    assert stored.verified
    assert stored.environment["FILESYSTEM_ROOT_DIR"] == str(root)
    assert [record.server_name for record in adapter.records] == ["mcps-filesystem-docs"]
    assert any("MCP exposed" in message for message in prompt.messages)


@pytest.mark.asyncio
async def test_validation_failure_can_be_explicitly_installed_unverified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fail_validation(collected: installer.CollectedProfile) -> list[str]:
        del collected
        raise ProfileValidationError("credentials rejected")

    monkeypatch.setattr(installer, "validate_profile", fail_validation)
    prompt = ScriptedPrompt(
        text=["profile", str(tmp_path)],
        confirms=[],
        selects=["unverified"],
    )

    collected = await installer._collect_validated(
        prompt,
        ServiceKind.FILESYSTEM,
        SecretStoreKind.FILE,
        skip_validation=False,
    )

    assert not collected.record.verified
    assert any("credentials rejected" in message for message in prompt.messages)


@pytest.mark.asyncio
async def test_existing_profile_can_be_reconfigured_without_new_secret_store_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    config_dir = tmp_path / "config"
    store = ProfileStore(config_dir)
    store.put(
        ProfileRecord(
            service=ServiceKind.FILESYSTEM,
            name="docs",
            environment={"FILESYSTEM_ROOT_DIR": str(old_root)},
            secret_store=SecretStoreKind.KEYRING,
        )
    )
    adapter = FakeAdapter()
    monkeypatch.setattr(installer, "agent_adapters", lambda: {AgentKind.CODEX: adapter})
    prompt = ScriptedPrompt(
        text=[str(new_root)],
        confirms=[True],
        selects=["reconfigure", "filesystem:docs"],
        checkboxes=[["codex"]],
    )

    await installer.install(prompt, config_dir=config_dir)

    stored = store.get("filesystem", "docs")
    assert stored.environment["FILESYSTEM_ROOT_DIR"] == str(new_root)
    assert stored.verified
    assert [record.server_name for record in adapter.records] == ["mcps-filesystem-docs"]


@pytest.mark.asyncio
async def test_reconfiguration_removes_secrets_no_longer_used(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = ProfileStore(tmp_path)
    original_record = ProfileRecord(
        service=ServiceKind.SLSKD,
        name="home",
        environment={"SLSKD_URL": "https://slskd.example", "SLSKD_USERNAME": "alice"},
        secret_store=SecretStoreKind.FILE,
    )
    store_profile_secrets(original_record, {"SLSKD_PASSWORD": "old-secret"}, config_dir=tmp_path)
    store.put(original_record)
    original_config = store.load()
    replacement = installer.CollectedProfile(
        record=ProfileRecord(
            service=ServiceKind.SLSKD,
            name="home",
            environment={"SLSKD_URL": "https://slskd.example"},
            secret_store=SecretStoreKind.FILE,
        ),
        secret_values={"SLSKD_API_KEY": "new-secret"},
    )

    async def smoke(record: ProfileRecord, config_dir: Path) -> int:
        del record, config_dir
        return 4

    monkeypatch.setattr(installer, "smoke_test_profile", smoke)

    assert await installer._store_and_smoke(store, replacement, original_config) == 4
    backend = FileSecretBackend(tmp_path / "secrets.json")
    assert backend.get("slskd/home/SLSKD_API_KEY") == "new-secret"
    with pytest.raises(ValueError, match="not found"):
        backend.get("slskd/home/SLSKD_PASSWORD")
