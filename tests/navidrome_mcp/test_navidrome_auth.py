import pytest

from navidrome_mcp.auth import build_subsonic_auth_params


def test_build_subsonic_auth_params_uses_token_and_salt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("navidrome_mcp.auth.secrets.token_hex", lambda _: "abcd1234")
    params = build_subsonic_auth_params(
        username="alice",
        password="secret",
        client_name="navidrome-mcp",
        api_version="1.16.1",
    )
    assert params == {
        "u": "alice",
        "t": "56f2ffee872afa6f1cec74ba0fe8baa1",
        "s": "abcd1234",
        "v": "1.16.1",
        "c": "navidrome-mcp",
        "f": "json",
    }
