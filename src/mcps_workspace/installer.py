import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from mcps_workspace.agents import AgentAdapter, agent_adapters
from mcps_workspace.models import AgentKind, CollectedProfile, InstallerConfig, SecretStoreKind, ServiceKind
from mcps_workspace.prompts import (
    InstallerCancelledError,
    PromptIO,
    QuestionaryPrompt,
    choose_agents,
    choose_services,
    collect_profile,
)
from mcps_workspace.secrets import (
    KeyringSecretBackend,
    backend_for,
    secret_key,
    store_profile_secrets,
)
from mcps_workspace.smoke import smoke_test_profile
from mcps_workspace.storage import ProfileStore
from mcps_workspace.validation import ProfileValidationError, validate_profile


class InstallationAbortedError(RuntimeError):
    pass


async def _choose_secret_store(prompt: PromptIO, requested: SecretStoreKind | None) -> SecretStoreKind:
    if requested is SecretStoreKind.FILE:
        return SecretStoreKind.FILE
    available = KeyringSecretBackend().probe()
    if available:
        return SecretStoreKind.KEYRING
    if requested is SecretStoreKind.KEYRING:
        raise InstallationAbortedError("No usable system keyring backend is available.")
    prompt.message("No usable system keyring backend was found.")
    if await prompt.confirm("Use a restricted local secrets file instead?", default=False):
        return SecretStoreKind.FILE
    raise InstallationAbortedError("Secure secret storage is required.")


async def _collect_validated(
    prompt: PromptIO,
    service: ServiceKind,
    secret_store: SecretStoreKind,
    *,
    skip_validation: bool,
) -> CollectedProfile:
    collected = await collect_profile(prompt, service, secret_store)
    if skip_validation:
        return collected
    while True:
        try:
            warnings = await validate_profile(collected)
        except ProfileValidationError as exc:
            prompt.message(f"Validation failed: {exc}")
            action = await prompt.select(
                "How should the installer continue?",
                [
                    ("Retry validation", "retry"),
                    ("Edit configuration", "edit"),
                    ("Install unverified", "unverified"),
                    ("Abort installation", "abort"),
                ],
            )
            if action == "retry":
                continue
            if action == "edit":
                collected = await collect_profile(
                    prompt,
                    service,
                    secret_store,
                    profile_name=collected.record.name,
                )
                continue
            if action == "unverified":
                return collected
            raise InstallationAbortedError("Installation aborted after validation failure.") from exc
        for warning in warnings:
            prompt.message(f"Warning: {warning}")
        collected.record.mark_verified()
        return collected


def _preview(prompt: PromptIO, profiles: list[CollectedProfile], agents: list[AgentKind]) -> None:
    prompt.message("\nPlanned installation:")
    prompt.message("  Agents: " + ", ".join(agent.display_name for agent in agents))
    for collected in profiles:
        state = "verified" if collected.record.verified else "unverified"
        prompt.message(f"  {collected.record.server_name}: {collected.record.service.display_name} ({state})")
    prompt.message(
        "  Agent entries contain only the uvx runner command and profile name; credentials are not embedded."
    )


def _restore_secrets(
    collected: CollectedProfile,
    previous: dict[str, str | None],
    config_dir: Path,
) -> None:
    backend = backend_for(collected.record.secret_store, config_dir)
    for environment_name in collected.secret_values:
        key = secret_key(collected.record, environment_name)
        value = previous.get(key)
        if value is None:
            backend.delete(key)
        else:
            backend.set(key, value)


async def _store_and_smoke(
    store: ProfileStore,
    collected: CollectedProfile,
    original_config: InstallerConfig,
) -> int:
    backend = backend_for(collected.record.secret_store, store.config_dir)
    previous: dict[str, str | None] = {}
    for environment_name in collected.secret_values:
        key = secret_key(collected.record, environment_name)
        try:
            previous[key] = backend.get(key)
        except ValueError:
            previous[key] = None
    try:
        store_profile_secrets(collected.record, collected.secret_values, config_dir=store.config_dir)
        store.put(collected.record)
        return await smoke_test_profile(collected.record, store.config_dir)
    except BaseException:
        store.save(original_config)
        _restore_secrets(collected, previous, store.config_dir)
        raise


