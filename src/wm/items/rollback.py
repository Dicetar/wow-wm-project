from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess
import sys
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.runtime_sync import RuntimeCommandResult, RuntimeSyncResult, SoapRuntimeClient


@dataclass(slots=True)
class ItemRollbackResult:
    item_entry: int
    mode: str
    snapshot_found: bool
    restored_action: str
    applied: bool
    runtime_sync: dict[str, Any]
    restart_recommended: bool
    ok: bool
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ItemRollback:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def rollback(
        self,
        *,
        item_entry: int,
        mode: str,
        runtime_sync_mode: str,
        soap_commands: list[str],
    ) -> ItemRollbackResult:
        issues: list[str] = []
        snapshot_rows = self._query_world(
            "SELECT `snapshot_json` FROM `wm_rollback_snapshot` "
            "WHERE `artifact_type` = 'item' "
            f"AND `artifact_entry` = {int(item_entry)} "
            "ORDER BY `id` DESC LIMIT 1"
        )
        if not snapshot_rows:
            return ItemRollbackResult(
                item_entry=item_entry,
                mode=mode,
                snapshot_found=False,
                restored_action="none",
                applied=False,
                runtime_sync=RuntimeSyncResult(
                    protocol="none",
                    enabled=False,
                    overall_ok=False,
                    restart_recommended=False,
                    note="No wm_rollback_snapshot row exists for this item entry.",
                ).to_dict(),
                restart_recommended=False,
                ok=False,
                issues=[f"No rollback snapshot found for item {item_entry}."],
            )

        snapshot_json = str(snapshot_rows[0]["snapshot_json"])
        snapshot = json.loads(snapshot_json)
        existing_rows = snapshot.get("existing_item_template") or []
        restored_action = "delete_slot" if not existing_rows else "restore_previous_row"

        runtime_sync = RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=False,
            note="Dry-run mode does not touch the live runtime.",
        )

        if mode == "apply":
            try:
                self._execute_world(
                    "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                    f"('item', {int(item_entry)}, 'rollback', 'started', 'Managed item rollback started by wm.items.rollback')"
                )
                if not existing_rows:
                    self._execute_world(f"DELETE FROM `item_template` WHERE `entry` = {int(item_entry)}")
                    self._update_reserved_slot(item_entry=item_entry, slot_status="staged")
                else:
                    row = dict(existing_rows[0])
                    column_order = list(row.keys())
                    columns_sql = ", ".join(f"`{column}`" for column in column_order)
                    values_sql = ", ".join(_sql_value(row.get(column)) for column in column_order)
                    self._execute_world(
                        f"REPLACE INTO `item_template` ({columns_sql}) VALUES ({values_sql})"
                    )
                    self._update_reserved_slot(item_entry=item_entry, slot_status="active")
                self._execute_world(
                    "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                    f"('item', {int(item_entry)}, 'rollback', 'success', 'Managed item rollback completed successfully')"
                )
            except MysqlCliError as exc:
                issues.append(str(exc))
                self._log_failure(item_entry=item_entry, error_message=str(exc))
                return ItemRollbackResult(
                    item_entry=item_entry,
                    mode=mode,
                    snapshot_found=True,
                    restored_action=restored_action,
                    applied=False,
                    runtime_sync=RuntimeSyncResult(
                        protocol="none",
                        enabled=False,
                        overall_ok=False,
                        restart_recommended=True,
                        note="Rollback failed before runtime sync could run.",
                    ).to_dict(),
                    restart_recommended=True,
                    ok=False,
                    issues=issues,
                )
            runtime_sync = _sync_runtime(
                settings=self.settings,
                mode=mode,
                runtime_sync_mode=runtime_sync_mode,
                soap_commands=soap_commands,
            )

        return ItemRollbackResult(
            item_entry=item_entry,
            mode=mode,
            snapshot_found=True,
            restored_action=restored_action,
            applied=(mode == "apply"),
            runtime_sync=runtime_sync.to_dict(),
            restart_recommended=bool(runtime_sync.restart_recommended),
            ok=not issues and bool(runtime_sync.overall_ok),
            issues=issues,
        )

    def _query_world(self, sql: str) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=sql,
        )

    def _execute_world(self, sql: str) -> None:
        command = [
            str(self.client.mysql_bin_path),
            f"--host={self.settings.world_db_host}",
            f"--port={self.settings.world_db_port}",
            f"--user={self.settings.world_db_user}",
            f"--password={self.settings.world_db_password}",
            f"--database={self.settings.world_db_name}",
            f"--execute={sql}",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise MysqlCliError(completed.stderr.strip() or completed.stdout.strip() or "mysql execute failed")

    def _update_reserved_slot(self, *, item_entry: int, slot_status: str) -> None:
        try:
            self._execute_world(
                "UPDATE `wm_reserved_slot` SET `SlotStatus` = "
                f"{_sql_value(slot_status)} WHERE `EntityType` = 'item' AND `ReservedID` = {int(item_entry)}"
            )
        except MysqlCliError:
            pass

    def _log_failure(self, *, item_entry: int, error_message: str) -> None:
        safe_error = error_message.replace("'", "''")
        try:
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('item', {int(item_entry)}, 'rollback', 'failed', '{safe_error}')"
            )
        except MysqlCliError:
            pass


def _sync_runtime(*, settings: Settings, mode: str, runtime_sync_mode: str, soap_commands: list[str]) -> RuntimeSyncResult:
    if mode != "apply":
        return RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=False,
            note="Dry-run mode does not touch the live runtime.",
        )
    enabled = runtime_sync_mode == "soap" or (runtime_sync_mode == "auto" and settings.soap_enabled and bool(soap_commands))
    if not enabled:
        return RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=True,
            note="Rollback changed live item rows in DB. Restart worldserver if item state stays stale.",
        )
    if not settings.soap_user or not settings.soap_password:
        return RuntimeSyncResult(
            protocol="soap",
            enabled=True,
            overall_ok=False,
            restart_recommended=True,
            note="SOAP runtime sync was requested but WM_SOAP_USER / WM_SOAP_PASSWORD are not configured.",
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
        restart_recommended=True,
        note="Rollback changed live item rows and the supplied runtime command(s) were sent.",
    )


def _sql_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.items.rollback")
    parser.add_argument("--item-entry", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument("--soap-command", action="append", default=[])
    parser.add_argument("--output-json", type=Path)
    return parser


def _render_summary(result: ItemRollbackResult) -> str:
    runtime = result.runtime_sync
    return "\n".join(
        [
            f"item_entry: {result.item_entry}",
            f"snapshot_found: {str(result.snapshot_found).lower()}",
            f"restored_action: {result.restored_action}",
            f"applied: {str(result.applied).lower()}",
            f"ok: {str(result.ok).lower()}",
            f"runtime_sync.enabled: {str(bool(runtime.get('enabled', False))).lower()}",
            f"runtime_sync.overall_ok: {str(bool(runtime.get('overall_ok', False))).lower()}",
            f"restart_recommended: {str(bool(result.restart_recommended)).lower()}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    tool = ItemRollback(client=client, settings=settings)
    result = tool.rollback(
        item_entry=args.item_entry,
        mode=args.mode,
        runtime_sync_mode=args.runtime_sync,
        soap_commands=[str(command) for command in args.soap_command],
    )
    raw = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    print(_render_summary(result))
    if args.output_json is not None:
        print("")
        print(f"output_json: {args.output_json}")
    return 0 if result.ok else 2


if __name__ == "__main__":
    sys.exit(main())
