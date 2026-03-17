from typing import cast

from fastmcp.server.auth import JWTVerifier
from pydantic import AnyHttpUrl

from mcp_common.auth import OAuth2Settings, build_auth_provider


def test_build_auth_provider_returns_jwt_verifier() -> None:
    provider = build_auth_provider(
        OAuth2Settings(
            strategy="bearer",
            jwks_uri=cast(
                AnyHttpUrl,
                "https://auth.example.com/.well-known/jwks.json",
            ),
            issuer_url=cast(AnyHttpUrl, "https://auth.example.com/"),
            audience="mcps",
        )
    )
    assert isinstance(provider, JWTVerifier)


def test_build_auth_provider_returns_none_for_disabled_auth() -> None:
    assert build_auth_provider(None) is None
