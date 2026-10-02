from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wm.panel.catalog import CommandCatalog
from wm.panel.catalog import CommandEntry
from wm.panel.server import PanelApp
from wm.panel.state import PanelState
from wm.autoplay.director_work import FrozenWork, WorkRequest
from wm.events.models import PlannedAction, ReactionPlan, SubjectRef


class PanelServerTests(unittest.TestCase):
    def test_director_operator_approval_claims_exact_preview_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = PanelState(Path(temp))
            state.save_session({"character_guid": 5408, "source": "explicit_guid"})
            store = MagicMock()
            store.load_status.return_value = {
                "proposal_queue": [], "running": True, "paused": False,
                "config": {"durable_director_enabled": True, "durable_director_player_guid": 5408},
                "policy": {"enabled_lanes": ["quest", "action"],
                           "lane_budgets": {"quest": 2, "action": 5},
                           "require_rollback_for_lanes": ["quest"]},
            }
            store.load_idempotency_keys.return_value = set()
            app = PanelApp(state=state, command_catalog=_catalog(), autoplay_store=store)
            plan = ReactionPlan(
                plan_key="test:operator", opportunity_type="test", rule_type="test", player_guid=5408,
                subject=SubjectRef(subject_type="creature", subject_entry=449),
                actions=[PlannedAction(kind="quest_publish", payload={"objective": {
                    "target_entry": 449, "kill_count": 3}, "end_npc_entry": 234,
                    "grant_mode": "direct_grant", "reward": {"money_copper": 500}})],
            )
            artifact = FrozenWork.from_runtime({"kind": "plan", "plan": plan})
            work = WorkRequest(7, "test:operator", 5408, "received", 0, artifact.artifact_hash, artifact)
            ledger = MagicMock()
            ledger.load_review.return_value = (work, {"evidence": {
                "draft_id": "draft-7", "schema_version": "wm.quest.release.repeatable_bounty.v1",
                "risk": "medium", "source_event_at": None}})
            ledger.authorize.return_value = replace(work, state="authorized", revision=1)
            ledger.claim.return_value = replace(work, state="dispatching", revision=2)
            ledger.record_result.return_value = replace(work, state="applied", revision=3)
            with patch("wm.autoplay.director_work.DirectorWorkLedger", return_value=ledger), \
                 patch("wm.autoplay.quest_feasibility.assess_quest_plan"), \
                 patch("wm.control._cli.build_live_coordinator"), \
                 patch("wm.autoplay._runtime_plan._execute_runtime_work", side_effect=[
                     [SimpleNamespace(status="preview")], [SimpleNamespace(status="applied")]]):
                with patch.object(app, "_wm_readiness", return_value={"can_apply": True}):
                    code, result = app.post("/api/wm/session/effects/approve", {
                        "request_id": 7, "artifact_hash": artifact.artifact_hash,
                    })
            self.assertEqual(code, 200, result)
            self.assertEqual(result["state"], "applied")
            self.assertFalse(result["player_visible_verified"])
            ledger.authorize.assert_called_once()
            ledger.claim.assert_called_once()
            ledger.record_result.assert_called_once()
            store.update_draft.assert_called_once_with("draft-7", {"state": "APPLIED"})
            store.load_status.return_value["config"]["durable_director_enabled"] = False
            ledger.authorize.reset_mock()
            with patch("wm.autoplay.director_work.DirectorWorkLedger", return_value=ledger), \
                 patch("wm.autoplay.quest_feasibility.assess_quest_plan"), \
                 patch("wm.control._cli.build_live_coordinator"), \
                 patch("wm.autoplay._runtime_plan._execute_runtime_work",
                       return_value=[SimpleNamespace(status="preview")]):
                code, result = app.post("/api/wm/session/effects/approve", {
                    "request_id": 7, "artifact_hash": artifact.artifact_hash,
                })
            self.assertEqual(code, 409)
            self.assertIn("no longer active", result["error"])
            ledger.authorize.assert_not_called()

    def test_director_effect_approval_rejects_changed_hash_without_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = PanelState(Path(temp))
            state.save_session({"character_guid": 5408, "source": "explicit_guid"})
            app = PanelApp(state=state, command_catalog=_catalog())
            ledger = MagicMock()
            ledger.load_review.return_value = (
                SimpleNamespace(state="received", artifact_hash="a" * 64),
                {"preview": {}, "evidence": {}},
            )
            with patch("wm.autoplay.director_work.DirectorWorkLedger", return_value=ledger):
                code, result = app.post("/api/wm/session/effects/approve", {
                    "request_id": 7, "artifact_hash": "b" * 64,
                })
            self.assertEqual(code, 409)
            self.assertFalse(result["ok"])
            ledger.authorize.assert_not_called()
            ledger.claim.assert_not_called()

    def test_director_effect_reject_uses_selected_character_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = PanelState(Path(temp))
            state.save_session({"character_guid": 5408, "source": "explicit_guid"})
            app = PanelApp(state=state, command_catalog=_catalog())
            ledger = MagicMock()
            work = SimpleNamespace(state="received", artifact_hash="a" * 64)
            ledger.load_review.return_value = (work, {"evidence": {"draft_id": "draft-7"}})
            ledger.reject.return_value = SimpleNamespace(state="rejected")
            store = MagicMock()
            app._autoplay_store = store
            with patch("wm.autoplay.director_work.DirectorWorkLedger", return_value=ledger):
                code, result = app.post("/api/wm/session/effects/reject", {
                    "request_id": 7, "artifact_hash": "a" * 64,
                })
            self.assertEqual(code, 200)
            self.assertEqual(result["state"], "rejected")
            ledger.load_review.assert_called_once_with(request_id=7, player_guid=5408)
            ledger.reject.assert_called_once()
            store.update_draft.assert_called_once_with("draft-7", {"state": "REJECTED"})

    def test_wm_session_routes_work_without_legacy_slice_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = PanelState(Path(temp))
            app = PanelApp(state=state, command_catalog=_catalog())
            state.save_session({"character_guid": 5408, "source": "explicit_guid"})
            row = {"request_id": 7, "origin_key": "test:7", "lane": "action",
                   "state": "uncertain", "effects": [], "proof": None}
            with patch.object(app, "_session_director_effects", return_value=[row]):
                code, status = app.get("/api/wm/session/status")
                self.assertEqual(code, 200)
                self.assertEqual(status["character_guid"], 5408)
                self.assertEqual(status["issues_count"], 1)
                code, issues = app.get("/api/wm/session/issues")
                self.assertEqual(code, 200)
                self.assertEqual(issues["issues"][0]["reason"], "director_effect_uncertain")
                code, effects = app.get("/api/wm/session/effects")
                self.assertEqual(code, 200)
                self.assertEqual(effects["effects"][0]["request_id"], 7)
            intake = MagicMock()
            intake.list_recent.return_value = [{"origin_key": "chat:7", "state": "decided",
                                                "decision": {"outcome": "no_action"}}]
            with patch("wm.autoplay.director_intake.DirectorIntakeLedger", return_value=intake):
                code, decisions = app.get("/api/wm/session/decisions")
            self.assertEqual(code, 200)
            self.assertEqual(decisions["decisions"][0]["decision"]["outcome"], "no_action")
            intake.list_recent.assert_called_once_with(player_guid=5408)

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
