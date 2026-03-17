from pathlib import Path

import pytest

from tg_export_txt_mcp.config import TgExportTxtSettings


def test_txt_export_settings_resolve_root_from_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TG_EXPORT_TXT_ROOT_DIR", str(tmp_path))
    settings = TgExportTxtSettings.from_env()
    assert settings.export_root_dir == tmp_path.resolve()


def test_txt_export_settings_require_positive_limits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TG_EXPORT_TXT_ROOT_DIR", str(tmp_path))
    monkeypatch.setenv("TG_EXPORT_TXT_MAX_SEARCH_RESULTS", "0")
    with pytest.raises(ValueError, match="positive integer"):
        TgExportTxtSettings.from_env()
