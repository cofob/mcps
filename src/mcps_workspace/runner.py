import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from email_mcp.app import create_app as create_email_app
from email_mcp.app import create_mcp as create_email_mcp
from email_mcp.config import EmailSettings
from filesystem_mcp.app import create_app as create_filesystem_app
from filesystem_mcp.app import create_mcp as create_filesystem_mcp
from filesystem_mcp.config import FilesystemSettings
from mcp_common import run_service
from mcps_workspace.models import ServiceKind
from mcps_workspace.secrets import resolve_environment
from mcps_workspace.storage import ProfileStore
from navidrome_mcp.app import create_app as create_navidrome_app
from navidrome_mcp.app import create_mcp as create_navidrome_mcp
from navidrome_mcp.config import NavidromeSettings
from slskd_mcp.app import create_app as create_slskd_app
from slskd_mcp.app import create_mcp as create_slskd_mcp
from slskd_mcp.config import SlskdSettings
from tg_export_txt_mcp.app import create_app as create_tg_export_txt_app
from tg_export_txt_mcp.app import create_mcp as create_tg_export_txt_mcp
from tg_export_txt_mcp.config import TgExportTxtSettings


def _apply_environment(environment: dict[str, str]) -> None:
    for key, value in environment.items():
        os.environ[key] = value


def run_profile(service: ServiceKind, profile: str, *, config_dir: Path | None = None) -> None:
    store = ProfileStore(config_dir)
    record = store.get(service.value, profile)
    if record.service is not service:
        raise ValueError(f"Profile {record.key!r} does not match requested service {service.value!r}.")
    _apply_environment(resolve_environment(record, config_dir=store.config_dir))

    if service is ServiceKind.EMAIL:
        email_settings = EmailSettings.from_env()
        run_service(lambda: email_settings, create_email_mcp, create_email_app, argv=[])
    elif service is ServiceKind.FILESYSTEM:
        filesystem_settings = FilesystemSettings.from_env()
        run_service(
            lambda: filesystem_settings,
            create_filesystem_mcp,
            create_filesystem_app,
            argv=[],
        )
    elif service is ServiceKind.NAVIDROME:
        navidrome_settings = NavidromeSettings.from_env()
        run_service(
            lambda: navidrome_settings,
            create_navidrome_mcp,
            create_navidrome_app,
            argv=[],
        )
    elif service is ServiceKind.SLSKD:
        slskd_settings = SlskdSettings.from_env()
        run_service(lambda: slskd_settings, create_slskd_mcp, create_slskd_app, argv=[])
    else:
        tg_settings = TgExportTxtSettings.from_env()
        run_service(lambda: tg_settings, create_tg_export_txt_mcp, create_tg_export_txt_app, argv=[])


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run an MCP service using an installed named profile.")
    parser.add_argument("service", choices=[service.value for service in ServiceKind])
    parser.add_argument("--profile", required=True)
    parser.add_argument("--config-dir", type=Path, default=None, help=argparse.SUPPRESS)
    parsed = parser.parse_args(argv)
    run_profile(ServiceKind(parsed.service), parsed.profile, config_dir=parsed.config_dir)


if __name__ == "__main__":
    main()
