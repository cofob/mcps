import hashlib
import secrets


def build_subsonic_auth_params(
    *,
    username: str,
    password: str,
    client_name: str,
    api_version: str,
) -> dict[str, str]:
    salt = secrets.token_hex(8)
    token = hashlib.md5(f"{password}{salt}".encode(), usedforsecurity=False).hexdigest()
    return {
        "u": username,
        "t": token,
        "s": salt,
        "v": api_version,
        "c": client_name,
        "f": "json",
    }
