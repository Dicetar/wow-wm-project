from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import subprocess
import sys
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.runtime_sync import RuntimeCommandResult, RuntimeSyncResult, SoapRuntimeClient, build_default_quest_reload_commands


@dataclass(slots=True)
class RollbackIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class QuestRollbackResult:
    quest_id: int
    mode: str
    applied: bool
    ok: bool
    snapshot_id: int | None = None
    restored_tables: dict[str, int] = field(default_factory=dict)
    issues: list[RollbackIssue] = field(default_factory=list)
    runtime_sync: dict[str, Any] = field(default_factory=dict)
    restart_recommended: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "quest_id": self.quest_id,
            "mode": self.mode,
            "applied": self.applied,
            "ok": self.ok,
            "snapshot_id": self.snapshot_id,
            "restored_tables": self.restored_tables,
            "issues": [issue.to_dict() for issue in self.issues],
            "runtime_sync": self.runtime_sync,
            "restart_recommended": self.restart_recommended,
        }


class QuestRollbackManager:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def rollback(self, *, quest_id: int, mode: str, runtime_sync_mode: str) -> QuestRollbackResult:
        issues: list[RollbackIssue] = []
        snapshot_row = self._latest_snapshot_row(quest_id)
        if snapshot_row is None:
            issues.append(RollbackIssue(path="snapshot", message=f"No rollback snapshot exists for quest {quest_id}."))
            return QuestRollbackResult(
                quest_id=quest_id,
                mode=mode,
                applied=False,
                ok=False,
                issues=issues,
            )

        try:
            snapshot = json.loads(str(snapshot_row["snapshot_json"]))
        except json.JSONDecodeError:
            issues.append(RollbackIssue(path="snapshot", message=f"Rollback snapshot {snapshot_row['id']} is not valid JSON."))
            return QuestRollbackResult(
                quest_id=quest_id,
                mode=mode,
                applied=False,
                ok=False,
                snapshot_id=int(snapshot_row["id"]),
                issues=issues,
            )

        if not isinstance(snapshot, dict):
            issues.append(RollbackIssue(path="snapshot", message="Rollback snapshot payload must be an object."))
            return QuestRollbackResult(
                quest_id=quest_id,
                mode=mode,
                applied=False,
                ok=False,
                snapshot_id=int(snapshot_row["id"]),
                issues=issues,
            )

        table_presence = self._table_presence({"quest_offer_reward", "quest_request_items", "wm_reserved_slot"})
        restore_statements, restored_tables = self._build_restore_plan(
            quest_id=quest_id,
            snapshot=snapshot,
            table_presence=table_presence,
        )

        runtime_sync = RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=False,
            note="Dry-run mode does not touch the live runtime.",
        )

        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported rollback mode: {mode}")

        if mode == "apply":
            try:
                self._execute_world(
                    "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                    f"('quest', {int(quest_id)}, 'rollback', 'started', 'Quest rollback started by wm.quests.rollback')"
                )
                for statement in restore_statements:
                    self._execute_world(statement)
                if table_presence.get("wm_reserved_slot", False):
                    slot_status = "active" if restored_tables.get("quest_template", 0) > 0 else "staged"
                    self._execute_world(
                        "UPDATE wm_reserved_slot SET "
                        f"SlotStatus = {_sql_string(slot_status)} "
                        "WHERE EntityType = 'quest' "
                        f"AND ReservedID = {int(quest_id)}"
                    )
                self._execute_world(
                    "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                    f"('quest', {int(quest_id)}, 'rollback', 'success', 'Quest rollback completed successfully')"
                )
            except MysqlCliError as exc:
                self._record_failure_log(quest_id, str(exc))
                raise
            runtime_sync = self._sync_runtime(
                runtime_sync_mode=runtime_sync_mode,
                questgiver_entry=self._starter_entry_from_snapshot(snapshot),
                apply=True,
            )

        return QuestRollbackResult(
            quest_id=quest_id,
            mode=mode,
            applied=mode == "apply",
            ok=(not issues and bool(runtime_sync.overall_ok)),
            snapshot_id=int(snapshot_row["id"]),
            restored_tables=restored_tables,
            issues=issues,
            runtime_sync=runtime_sync.to_dict(),
            restart_recommended=bool(runtime_sync.restart_recommended),
        )

    def _build_restore_plan(
        self,
        *,
        quest_id: int,
        snapshot: dict[str, Any],
        table_presence: dict[str, bool],
    ) -> tuple[list[str], dict[str, int]]:
        statements = [
            f"DELETE FROM creature_queststarter WHERE quest = {int(quest_id)};",
            f"DELETE FROM creature_questender WHERE quest = {int(quest_id)};",
        ]
        if table_presence.get("quest_offer_reward", False):
            statements.append(f"DELETE FROM quest_offer_reward WHERE ID = {int(quest_id)};")
        if table_presence.get("quest_request_items", False):
            statements.append(f"DELETE FROM quest_request_items WHERE ID = {int(quest_id)};")
        statements.append(f"DELETE FROM quest_template WHERE ID = {int(quest_id)};")

        restored_tables = {
            "quest_template": len(snapshot.get("quest_template", []) or []),
            "creature_queststarter": len(snapshot.get("creature_queststarter", []) or []),
            "creature_questender": len(snapshot.get("creature_questender", []) or []),
            "quest_offer_reward": len(snapshot.get("quest_offer_reward", []) or []),
            "quest_request_items": len(snapshot.get("quest_request_items", []) or []),
        }

        statements.extend(self._build_insert_statements("quest_template", snapshot.get("quest_template", []) or []))
        if table_presence.get("quest_offer_reward", False):
            statements.extend(self._build_insert_statements("quest_offer_reward", snapshot.get("quest_offer_reward", []) or []))
        if table_presence.get("quest_request_items", False):
            statements.extend(self._build_insert_statements("quest_request_items", snapshot.get("quest_request_items", []) or []))
        statements.extend(self._build_insert_statements("creature_queststarter", snapshot.get("creature_queststarter", []) or []))
        statements.extend(self._build_insert_statements("creature_questender", snapshot.get("creature_questender", []) or []))
        return statements, restored_tables

    def _build_insert_statements(self, table_name: str, rows: list[dict[str, Any]]) -> list[str]:
        statements: list[str] = []
        for row in rows:
            if not isinstance(row, dict) or not row:
                continue
            columns = list(row.keys())
            values = [_sql_literal(row[column]) for column in columns]
            statements.append(
                f"INSERT INTO {table_name} (" + ", ".join(f"`{column}`" for column in columns) + ") VALUES (" + ", ".join(values) + ");"
            )
        return statements

    def _latest_snapshot_row(self, quest_id: int) -> dict[str, Any] | None:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT id, snapshot_json FROM wm_rollback_snapshot "
                "WHERE artifact_type = 'quest' "
                f"AND artifact_entry = {int(quest_id)} ORDER BY id DESC LIMIT 1"
            ),
        )
        return rows[0] if rows else None

    def _table_presence(self, table_names: set[str]) -> dict[str, bool]:
        if not table_names:
            return {}
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database="information_schema",
            sql=(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.world_db_name)} "
                f"AND TABLE_NAME IN ({_sql_list(table_names)})"
            ),
        )
        present = {str(row["TABLE_NAME"]): True for row in rows}
        return {name: present.get(name, False) for name in table_names}

    def _starter_entry_from_snapshot(self, snapshot: dict[str, Any]) -> int | None:
        rows = snapshot.get("creature_queststarter", []) or []
        if not rows:
            return None
        first = rows[0]
        if not isinstance(first, dict):
            return None
        if first.get("id") in (None, ""):
            return None
        return int(first["id"])

    def _sync_runtime(self, *, runtime_sync_mode: str, questgiver_entry: int | None, apply: bool) -> RuntimeSyncResult:
        if not apply:
            return RuntimeSyncResult(
                protocol="none",
                enabled=False,
                overall_ok=True,
                restart_recommended=False,
                note="Dry-run mode does not touch the live runtime.",
            )
        enabled = runtime_sync_mode == "soap" or (runtime_sync_mode == "auto" and self.settings.soap_enabled)
        if not enabled:
            return RuntimeSyncResult(
                protocol="none",
                enabled=False,
                overall_ok=True,
                restart_recommended=True,
                note="Runtime sync is disabled. Restart worldserver before testing the rolled-back quest.",
            )
        if not self.settings.soap_user or not self.settings.soap_password:
            return RuntimeSyncResult(
                protocol="soap",
                enabled=True,
                overall_ok=False,
                restart_recommended=True,
                note="SOAP runtime sync was requested but WM_SOAP_USER / WM_SOAP_PASSWORD are not configured.",
            )
        client = SoapRuntimeClient(settings=self.settings)
        commands = build_default_quest_reload_commands(questgiver_entry=questgiver_entry)
        results: list[RuntimeCommandResult] = []
        overall_ok = True
        for command in commands:
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
            note="Quest rollback restored DB rows and sent runtime reload commands. Restart worldserver if quest behavior remains stale.",
        )

    def _record_failure_log(self, quest_id: int, error_message: str) -> None:
        safe_error = error_message.replace("'", "''")
        try:
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('quest', {int(quest_id)}, 'rollback', 'failed', '{safe_error}')"
            )
        except MysqlCliError:
            pass

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


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_list(values: set[str]) -> str:
    return ", ".join(_sql_string(value) for value in sorted(values))


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return _sql_string(str(value))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.rollback")
    parser.add_argument("--quest-id", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _render_summary(result: QuestRollbackResult) -> str:
    runtime_sync = result.runtime_sync
    lines = [
        f"quest_id: {result.quest_id}",
        f"mode: {result.mode}",
        f"applied: {str(result.applied).lower()}",
        f"ok: {str(result.ok).lower()}",
        f"snapshot_id: {result.snapshot_id}",
        f"runtime_sync.enabled: {str(bool(runtime_sync.get('enabled', False))).lower()}",
        f"runtime_sync.protocol: {runtime_sync.get('protocol')}",
        f"runtime_sync.overall_ok: {str(bool(runtime_sync.get('overall_ok', False))).lower()}",
        f"restart_recommended: {str(bool(result.restart_recommended)).lower()}",
        "",
        "restored_tables:",
    ]
    if not result.restored_tables:
        lines.append("- none")
    else:
        for key, value in result.restored_tables.items():
            lines.append(f"- {key} = {value}")
    lines.extend(["", "issues:"])
    if not result.issues:
        lines.append("- none")
    else:
        for issue in result.issues:
            lines.append(f"- {issue.path} | {issue.severity} | {issue.message}")
    lines.extend(["", "runtime_commands:"])
    commands = runtime_sync.get("commands", [])
    if not commands:
        lines.append("- none")
    else:
        for command in commands:
            if command.get("ok"):
                preview = str(command.get("result") or "").strip().splitlines()
                preview_text = preview[0] if preview else "ok"
                lines.append(f"- ok | {command.get('command')} | {preview_text}")
            else:
                lines.append(
                    f"- fail | {command.get('command')} | {command.get('fault_string') or command.get('fault_code')}"
                )
    if runtime_sync.get("note"):
        lines.extend(["", f"note: {runtime_sync.get('note')}"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    manager = QuestRollbackManager(client=client, settings=settings)
    result = manager.rollback(quest_id=args.quest_id, mode=args.mode, runtime_sync_mode=args.runtime_sync)
    raw = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary or args.output_json is not None:
        print(_render_summary(result))
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(raw)
    return 0 if result.ok else 2


if __name__ == "__main__":
    sys.exit(main())
