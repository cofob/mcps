import json
import os
import tempfile
from pathlib import Path

from platformdirs import user_config_path

from mcps_workspace.models import InstallerConfig, ProfileRecord


def default_config_dir() -> Path:
    return user_config_path("mcps", "cofob", ensure_exists=False)


def _atomic_write(path: Path, content: str, *, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        path.parent.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        if os.name != "nt":
            path.chmod(mode)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


class ProfileStore:
    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or default_config_dir()
        self.config_path = self.config_dir / "config.json"

    def load(self) -> InstallerConfig:
        if not self.config_path.exists():
            return InstallerConfig()
        return InstallerConfig.model_validate_json(self.config_path.read_text(encoding="utf-8"))

    def save(self, config: InstallerConfig) -> None:
        payload = config.model_dump(mode="json", exclude_none=True)
        _atomic_write(self.config_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def get(self, service: str, name: str) -> ProfileRecord:
        key = f"{service}:{name}"
        try:
            return self.load().profiles[key]
        except KeyError as exc:
            raise ValueError(f"Unknown MCP profile {key!r}.") from exc

    def put(self, record: ProfileRecord) -> None:
        config = self.load()
        config.profiles[record.key] = record
        self.save(config)