async def _register_profile(
    prompt: PromptIO,
    collected: CollectedProfile,
    adapters: dict[AgentKind, AgentAdapter],
    selected_agents: list[AgentKind],
) -> list[str]:
    failures: list[str] = []
    for agent in selected_agents:
        adapter = adapters[agent]
        try:
            exists = adapter.exists(collected.record.server_name)
        except Exception as exc:
            failure = f"{agent.display_name}: {exc}"
            failures.append(failure)
            prompt.message(f"Registration check failed for {failure}")
            continue
        if exists and not await prompt.confirm(
            f"Replace existing {agent.display_name} entry {collected.record.server_name}?",
            default=False,
        ):
            prompt.message(f"Skipped {agent.display_name}.")
            continue
        try:
            result = adapter.register(collected.record, replace=exists)
        except Exception as exc:
            failures.append(f"{agent.display_name}: {exc}")
            prompt.message(f"Registration failed for {agent.display_name}: {exc}")
            continue
        prompt.message(f"Registered {result.server_name} in {agent.display_name}.")
        for backup in result.backup_paths:
            prompt.message(f"  Backup: {backup}")
    return failures


async def install(
    prompt: PromptIO,
    *,
    config_dir: Path | None = None,
    requested_secret_store: SecretStoreKind | None = None,
    skip_validation: bool = False,
) -> None:
    adapters = agent_adapters()
    detected = [agent for agent, adapter in adapters.items() if adapter.detected()]
    if not detected:
        raise InstallationAbortedError("No supported agent CLI was detected.")
    services = await choose_services(prompt)
    if not services:
        raise InstallationAbortedError("Select at least one MCP service.")
    selected_agents = await choose_agents(prompt, detected)
    if not selected_agents:
        raise InstallationAbortedError("Select at least one agent.")
    secret_store = await _choose_secret_store(prompt, requested_secret_store)
    profiles = [
        await _collect_validated(
            prompt,
            service,
            secret_store,
            skip_validation=skip_validation,
        )
        for service in services
    ]
    store = ProfileStore(config_dir)
    existing_profiles = store.load().profiles
    confirmed_profiles: list[CollectedProfile] = []
    registration_failures: list[str] = []
    for collected in profiles:
        if collected.record.key in existing_profiles and not await prompt.confirm(
            f"Replace existing profile {collected.record.key}?",
            default=False,
        ):
            prompt.message(f"Skipped profile {collected.record.key}.")
            continue
        confirmed_profiles.append(collected)
    profiles = confirmed_profiles
    if not profiles:
        raise InstallationAbortedError("No profiles remain to install.")
    _preview(prompt, profiles, selected_agents)
    if not await prompt.confirm("Apply these changes?", default=True):
        raise InstallationAbortedError("Installation cancelled before writing changes.")

    for collected in profiles:
        original_config = store.load()
        try:
            tool_count = await _store_and_smoke(store, collected, original_config)
        except Exception as exc:
            raise InstallationAbortedError(f"MCP smoke test failed for {collected.record.server_name}: {exc}") from exc
        prompt.message(f"Stored {collected.record.server_name}; MCP exposed {tool_count} tools.")
        registration_failures.extend(await _register_profile(prompt, collected, adapters, selected_agents))
    if registration_failures:
        summary = "; ".join(registration_failures)
        raise InstallationAbortedError(f"Some agent registrations failed; profiles were retained: {summary}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Interactively configure and install mcps for local coding agents.")
    parser.add_argument("--config-dir", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--secret-store",
        choices=[kind.value for kind in SecretStoreKind],
        default=None,
        help="Force system keyring or restricted-file secret storage.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip service credential checks; profiles are marked unverified.",
    )
    parsed = parser.parse_args(argv)
    requested = SecretStoreKind(parsed.secret_store) if parsed.secret_store is not None else None
    try:
        asyncio.run(
            install(
                QuestionaryPrompt(),
                config_dir=parsed.config_dir,
                requested_secret_store=requested,
                skip_validation=parsed.skip_validation,
            )
        )
    except (InstallationAbortedError, InstallerCancelledError, ValidationError) as exc:
        sys.stderr.write(f"install: {exc}\n")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
