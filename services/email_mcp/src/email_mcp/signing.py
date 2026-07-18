import asyncio
import subprocess

from email_mcp.config import EmailAccountSettings, EmailSettings
from mcp_common import UpstreamServerError, UpstreamValidationError


class GpgSigner:
    def __init__(self, settings: EmailSettings) -> None:
        self._settings = settings

    async def sign(self, account: EmailAccountSettings, payload: bytes) -> bytes:
        if account.gpg_key_fingerprint is None:
            raise UpstreamValidationError("This account does not have a GPG signing key configured.")
        return await asyncio.to_thread(self._sign, account, payload)

    def _sign(self, account: EmailAccountSettings, payload: bytes) -> bytes:
        command = [
            self._settings.email_gpg_binary,
            "--batch",
            "--no-tty",
            "--armor",
            "--detach-sign",
            "--digest-algo",
            "SHA256",
            "--local-user",
            account.gpg_key_fingerprint or "",
            "--output",
            "-",
        ]
        if account.gpg_home is not None:
            command[1:1] = ["--homedir", str(account.gpg_home)]
        try:
            completed = subprocess.run(  # noqa: S603 - executable and keyring are operator configuration.
                command,
                input=payload,
                capture_output=True,
                check=False,
                timeout=self._settings.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise UpstreamServerError(f"GPG executable not found: {self._settings.email_gpg_binary}.") from exc
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UpstreamServerError("GPG signing failed to run.") from exc
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()[:1000]
            suffix = f" {detail}" if detail else ""
            raise UpstreamServerError(f"GPG signing failed.{suffix}")
        if not completed.stdout.startswith(b"-----BEGIN PGP SIGNATURE-----"):
            raise UpstreamServerError("GPG returned an invalid detached signature.")
        return completed.stdout
