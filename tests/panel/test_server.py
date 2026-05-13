from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from wm.panel.catalog import CommandCatalog
from wm.panel.catalog import CommandEntry
from wm.panel.server import PanelApp
from wm.panel.state import PanelState


class PanelServerTests(unittest.TestCase):
    def test_status_and_schema_validation_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = PanelApp(state=PanelState(Path(temp)), command_catalog=_catalog())

            status_code, status = app.get("/api/status")
            self.assertEqual(status_code, 200)
            self.assertEqual(status["status"], "PARTIAL")

            payload = {
                "schema_version": "wm.quest.release.repeatable_bounty.v1",
                "quest_kind": "repeatable_bounty",
                "player_guid": 5406,
                "slot_policy": "fresh_reserved_or_existing_active_repeatable",
                "repeatable": True,
                "quest": {"quest_level": 70, "min_level": 68, "grant_mode": "npc_start", "template_defaults": {"SpecialFlags": 1}},
                "objective": {"kind": "kill", "target_entry": 46, "kill_count": 4},
                "reward": {"kind": "none"},
            }
            code, result = app.post("/api/schema/validate", {"schema_version": payload["schema_version"], "payload": payload})

            self.assertEqual(code, 200)
            self.assertTrue(result["ok"], result)

    def test_draft_adoption_preserves_llm_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = PanelApp(state=PanelState(Path(temp)), command_catalog=_catalog())
            draft = {
                "draft_id": "draft-1",
                "origin": "llm",
                "schema_version": "control.proposal.v1",
                "state": "VALIDATED",
                "settings": {"model": "local-model"},
                "instruction": "x",
                "parsed_json": {
                    "schema_version": "control.proposal.v1",
                    "source_event": {"event_id": 1},
                    "player": {"guid": 5406},
                    "selected_recipe": "manual_admin_action",
                    "action": {"kind": "noop", "payload": {}},
                    "rationale": "test",
                    "author": {"kind": "llm", "name": "local-model"},
                },
            }
            app.state.save_draft(draft)

            code, adopted = app.post("/api/drafts/draft-1/adopt", {"operator_name": "tester"})

            self.assertEqual(code, 200)
            self.assertEqual(adopted["origin"], "human_reviewed")
            self.assertEqual(adopted["parsed_json"]["author"]["kind"], "manual")
            self.assertEqual(adopted["parsed_json"]["metadata"]["original_llm_draft_id"], "draft-1")

    def test_content_draft_adoption_preserves_metadata_without_mutating_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = PanelApp(state=PanelState(Path(temp)), command_catalog=_catalog())
            payload = {
                "schema_version": "wm.item.release.managed_power.v1",
                "content_kind": "item",
                "player_guid": 5406,
                "item_key": "test_boots",
                "item_entry": 900001,
                "slot_policy": "fresh_item_slot_required",
                "visibility": {"player_visible_state_required": True, "tooltip_required": True},
                "reward_integration": {"fresh_quest_required_when_reward_changes": True},
                "runtime": {"native_behavior_required": True, "audit_required": True, "rollback_required": True},
                "effects": [{"effect_key": "wearer_marker", "kind": "wearer_aura"}],
            }
            draft = {
                "draft_id": "draft-item-1",
                "origin": "llm",
                "schema_version": payload["schema_version"],
                "state": "VALIDATED",
                "settings": {"model": "local-model"},
                "instruction": "make boots",
                "parsed_json": payload,
            }
            app.state.save_draft(draft)

            code, adopted = app.post("/api/drafts/draft-item-1/adopt", {"operator_name": "tester"})

            self.assertEqual(code, 200)
            self.assertEqual(adopted["origin"], "human_reviewed")
            self.assertEqual(adopted["parsed_json"], payload)
            self.assertEqual(adopted["original_llm_metadata"]["draft_id"], "draft-item-1")
            self.assertEqual(adopted["original_llm_metadata"]["settings"]["model"], "local-model")

    def test_llm_context_pack_path_rejects_absolute_path_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = PanelApp(state=PanelState(Path(temp)), command_catalog=_catalog())

            _, result = app.post(
                "/api/llm/generate",
                {
                    "schema_version": "wm.quest.release.repeatable_bounty.v1",
                    "instruction": "draft a bounty",
                    "context_pack_path": str(Path.home() / "outside-context.json"),
                },
            )

            self.assertEqual(result["state"], "BROKEN")
            self.assertIn("inside WM workspace", result["error"])


def _catalog() -> CommandCatalog:
    return CommandCatalog(
        [
            CommandEntry(
                id="test.read",
                label="Read",
                category="test",
                kind="read_only",
                dry_run_argv=("python", "-c", "print('read')"),
            )
        ]
    )


if __name__ == "__main__":
    unittest.main()
