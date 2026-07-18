from pathlib import Path

import pytest

from mcps_workspace.models import ProfileRecord, SecretStoreKind, ServiceKind
from mcps_workspace.smoke import smoke_test_profile
from mcps_workspace.storage import ProfileStore


@pytest.mark.asyncio
async def test_stored_filesystem_profile_completes_stdio_handshake(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    config_dir = tmp_path / "config"
    record = ProfileRecord(
        service=ServiceKind.FILESYSTEM,
        name="test",
        environment={"FILESYSTEM_ROOT_DIR": str(root)},
        secret_store=SecretStoreKind.FILE,
    )
    ProfileStore(config_dir).put(record)

    tool_count = await smoke_test_profile(record, config_dir)

    assert tool_count > 0
