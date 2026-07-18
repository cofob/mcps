import os
from pathlib import Path

import pytest

from mcps_workspace import secrets
from mcps_workspace.models import ProfileRecord, SecretStoreKind, ServiceKind
from mcps_workspace.secrets import FileSecretBackend, KeyringSecretBackend, resolve_environment, store_profile_secrets
from mcps_workspace.storage import ProfileStore


def test_profile_store_round_trip(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path)
    record = ProfileRecord(
        service=ServiceKind.FILESYSTEM,
        name="work-tree",
        environment={"FILESYSTEM_ROOT_DIR": str(tmp_path / "work")},
    )

    store.put(record)

    loaded = store.get("filesystem", "work-tree")
    assert loaded == record
    if os.name != "nt":
        assert store.config_path.stat().st_mode & 0o777 == 0o600


def test_file_secret_backend_and_environment_resolution(tmp_path: Path) -> None:
    record = ProfileRecord(
        service=ServiceKind.NAVIDROME,
        name="home",
        environment={"NAVIDROME_URL": "https://music.example", "NAVIDROME_USERNAME": "alice"},
        secret_store=SecretStoreKind.FILE,
    )

    stored = store_profile_secrets(
        record,
        {"NAVIDROME_PASSWORD": "secret"},
        config_dir=tmp_path,
    )

    assert stored == ["navidrome/home/NAVIDROME_PASSWORD"]
    assert resolve_environment(record, config_dir=tmp_path) == {
        "NAVIDROME_URL": "https://music.example",
        "NAVIDROME_USERNAME": "alice",
        "NAVIDROME_PASSWORD": "secret",
        "MCP_TRANSPORT": "stdio",
        "MCP_AUTH_MODE": "none",
    }
    if os.name != "nt":
        assert (tmp_path / "secrets.json").stat().st_mode & 0o777 == 0o600


def test_file_secret_backend_rejects_invalid_payload(tmp_path: Path) -> None:
    path = tmp_path / "secrets.json"
    path.write_text('["not", "an", "object"]', encoding="utf-8")

    with pytest.raises(ValueError, match="invalid"):
        FileSecretBackend(path).get("missing")


def test_keyring_probe_round_trips_and_removes_probe_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    values: dict[tuple[str, str], str] = {}

    def set_password(service: str, key: str, value: str) -> None:
        values[(service, key)] = value

    def get_password(service: str, key: str) -> str | None:
        return values.get((service, key))

    def delete_password(service: str, key: str) -> None:
        del values[(service, key)]

    monkeypatch.setattr(secrets.keyring, "set_password", set_password)
    monkeypatch.setattr(secrets.keyring, "get_password", get_password)
    monkeypatch.setattr(secrets.keyring, "delete_password", delete_password)

    assert KeyringSecretBackend().probe()
    assert values == {}
