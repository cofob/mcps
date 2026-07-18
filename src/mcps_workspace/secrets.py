import json
import uuid
from pathlib import Path
from typing import Protocol

import keyring
from keyring.errors import KeyringError

from mcps_workspace.models import ProfileRecord, SecretStoreKind
from mcps_workspace.storage import _atomic_write, default_config_dir

KEYRING_SERVICE = "cofob.mcps"


class SecretBackend(Protocol):
    def set(self, key: str, value: str) -> None: ...

    def get(self, key: str) -> str: ...

    def delete(self, key: str) -> None: ...


class KeyringSecretBackend:
    def probe(self) -> bool:
        key = f"probe/{uuid.uuid4()}"
        try:
            self.set(key, "probe")
            available = self.get(key) == "probe"
            self.delete(key)
        except (KeyringError, RuntimeError):
            return False
        return available

    def set(self, key: str, value: str) -> None:
        keyring.set_password(KEYRING_SERVICE, key, value)

    def get(self, key: str) -> str:
        value = keyring.get_password(KEYRING_SERVICE, key)
        if value is None:
            raise ValueError(f"Secret {key!r} was not found in the system keyring.")
        return value

    def delete(self, key: str) -> None:
        try:
            keyring.delete_password(KEYRING_SERVICE, key)
        except KeyringError:
            return


class FileSecretBackend:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (default_config_dir() / "secrets.json")

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in payload.items()
        ):
            raise ValueError("The fallback secrets file is invalid.")
        return dict(payload)

    def _save(self, values: dict[str, str]) -> None:
        _atomic_write(self.path, json.dumps(values, indent=2, sort_keys=True) + "\n")

    def set(self, key: str, value: str) -> None:
        values = self._load()
        values[key] = value
        self._save(values)

    def get(self, key: str) -> str:
        try:
            return self._load()[key]
        except KeyError as exc:
            raise ValueError(f"Secret {key!r} was not found in {self.path}.") from exc

    def delete(self, key: str) -> None:
        values = self._load()
        if key in values:
            del values[key]
            self._save(values)


def backend_for(kind: SecretStoreKind, config_dir: Path | None = None) -> SecretBackend:
    if kind is SecretStoreKind.KEYRING:
        return KeyringSecretBackend()
    return FileSecretBackend((config_dir or default_config_dir()) / "secrets.json")


def secret_key(record: ProfileRecord, environment_name: str) -> str:
    return f"{record.service.value}/{record.name}/{environment_name}"


def store_profile_secrets(
    record: ProfileRecord,
    values: dict[str, str],
    *,
    config_dir: Path | None = None,
) -> list[str]:
    backend = backend_for(record.secret_store, config_dir)
    stored: list[str] = []
    try:
        for environment_name, value in values.items():
            key = secret_key(record, environment_name)
            backend.set(key, value)
            record.secret_environment[environment_name] = key
            stored.append(key)
    except BaseException:
        for key in stored:
            backend.delete(key)
        raise
    return stored


def resolve_environment(record: ProfileRecord, *, config_dir: Path | None = None) -> dict[str, str]:
    environment = dict(record.environment)
    backend = backend_for(record.secret_store, config_dir)
    for environment_name, key in record.secret_environment.items():
        environment[environment_name] = backend.get(key)
    environment["MCP_TRANSPORT"] = "stdio"
    environment["MCP_AUTH_MODE"] = "none"
    return environment
