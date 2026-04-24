from __future__ import annotations

import unittest
from typing import Any

from wm.config import Settings
from wm.spells.models import ManagedSpellDraft, ManagedSpellLink, ManagedSpellProcRule
from wm.spells.publish import SpellPublisher


class FakeMysqlClient:
    mysql_bin_path = "mysql"


class RecordingSpellPublisher(SpellPublisher):
    def __init__(
        self,
        *,
        tables: dict[str, bool] | None = None,
        columns: dict[str, set[str]] | None = None,
        world_rows: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        super().__init__(client=FakeMysqlClient(), settings=Settings(world_db_name="acore_world"))  # type: ignore[arg-type]
        self.tables = tables or {
            "wm_publish_log": True,
            "wm_rollback_snapshot": True,
            "wm_reserved_slot": True,
            "spell_linked_spell": True,
            "spell_proc": True,
        }
        self.columns = columns or {
            "spell_linked_spell": {"spell_trigger", "spell_effect", "type", "comment"},
            "spell_proc": {"SpellId", "ProcFlags", "Chance", "Cooldown", "Charges"},
        }
        self.world_rows = world_rows or {}
        self.executed: list[str] = []

    def _table_presence(self, table_names: set[str]) -> dict[str, bool]:
        return {name: self.tables.get(name, False) for name in table_names}

    def _table_columns(self, table_name: str) -> set[str]:
        return self.columns.get(table_name, set())

    def _query_world(self, sql: str) -> list[dict[str, Any]]:
        if "FROM wm_reserved_slot" in sql:
            return self.world_rows.get("reserved_slot", [])
        if "FROM `spell_linked_spell`" in sql or "FROM spell_linked_spell" in sql:
            return self.world_rows.get("spell_linked_spell", [])
        if "FROM `spell_proc`" in sql or "FROM spell_proc" in sql:
            return self.world_rows.get("spell_proc", [])
        raise AssertionError(f"Unexpected SQL: {sql}")

    def _execute_world(self, sql: str) -> None:
        self.executed.append(sql)


def _draft() -> ManagedSpellDraft:
    return ManagedSpellDraft(
        spell_entry=947020,
        slot_kind="item_trigger_slot",
        name="WM Trigger Burst",
        helper_spell_id=133,
        trigger_item_entry=910020,
        proc_rules=[
            ManagedSpellProcRule(
                spell_id=947020,
                proc_flags=4,
                chance=25.0,
                cooldown=6000,
                charges=0,
            )
        ],
        linked_spells=[
            ManagedSpellLink(
                trigger_spell_id=947020,
                effect_spell_id=133,
                link_type=0,
                comment="Prototype trigger link",
            )
        ],
        tags=["wm_generated", "spell_slot", "item_trigger_slot"],
    )


class SpellPublishTests(unittest.TestCase):
    def test_dry_run_captures_snapshot_and_builds_sql_plan(self) -> None:
        publisher = RecordingSpellPublisher(
            world_rows={
                "reserved_slot": [
                    {
                        "EntityType": "spell",
                        "ReservedID": "947020",
                        "SlotStatus": "staged",
                        "ArcKey": "wm_content:item_trigger:wm-trigger-burst",
                        "CharacterGUID": "5406",
                        "SourceQuestID": None,
                        "NotesJSON": None,
                    }
                ],
                "spell_linked_spell": [{"spell_trigger": "947020", "spell_effect": "133", "type": "0"}],
                "spell_proc": [{"SpellId": "947020", "ProcFlags": "4", "Chance": "25", "Cooldown": "6000"}],
            }
        )

        result = publisher.publish(draft=_draft(), mode="dry-run")

        self.assertFalse(result.applied)
        self.assertTrue(result.validation.get("ok", False))
        self.assertTrue(result.preflight.get("ok", False))
        self.assertEqual(result.preflight["linked_columns"]["trigger"], "spell_trigger")
        self.assertEqual(result.preflight["proc_columns"]["spell_id"], "SpellId")
        self.assertEqual(len(result.snapshot_preview["spell_linked_spell"]), 1)
        self.assertEqual(len(result.snapshot_preview["spell_proc"]), 1)
        joined = "\n".join(result.sql_plan["statements"])
        self.assertIn("DELETE FROM `spell_linked_spell`", joined)
        self.assertIn("INSERT INTO `spell_proc`", joined)
        self.assertEqual(publisher.executed, [])

    def test_apply_records_snapshot_and_marks_slot_active(self) -> None:
        publisher = RecordingSpellPublisher(
            world_rows={
                "reserved_slot": [
                    {
                        "EntityType": "spell",
                        "ReservedID": "947020",
                        "SlotStatus": "staged",
                        "ArcKey": "wm_content:item_trigger:wm-trigger-burst",
                        "CharacterGUID": "5406",
                        "SourceQuestID": None,
                        "NotesJSON": None,
                    }
                ],
                "spell_linked_spell": [],
                "spell_proc": [],
            }
        )

        result = publisher.publish(draft=_draft(), mode="apply")

        self.assertTrue(result.applied)
        joined = "\n".join(publisher.executed)
        self.assertIn("INSERT INTO wm_rollback_snapshot", joined)
        self.assertIn("DELETE FROM `spell_linked_spell`", joined)
        self.assertIn("INSERT INTO `spell_linked_spell`", joined)
        self.assertIn("DELETE FROM `spell_proc`", joined)
        self.assertIn("INSERT INTO `spell_proc`", joined)
        self.assertIn("'publish', 'success'", joined)
        self.assertIn("UPDATE wm_reserved_slot SET SlotStatus = 'active'", joined)

    def test_missing_linked_spell_table_fails_preflight(self) -> None:
        publisher = RecordingSpellPublisher(
            tables={
                "wm_publish_log": True,
                "wm_rollback_snapshot": True,
                "wm_reserved_slot": True,
                "spell_linked_spell": False,
                "spell_proc": True,
            },
            world_rows={
                "reserved_slot": [
                    {
                        "EntityType": "spell",
                        "ReservedID": "947020",
                        "SlotStatus": "staged",
                        "ArcKey": "wm_content:item_trigger:wm-trigger-burst",
                        "CharacterGUID": "5406",
                        "SourceQuestID": None,
                        "NotesJSON": None,
                    }
                ],
                "spell_proc": [],
            },
        )

        result = publisher.publish(draft=_draft(), mode="dry-run")

        self.assertFalse(result.preflight.get("ok", True))
        self.assertTrue(
            any(issue["path"] == "table.spell_linked_spell" for issue in result.preflight.get("issues", []))
        )
        self.assertEqual(result.sql_plan["statements"], [])


if __name__ == "__main__":
    unittest.main()
