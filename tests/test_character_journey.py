from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from wm.character.journey import (
    CharacterJourneyStore,
    JOURNEY_PLAN_SCHEMA_VERSION,
    JourneyPlanError,
    main,
    render_apply_summary,
    validate_journey_plan,
)
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliError


class CharacterJourneyPlanTests(unittest.TestCase):
    def test_validates_plan_and_rejects_freeform_mutation_fields(self) -> None:
        plan = _plan()
        normalized = validate_journey_plan(plan)

        self.assertEqual(normalized["player_guid"], 5406)
        self.assertEqual(normalized["profile"]["character_name"], "Jecia")
        self.assertEqual(normalized["unlocks"][0]["grant_method"], "shell_grant")

        unsafe = dict(plan)
        unsafe["sql"] = "DROP TABLE item_template"
        with self.assertRaises(JourneyPlanError):
            validate_journey_plan(unsafe)

    def test_rejects_gm_command_grant_method(self) -> None:
        plan = _plan()
        plan["unlocks"][0]["grant_method"] = "gm_command"

        with self.assertRaises(JourneyPlanError):
            validate_journey_plan(plan)

    def test_dry_run_builds_operations_without_mutating(self) -> None:
        client = _FakeMysqlClient()
        result = CharacterJourneyStore(client=client, settings=Settings()).apply_plan(plan=_plan(), mode="dry-run")
        payload = result.to_dict(include_sql=True)

        self.assertTrue(result.ok)
        self.assertFalse(result.mutated)
        self.assertEqual(client.queries, [])
        labels = [operation["label"] for operation in payload["operations"]]
        self.assertIn("profile:upsert", labels)
        self.assertIn("arc_state:upsert:jecia_world_master_awakened", labels)
        self.assertIn("steering:upsert:wild_powers_visible_first", labels)
        self.assertTrue(any("wm_character_conversation_steering" in operation["sql"] for operation in payload["operations"]))

    def test_apply_executes_structured_sql(self) -> None:
        client = _FakeMysqlClient()
        result = CharacterJourneyStore(client=client, settings=Settings()).apply_plan(plan=_plan(), mode="apply")

        self.assertTrue(result.ok)
        self.assertTrue(result.mutated)
        self.assertGreaterEqual(len(client.queries), 6)
        self.assertTrue(any("INSERT INTO wm_character_profile" in query["sql"] for query in client.queries))
        self.assertTrue(any("INSERT INTO wm_character_prompt_queue" in query["sql"] for query in client.queries))
        self.assertFalse(any("gm_command" in query["sql"] for query in client.queries))

    def test_apply_reports_failed_operation(self) -> None:
        client = _FakeMysqlClient(fail_on="wm_character_unlock")
        result = CharacterJourneyStore(client=client, settings=Settings()).apply_plan(plan=_plan(), mode="apply")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "BROKEN")
        self.assertIn("unlock:record", result.error or "")

    def test_cli_dry_run_summary(self) -> None:
        temp_path = Path(".pytest-tmp") / "journey-plan.json"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(_plan()), encoding="utf-8")
        stdout = io.StringIO()

        with patch("wm.character.journey.MysqlCliClient", return_value=_FakeMysqlClient()):
            with redirect_stdout(stdout):
                exit_code = main(["apply", "--plan-json", str(temp_path), "--mode", "dry-run", "--summary"])

        self.assertEqual(exit_code, 0)
        self.assertIn("ok: true", stdout.getvalue())
        self.assertIn("mutated: false", stdout.getvalue())

    def test_apply_summary_renders_error(self) -> None:
        rendered = render_apply_summary(
            {
                "player_guid": 5406,
                "mode": "apply",
                "status": "BROKEN",
                "ok": False,
                "mutated": True,
                "operation_count": 2,
                "error": "failed",
            }
        )

        self.assertIn("error: failed", rendered)


def _plan() -> dict[str, Any]:
    return {
        "schema_version": JOURNEY_PLAN_SCHEMA_VERSION,
        "player_guid": 5406,
        "profile": {
            "character_name": "Jecia",
            "wm_persona": "world_master_candidate",
            "tone": "direct",
            "preferred_themes": ["visible combat powers"],
            "avoided_themes": ["global bot rewards"],
        },
        "arc_states": [
            {
                "arc_key": "jecia_world_master_awakened",
                "stage_key": "field_power_trials",
                "status": "active",
                "branch_key": "wild_powers_first",
                "summary": "Jecia is testing personal WM powers.",
            }
        ],
        "unlocks": [
            {
                "unlock_kind": "shell_spell",
                "unlock_id": 940001,
                "source_arc_key": "jecia_world_master_awakened",
                "grant_method": "shell_grant",
                "bot_eligible": False,
            }
        ],
        "reward_instances": [
            {
                "reward_kind": "item",
                "template_id": 910006,
                "source_arc_key": "jecia_world_master_awakened",
                "source_quest_id": 910075,
                "is_equipped_gate": True,
            }
        ],
        "conversation_steering": [
            {
                "steering_key": "wild_powers_visible_first",
                "body": "Prioritize visible powers.",
                "priority": 50,
                "source": "operator",
                "metadata": {"track": "wild_powers"},
            }
        ],
        "prompt_queue": [
            {
                "prompt_kind": "roadmap_branch_choice",
                "body": "Pick a branch.",
            }
        ],
    }


class _FakeMysqlClient:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
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
        if self.fail_on and self.fail_on in sql:
            raise MysqlCliError("forced failure")
        return []


if __name__ == "__main__":
    unittest.main()
