from enum import StrEnum

from fastmcp.server.auth import AuthProvider, JWTVerifier
from pydantic import AnyHttpUrl, BaseModel


class AuthMode(StrEnum):
    NONE = "none"
    OAUTH2 = "oauth2"


class OAuth2Settings(BaseModel):
    issuer_url: AnyHttpUrl | None = None
    audience: str | None = None
    jwks_uri: AnyHttpUrl | None = None
    client_id: str | None = None
    client_secret: str | None = None
    base_url: AnyHttpUrl | None = None
    strategy: str = "bearer"


def build_auth_provider(settings: OAuth2Settings | None) -> AuthProvider | None:
    if settings is None:
        return None

    strategy = settings.strategy.lower()
    if strategy == "bearer":
        if not settings.jwks_uri or not settings.issuer_url or not settings.audience:
            raise RuntimeError(
                "Bearer OAuth2 mode requires jwks_uri, issuer_url, and audience."
            )

        return JWTVerifier(
            jwks_uri=str(settings.jwks_uri),
            issuer=str(settings.issuer_url),
            audience=settings.audience,
        )

    raise RuntimeError(f"Unsupported OAuth2 strategy: {settings.strategy}")
