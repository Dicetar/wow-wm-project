from __future__ import annotations

import json
import unittest
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliError
from wm.spells.rollback import SpellRollback, _render_summary


class FakeMysqlClient:
    mysql_bin_path = "mysql"


class RecordingSpellRollback(SpellRollback):
    def __init__(
        self,
        *,
        rows: list[dict[str, Any]] | None = None,
        tables: dict[str, bool] | None = None,
        columns: dict[str, set[str]] | None = None,
    ) -> None:
        super().__init__(client=FakeMysqlClient(), settings=Settings(world_db_name="acore_world"))  # type: ignore[arg-type]
        self.rows = rows or []
        self.tables = tables or {"spell_linked_spell": True, "spell_proc": True}
        self.columns = columns or {
            "spell_linked_spell": {"spell_trigger", "spell_effect", "type", "comment"},
            "spell_proc": {"SpellId", "ProcFlags", "Chance", "Cooldown", "Charges"},
        }
        self.executed: list[str] = []

    def _query_world(self, sql: str) -> list[dict[str, Any]]:
        if "wm_rollback_snapshot" in sql:
            return self.rows
        raise AssertionError(f"Unexpected SQL: {sql}")

    def _table_exists(self, table_name: str) -> bool:
        return self.tables.get(table_name, False)

    def _table_columns(self, table_name: str) -> set[str]:
        return self.columns.get(table_name, set())

    def _execute_world(self, sql: str) -> None:
        self.executed.append(sql)


class FailingSpellRollback(RecordingSpellRollback):
    def _execute_world(self, sql: str) -> None:
        self.executed.append(sql)
        if "DELETE FROM `spell_proc`" in sql:
            raise MysqlCliError("delete failed")


def _snapshot_row(snapshot: Any, *, snapshot_id: int = 9) -> dict[str, Any]:
    payload = snapshot if isinstance(snapshot, str) else json.dumps(snapshot)
    return {"id": str(snapshot_id), "snapshot_json": payload}


class SpellRollbackTests(unittest.TestCase):
    def test_dry_run_reports_latest_snapshot_without_mutation(self) -> None:
        rollback = RecordingSpellRollback(rows=[_snapshot_row({"spell_linked_spell": [], "spell_proc": []})])

        result = rollback.rollback(
            spell_entry=940020,
            mode="dry-run",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.snapshot_found)
        self.assertEqual(result.snapshot_id, 9)
        self.assertEqual(result.restored_action, "clear_slot")
        self.assertFalse(result.applied)
        self.assertEqual(rollback.executed, [])
        self.assertIn("snapshot_id: 9", _render_summary(result))

    def test_apply_empty_snapshot_clears_rows_and_stages_slot(self) -> None:
        rollback = RecordingSpellRollback(rows=[_snapshot_row({"spell_linked_spell": [], "spell_proc": []})])

        result = rollback.rollback(
            spell_entry=940020,
            mode="apply",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertTrue(result.ok)
        joined = "\n".join(rollback.executed)
        self.assertIn("DELETE FROM `spell_linked_spell`", joined)
        self.assertIn("DELETE FROM `spell_proc`", joined)
        self.assertIn("UPDATE `wm_reserved_slot` SET `SlotStatus` = 'staged'", joined)
        self.assertTrue(result.restart_recommended)

    def test_apply_restores_previous_rows_and_keeps_slot_active(self) -> None:
        snapshot = {
            "spell_linked_spell": [{"spell_trigger": "940020", "spell_effect": "133", "type": "0"}],
            "spell_proc": [{"SpellId": "940020", "ProcFlags": "4", "Chance": "25", "Cooldown": "6000"}],
        }
        rollback = RecordingSpellRollback(rows=[_snapshot_row(snapshot)])

        result = rollback.rollback(
            spell_entry=940020,
            mode="apply",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.restored_action, "restore_previous_rows")
        joined = "\n".join(rollback.executed)
        self.assertIn("INSERT INTO `spell_linked_spell`", joined)
        self.assertIn("INSERT INTO `spell_proc`", joined)
        self.assertIn("UPDATE `wm_reserved_slot` SET `SlotStatus` = 'active'", joined)

    def test_missing_snapshot_is_structured_failure(self) -> None:
        rollback = RecordingSpellRollback(rows=[])

        result = rollback.rollback(
            spell_entry=940020,
            mode="dry-run",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertFalse(result.ok)
        self.assertFalse(result.snapshot_found)
        self.assertIsNone(result.snapshot_id)
        self.assertTrue(any(issue.path == "snapshot" for issue in result.issues))

    def test_malformed_snapshot_section_is_structured_failure(self) -> None:
        rollback = RecordingSpellRollback(rows=[_snapshot_row({"spell_linked_spell": "bad", "spell_proc": []})])

        result = rollback.rollback(
            spell_entry=940020,
            mode="apply",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertFalse(result.ok)
        self.assertFalse(result.applied)
        self.assertEqual(result.restored_action, "none")
        self.assertTrue(any(issue.path == "snapshot.spell_linked_spell" for issue in result.issues))
        self.assertEqual(rollback.executed, [])

    def test_missing_live_restore_table_is_explicit_failure(self) -> None:
        snapshot = {
            "spell_linked_spell": [{"spell_trigger": "940020", "spell_effect": "133", "type": "0"}],
            "spell_proc": [],
        }
        rollback = RecordingSpellRollback(
            rows=[_snapshot_row(snapshot)],
            tables={"spell_linked_spell": False, "spell_proc": True},
        )

        result = rollback.rollback(
            spell_entry=940020,
            mode="apply",
            runtime_sync_mode="off",
            soap_commands=[],
        )

        self.assertFalse(result.ok)
        self.assertFalse(result.applied)
        self.assertTrue(any(issue.path == "table.spell_linked_spell" for issue in result.issues))
        self.assertEqual(rollback.executed, [])

    def test_mysql_failure_reports_structured_issue(self) -> None:
        rollback = FailingSpellRollback(rows=[_snapshot_row({"spell_linked_spell": [], "spell_proc": []})])

        result = rollback.rollback(
            spell_entry=940020,
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
