from __future__ import annotations

import json
import unittest
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliError
from wm.items.rollback import ItemRollback, _render_summary


class FakeMysqlClient:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.mysql_bin_path = "mysql"
        self.rows = rows or []

    def query(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        sql: str,
    ) -> list[dict[str, Any]]:
        del host, port, user, password
        if database == "acore_world" and "wm_rollback_snapshot" in sql:
            return self.rows
        raise AssertionError(f"Unexpected SQL in database {database}: {sql}")


class RecordingItemRollback(ItemRollback):
    def __init__(self, *, rows: list[dict[str, Any]] | None = None) -> None:
        super().__init__(
            client=FakeMysqlClient(rows=rows),  # type: ignore[arg-type]
            settings=Settings(world_db_name="acore_world"),
        )
        self.executed: list[str] = []

    def _execute_world(self, sql: str) -> None:
        self.executed.append(sql)


class FailingItemRollback(RecordingItemRollback):
    def _execute_world(self, sql: str) -> None:
        self.executed.append(sql)
        if "DELETE FROM `item_template`" in sql:
            raise MysqlCliError("delete failed")


def _snapshot_row(snapshot: Any, *, snapshot_id: int = 7) -> dict[str, Any]:
    payload = snapshot if isinstance(snapshot, str) else json.dumps(snapshot)
    return {"id": str(snapshot_id), "snapshot_json": payload}


class ItemRollbackTests(unittest.TestCase):
    def test_dry_run_reports_latest_snapshot_without_mutation(self) -> None:
        rollback = RecordingItemRollback(rows=[_snapshot_row({"existing_item_template": []})])

        result = rollback.rollback(
            item_entry=910006,
            mode="dry-run",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.snapshot_found)
        self.assertEqual(result.snapshot_id, 7)
        self.assertEqual(result.restored_action, "delete_slot")
        self.assertFalse(result.applied)
        self.assertEqual(rollback.executed, [])
        self.assertIn("snapshot_id: 7", _render_summary(result))

    def test_apply_deletes_missing_original_and_sets_slot_staged(self) -> None:
        rollback = RecordingItemRollback(rows=[_snapshot_row({"existing_item_template": []})])

        result = rollback.rollback(
            item_entry=910006,
            mode="apply",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertTrue(result.ok)
        joined = "\n".join(rollback.executed)
        self.assertIn("DELETE FROM `item_template` WHERE `entry` = 910006", joined)
        self.assertIn("UPDATE `wm_reserved_slot` SET `SlotStatus` = 'staged'", joined)
        self.assertIn("'rollback', 'success'", joined)
        self.assertTrue(result.restart_recommended)

    def test_apply_restores_existing_row_and_keeps_slot_active(self) -> None:
        snapshot = {
            "existing_item_template": [
                {
                    "entry": "910006",
                    "name": "Old Lens",
                    "description": None,
                    "quality": "3",
                }
            ]
        }
        rollback = RecordingItemRollback(rows=[_snapshot_row(snapshot)])

        result = rollback.rollback(
            item_entry=910006,
            mode="apply",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.restored_action, "restore_previous_row")
        joined = "\n".join(rollback.executed)
        self.assertIn("REPLACE INTO `item_template`", joined)
        self.assertIn("`entry`, `name`, `description`, `quality`", joined)
        self.assertIn("'Old Lens'", joined)
        self.assertIn("NULL", joined)
        self.assertIn("UPDATE `wm_reserved_slot` SET `SlotStatus` = 'active'", joined)

    def test_invalid_snapshot_is_structured_failure(self) -> None:
        rollback = RecordingItemRollback(rows=[_snapshot_row("{bad")])

        result = rollback.rollback(
            item_entry=910006,
            mode="dry-run",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.snapshot_found)
        self.assertEqual(result.snapshot_id, 7)
        self.assertTrue(any(issue.path == "snapshot" for issue in result.issues))
        self.assertEqual(rollback.executed, [])

    def test_missing_snapshot_is_structured_failure(self) -> None:
        rollback = RecordingItemRollback(rows=[])

        result = rollback.rollback(
            item_entry=910006,
            mode="dry-run",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertFalse(result.ok)
        self.assertFalse(result.snapshot_found)
        self.assertIsNone(result.snapshot_id)
        self.assertTrue(any(issue.path == "snapshot" for issue in result.issues))

    def test_malformed_item_template_snapshot_section_does_not_delete_slot(self) -> None:
        rollback = RecordingItemRollback(rows=[_snapshot_row({"existing_item_template": "not-a-list"})])

        result = rollback.rollback(
            item_entry=910006,
            mode="apply",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertFalse(result.ok)
        self.assertFalse(result.applied)
        self.assertEqual(result.restored_action, "none")
        self.assertTrue(any(issue.path == "snapshot.existing_item_template" for issue in result.issues))
        self.assertEqual(rollback.executed, [])

    def test_missing_snapshot_id_is_structured_failure(self) -> None:
        rollback = RecordingItemRollback(rows=[{"snapshot_json": json.dumps({"existing_item_template": []})}])

        result = rollback.rollback(
            item_entry=910006,
            mode="dry-run",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertFalse(result.ok)
        self.assertIsNone(result.snapshot_id)
        self.assertTrue(any(issue.path == "snapshot.id" for issue in result.issues))
        self.assertEqual(rollback.executed, [])

    def test_mysql_failure_reports_structured_issue(self) -> None:
        rollback = FailingItemRollback(rows=[_snapshot_row({"existing_item_template": []})])

        result = rollback.rollback(
            item_entry=910006,
            mode="apply",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertFalse(result.ok)
        self.assertFalse(result.applied)
        self.assertTrue(result.restart_recommended)
        self.assertTrue(any(issue.path == "mysql" for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
