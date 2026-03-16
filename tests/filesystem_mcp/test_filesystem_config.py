from pathlib import Path

import pytest

from filesystem_mcp.config import FilesystemSettings


def test_filesystem_settings_resolve_root_from_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("FILESYSTEM_ROOT_DIR", str(tmp_path))
    settings = FilesystemSettings.from_env()
    assert settings.filesystem_root_dir == tmp_path.resolve()
