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
from wm.runtime_sync import RuntimeSyncResult, sync_runtime_after_publish


@dataclass(slots=True)
class ItemRollbackIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ItemRollbackResult:
    item_entry: int
    mode: str
    snapshot_found: bool
    snapshot_id: int | None
    restored_action: str
    applied: bool
    runtime_sync: dict[str, Any]
    restart_recommended: bool
    ok: bool
    issues: list[ItemRollbackIssue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_entry": self.item_entry,
            "mode": self.mode,
            "snapshot_found": self.snapshot_found,
            "snapshot_id": self.snapshot_id,
            "restored_action": self.restored_action,
            "applied": self.applied,
            "runtime_sync": self.runtime_sync,
            "restart_recommended": self.restart_recommended,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }


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
        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported rollback mode: {mode}")

        issues: list[ItemRollbackIssue] = []
        snapshot_rows = self._query_world(
            "SELECT `id`, `snapshot_json` FROM `wm_rollback_snapshot` "
            "WHERE `artifact_type` = 'item' "
            f"AND `artifact_entry` = {int(item_entry)} "
            "ORDER BY `id` DESC LIMIT 1"
        )
        if not snapshot_rows:
            return ItemRollbackResult(
                item_entry=item_entry,
                mode=mode,
                snapshot_found=False,
                snapshot_id=None,
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
                issues=[
                    ItemRollbackIssue(
                        path="snapshot",
                        message=f"No rollback snapshot found for item {item_entry}.",
                    )
                ],
            )

        try:
            snapshot_id = int(snapshot_rows[0]["id"])
        except (KeyError, TypeError, ValueError):
            return ItemRollbackResult(
                item_entry=item_entry,
                mode=mode,
                snapshot_found=True,
                snapshot_id=None,
                restored_action="none",
                applied=False,
                runtime_sync=RuntimeSyncResult(
                    protocol="none",
                    enabled=False,
                    overall_ok=False,
                    restart_recommended=False,
                    note="Rollback snapshot row is missing a valid id.",
                ).to_dict(),
                restart_recommended=False,
                ok=False,
                issues=[
                    ItemRollbackIssue(
                        path="snapshot.id",
                        message="Rollback snapshot row is missing a valid id.",
                    )
                ],
            )

        try:
            snapshot = json.loads(str(snapshot_rows[0]["snapshot_json"]))
        except json.JSONDecodeError:
            return ItemRollbackResult(
                item_entry=item_entry,
                mode=mode,
                snapshot_found=True,
                snapshot_id=snapshot_id,
                restored_action="none",
                applied=False,
                runtime_sync=RuntimeSyncResult(
                    protocol="none",
                    enabled=False,
                    overall_ok=False,
                    restart_recommended=False,
                    note="Rollback snapshot is not valid JSON.",
                ).to_dict(),
                restart_recommended=False,
                ok=False,
                issues=[
                    ItemRollbackIssue(
                        path="snapshot",
                        message=f"Rollback snapshot {snapshot_id} is not valid JSON.",
                    )
                ],
            )

        if not isinstance(snapshot, dict):
            return ItemRollbackResult(
                item_entry=item_entry,
                mode=mode,
                snapshot_found=True,
                snapshot_id=snapshot_id,
                restored_action="none",
                applied=False,
                runtime_sync=RuntimeSyncResult(
                    protocol="none",
                    enabled=False,
                    overall_ok=False,
                    restart_recommended=False,
                    note="Rollback snapshot payload must be an object.",
                ).to_dict(),
                restart_recommended=False,
                ok=False,
                issues=[
                    ItemRollbackIssue(
                        path="snapshot",
                        message=f"Rollback snapshot {snapshot_id} payload must be an object.",
                    )
                ],
            )

        existing_rows_issue = _snapshot_rows_issue(snapshot, "existing_item_template")
        if existing_rows_issue is not None:
            return ItemRollbackResult(
                item_entry=item_entry,
                mode=mode,
                snapshot_found=True,
                snapshot_id=snapshot_id,
                restored_action="none",
                applied=False,
                runtime_sync=RuntimeSyncResult(
                    protocol="none",
                    enabled=False,
                    overall_ok=False,
                    restart_recommended=False,
                    note="Rollback snapshot item_template section is malformed.",
                ).to_dict(),
                restart_recommended=False,
                ok=False,
                issues=[existing_rows_issue],
            )

        existing_rows = _snapshot_rows(snapshot, "existing_item_template")
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
                issues.append(ItemRollbackIssue(path="mysql", message=str(exc)))
                self._log_failure(item_entry=item_entry, error_message=str(exc))
                return ItemRollbackResult(
                    item_entry=item_entry,
                    mode=mode,
                    snapshot_found=True,
                    snapshot_id=snapshot_id,
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
            snapshot_id=snapshot_id,
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
    return sync_runtime_after_publish(
        settings=settings,
        mode=mode,
        runtime_sync_mode=runtime_sync_mode,
        soap_commands=soap_commands,
        no_sync_note="Rollback changed live item rows in DB. Restart worldserver if item state stays stale.",
        synced_note="Rollback changed live item rows and the supplied runtime command(s) were sent.",
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


def _snapshot_rows(snapshot: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = snapshot.get(key, [])
    if rows is None:
        rows = []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _snapshot_rows_issue(snapshot: dict[str, Any], key: str) -> ItemRollbackIssue | None:
    rows = snapshot.get(key, [])
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        return ItemRollbackIssue(
            path=f"snapshot.{key}",
            message=f"Rollback snapshot `{key}` must be a list.",
        )
    if any(not isinstance(row, dict) for row in rows):
        return ItemRollbackIssue(
            path=f"snapshot.{key}",
            message=f"Rollback snapshot `{key}` must contain only row objects.",
        )
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.items.rollback")
    parser.add_argument("--item-entry", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument("--soap-command", action="append", default=[])
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _render_summary(result: ItemRollbackResult) -> str:
    runtime = result.runtime_sync
    lines = [
        f"item_entry: {result.item_entry}",
        f"mode: {result.mode}",
        f"snapshot_found: {str(result.snapshot_found).lower()}",
        f"snapshot_id: {result.snapshot_id}",
        f"restored_action: {result.restored_action}",
        f"applied: {str(result.applied).lower()}",
        f"ok: {str(result.ok).lower()}",
        f"runtime_sync.enabled: {str(bool(runtime.get('enabled', False))).lower()}",
        f"runtime_sync.overall_ok: {str(bool(runtime.get('overall_ok', False))).lower()}",
        f"restart_recommended: {str(bool(result.restart_recommended)).lower()}",
        "",
        "issues:",
    ]
    if not result.issues:
        lines.append("- none")
    else:
        lines.extend(f"- {issue.path} | {issue.severity} | {issue.message}" for issue in result.issues)
    return "\n".join(lines)


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
