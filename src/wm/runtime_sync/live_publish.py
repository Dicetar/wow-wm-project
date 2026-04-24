from __future__ import annotations

from wm.config import Settings
from wm.runtime_sync.soap import RuntimeCommandResult
from wm.runtime_sync.soap import RuntimeSyncResult
from wm.runtime_sync.soap import SoapRuntimeClient


def sync_runtime_after_publish(
    *,
    settings: Settings,
    mode: str,
    runtime_sync_mode: str,
    soap_commands: list[str],
    no_sync_note: str,
    synced_note: str,
    dry_run_note: str = "Dry-run mode does not touch the live runtime.",
    missing_credentials_note: str = "SOAP runtime sync was requested but WM_SOAP_USER / WM_SOAP_PASSWORD are not configured.",
    restart_recommended_when_unsynced: bool = True,
    restart_recommended_when_synced: bool = True,
) -> RuntimeSyncResult:
    if mode != "apply":
        return RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=False,
            note=dry_run_note,
        )

    enabled = runtime_sync_mode == "soap" or (
        runtime_sync_mode == "auto" and settings.soap_enabled and bool(soap_commands)
    )
    if not enabled:
        return RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=restart_recommended_when_unsynced,
            note=no_sync_note,
        )

    if not settings.soap_user or not settings.soap_password:
        return RuntimeSyncResult(
            protocol="soap",
            enabled=True,
            overall_ok=False,
            restart_recommended=True,
            note=missing_credentials_note,
        )

    client = SoapRuntimeClient(settings=settings)
    results: list[RuntimeCommandResult] = []
    overall_ok = True
    for command in soap_commands:
        result = client.execute_command(command)
        result.command = command
        results.append(result)
        if not result.ok:
            overall_ok = False

    return RuntimeSyncResult(
        protocol="soap",
        enabled=True,
        overall_ok=overall_ok,
        commands=results,
        restart_recommended=restart_recommended_when_synced,
        note=synced_note,
    )
