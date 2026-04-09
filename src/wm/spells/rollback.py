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
from wm.spells.publish import (
    LINKED_EFFECT_CANDIDATES,
    LINKED_TRIGGER_CANDIDATES,
    PROC_COLUMN_CANDIDATES,
    _insert_sql,
    _resolve_column,
    _sql_list,
    _sql_string,
)


@dataclass(slots=True)
class SpellRollbackResult:
    spell_entry: int
    mode: str
    snapshot_found: bool
    applied: bool
    runtime_sync: dict[str, Any]
    restart_recommended: bool
    ok: bool
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpellRollback:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def rollback(
        self,
        *,
        spell_entry: int,
        mode: str,
        runtime_sync_mode: str,
        soap_commands: list[str],
    ) -> SpellRollbackResult:
        snapshot_rows = self._query_world(
            "SELECT `snapshot_json` FROM `wm_rollback_snapshot` "
            "WHERE `artifact_type` = 'spell' "
            f"AND `artifact_entry` = {int(spell_entry)} ORDER BY `id` DESC LIMIT 1"
        )
        if not snapshot_rows:
            return SpellRollbackResult(
                spell_entry=spell_entry,
                mode=mode,
                snapshot_found=False,
                applied=False,
                runtime_sync=RuntimeSyncResult(
                    protocol="none",
                    enabled=False,
                    overall_ok=False,
                    restart_recommended=False,
                    note="No wm_rollback_snapshot row exists for this spell entry.",
                ).to_dict(),
                restart_recommended=False,
                ok=False,
                issues=[f"No rollback snapshot found for spell {spell_entry}."],
            )

        snapshot = json.loads(str(snapshot_rows[0]["snapshot_json"]))
        runtime_sync = RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=False,
            note="Dry-run mode does not touch the live runtime.",
        )
        issues: list[str] = []

        if mode == "apply":
            try:
                self._execute_world(
                    "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                    f"('spell', {int(spell_entry)}, 'rollback', 'started', 'Managed spell rollback started by wm.spells.rollback')"
                )
                self._restore_linked_spell_rows(spell_entry=spell_entry, rows=snapshot.get("spell_linked_spell") or [])
                self._restore_spell_proc_rows(spell_entry=spell_entry, rows=snapshot.get("spell_proc") or [])
                self._update_reserved_slot(spell_entry=spell_entry, slot_status="staged")
                self._execute_world(
                    "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                    f"('spell', {int(spell_entry)}, 'rollback', 'success', 'Managed spell rollback completed successfully')"
                )
            except MysqlCliError as exc:
                issues.append(str(exc))
                self._log_failure(spell_entry=spell_entry, error_message=str(exc))
                return SpellRollbackResult(
                    spell_entry=spell_entry,
                    mode=mode,
                    snapshot_found=True,
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

        return SpellRollbackResult(
            spell_entry=spell_entry,
            mode=mode,
            snapshot_found=True,
            applied=(mode == "apply"),
            runtime_sync=runtime_sync.to_dict(),
            restart_recommended=bool(runtime_sync.restart_recommended),
            ok=not issues and bool(runtime_sync.overall_ok),
            issues=issues,
        )

    def _restore_linked_spell_rows(self, *, spell_entry: int, rows: list[dict[str, Any]]) -> None:
        if not self._table_exists("spell_linked_spell"):
            return
        columns = self._table_columns("spell_linked_spell")
        trigger_col = _resolve_column(columns, LINKED_TRIGGER_CANDIDATES)
        effect_col = _resolve_column(columns, LINKED_EFFECT_CANDIDATES)
        if not trigger_col or not effect_col:
            return
        self._execute_world(
            f"DELETE FROM `spell_linked_spell` WHERE `{trigger_col}` = {int(spell_entry)} OR `{effect_col}` = {int(spell_entry)}"
        )
        for row in rows:
            self._execute_world(_insert_sql("spell_linked_spell", row))

    def _restore_spell_proc_rows(self, *, spell_entry: int, rows: list[dict[str, Any]]) -> None:
        if not self._table_exists("spell_proc"):
            return
        columns = self._table_columns("spell_proc")
        spell_id_col = _resolve_column(columns, PROC_COLUMN_CANDIDATES["spell_id"])
        if not spell_id_col:
            return
        self._execute_world(f"DELETE FROM `spell_proc` WHERE `{spell_id_col}` = {int(spell_entry)}")
        for row in rows:
            self._execute_world(_insert_sql("spell_proc", row))

    def _table_exists(self, table_name: str) -> bool:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database="information_schema",
            sql=(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.world_db_name)} AND TABLE_NAME IN ({_sql_list({table_name})})"
            ),
        )
        return bool(rows)

    def _table_columns(self, table_name: str) -> set[str]:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database="information_schema",
            sql=(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.world_db_name)} AND TABLE_NAME = {_sql_string(table_name)}"
            ),
        )
        return {str(row['COLUMN_NAME']) for row in rows}

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

    def _update_reserved_slot(self, *, spell_entry: int, slot_status: str) -> None:
        try:
            self._execute_world(
                "UPDATE `wm_reserved_slot` SET `SlotStatus` = "
                f"'{slot_status}' WHERE `EntityType` = 'spell' AND `ReservedID` = {int(spell_entry)}"
            )
        except MysqlCliError:
            pass

    def _log_failure(self, *, spell_entry: int, error_message: str) -> None:
        safe_error = error_message.replace("'", "''")
        try:
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('spell', {int(spell_entry)}, 'rollback', 'failed', '{safe_error}')"
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
            note="Rollback changed live spell-side rows in DB. Restart worldserver if state stays stale.",
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
        note="Rollback changed live spell-side rows and the supplied runtime command(s) were sent.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.spells.rollback")
    parser.add_argument("--spell-entry", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument("--soap-command", action="append", default=[])
    parser.add_argument("--output-json", type=Path)
    return parser


def _render_summary(result: SpellRollbackResult) -> str:
    runtime = result.runtime_sync
    return "\n".join(
        [
            f"spell_entry: {result.spell_entry}",
            f"snapshot_found: {str(result.snapshot_found).lower()}",
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
    tool = SpellRollback(client=client, settings=settings)
    result = tool.rollback(
        spell_entry=args.spell_entry,
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
