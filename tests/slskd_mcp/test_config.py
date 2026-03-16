import pytest

from slskd_mcp.config import SlskdSettings


def test_slskd_requires_auth_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLSKD_URL", "http://localhost:5030")
    monkeypatch.setenv("SLSKD_API_KEY", "secret")
    settings = SlskdSettings.from_env()
    assert settings.slskd_api_key == "secret"
