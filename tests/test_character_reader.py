from __future__ import annotations

import unittest
from typing import Any

from wm.character.reader import CharacterStateReader
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliError


class CharacterStateReaderTests(unittest.TestCase):
    def test_missing_tables_degrade_to_partial_empty_bundle(self) -> None:
        client = _FakeMysqlClient(existing_tables=set())

        bundle = CharacterStateReader(client=client, settings=Settings()).load(character_guid=5406)

        self.assertEqual(bundle.status, "PARTIAL")
        self.assertIsNone(bundle.profile)
        self.assertEqual(bundle.arc_states, [])
        self.assertTrue(any("wm_character_profile: table not found" in note for note in bundle.notes))

    def test_loads_full_journey_state_with_conversation_steering(self) -> None:
        client = _FakeMysqlClient(
            existing_tables={
                "wm_character_profile",
                "wm_character_arc_state",
                "wm_character_unlock",
                "wm_character_reward_instance",
                "wm_character_conversation_steering",
                "wm_character_prompt_queue",
            },
            rows={
                "profile": [
                    {
                        "CharacterGUID": "5406",
                        "CharacterName": "Jecia",
                        "WMPersona": "world_master_candidate",
                        "Tone": "direct",
                        "PreferredThemesJSON": '["visible powers"]',
                        "AvoidedThemesJSON": '["global bot rewards"]',
                    }
                ],
                "arcs": [
                    {
                        "CharacterGUID": "5406",
                        "ArcKey": "jecia_world_master_awakened",
                        "StageKey": "field_power_trials",
                        "Status": "active",
                        "BranchKey": "wild_powers_first",
                        "Summary": "Jecia is testing personal WM powers.",
                    }
                ],
                "unlocks": [
                    {
                        "CharacterGUID": "5406",
                        "UnlockKind": "shell_spell",
                        "UnlockID": "940001",
                        "SourceArcKey": "jecia_world_master_awakened",
                        "SourceQuestID": None,
                        "GrantMethod": "shell_grant",
                        "BotEligible": "0",
                    }
                ],
                "rewards": [
                    {
                        "CharacterGUID": "5406",
                        "RewardKind": "item",
                        "TemplateID": "910006",
                        "SourceArcKey": "jecia_world_master_awakened",
                        "SourceQuestID": "910075",
                        "IsEquippedGate": "1",
                    }
                ],
                "steering": [
                    {
                        "CharacterGUID": "5406",
                        "SteeringKey": "wild_powers_visible_first",
                        "SteeringKind": "player_preference",
                        "Body": "Prioritize visible powers.",
                        "Priority": "50",
                        "Source": "operator",
                        "IsActive": "1",
                        "MetadataJSON": '{"track":"wild_powers"}',
                    }
                ],
                "prompts": [
                    {
                        "QueueID": "12",
                        "CharacterGUID": "5406",
                        "PromptKind": "roadmap_branch_choice",
                        "Body": "Pick a branch.",
                        "IsConsumed": "0",
                        "CreatedAt": "2026-04-26 10:00:00",
                    }
                ],
            },
        )

        bundle = CharacterStateReader(client=client, settings=Settings()).load(character_guid=5406)

        self.assertEqual(bundle.status, "WORKING")
        self.assertEqual(bundle.profile.character_name if bundle.profile else None, "Jecia")
        self.assertEqual(bundle.profile.preferred_themes if bundle.profile else [], ["visible powers"])
        self.assertEqual(bundle.arc_states[0].arc_key, "jecia_world_master_awakened")
        self.assertEqual(bundle.unlocks[0].grant_method, "shell_grant")
        self.assertTrue(bundle.rewards[0].is_equipped_gate)
        self.assertEqual(bundle.conversation_steering[0].metadata, {"track": "wild_powers"})
        self.assertEqual(bundle.prompt_queue[0].queue_id, 12)

    def test_character_db_failure_does_not_crash_inspect(self) -> None:
        client = _FakeMysqlClient(existing_tables={"wm_character_profile"}, fail_char_queries=True)

        bundle = CharacterStateReader(client=client, settings=Settings()).load(character_guid=5406)

        self.assertEqual(bundle.status, "PARTIAL")
        self.assertTrue(any("MysqlCliError" in note for note in bundle.notes))


class _FakeMysqlClient:
    def __init__(
        self,
        *,
        existing_tables: set[str],
        rows: dict[str, list[dict[str, Any]]] | None = None,
        fail_char_queries: bool = False,
    ) -> None:
        self.existing_tables = existing_tables
        self.rows = rows or {}
        self.fail_char_queries = fail_char_queries
        self.queries: list[dict[str, str]] = []

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
        self.queries.append({"database": database, "sql": sql})
        if database == "information_schema":
            table_name = _extract_table_name(sql)
            return [{"TABLE_NAME": table_name}] if table_name in self.existing_tables else []
        if self.fail_char_queries:
            raise MysqlCliError("characters db unavailable")
        if "FROM wm_character_profile" in sql:
            return list(self.rows.get("profile", []))
        if "FROM wm_character_arc_state" in sql:
            return list(self.rows.get("arcs", []))
        if "FROM wm_character_unlock" in sql:
            return list(self.rows.get("unlocks", []))
        if "FROM wm_character_reward_instance" in sql:
            return list(self.rows.get("rewards", []))
        if "FROM wm_character_conversation_steering" in sql:
            return list(self.rows.get("steering", []))
        if "FROM wm_character_prompt_queue" in sql:
            return list(self.rows.get("prompts", []))
        return []


def _extract_table_name(sql: str) -> str:
    marker = "AND TABLE_NAME = '"
    start = sql.index(marker) + len(marker)
    end = sql.index("'", start)
    return sql[start:end]


if __name__ == "__main__":
    unittest.main()
