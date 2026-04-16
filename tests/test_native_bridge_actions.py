from __future__ import annotations

import json
from pathlib import Path
import unittest

from wm.config import Settings
from wm.control.models import ControlAction
from wm.control.models import ControlAuthor
from wm.control.models import ControlPlayer
from wm.control.models import ControlProposal
from wm.control.models import ControlRisk
from wm.control.registry import ControlRegistry
from wm.control.validator import validate_control_proposal
from wm.events.executor import ReactionExecutor
from wm.events.models import PlannedAction
from wm.events.models import ReactionPlan
from wm.events.models import SubjectRef
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.action_kinds import native_action_kind_ids
from wm.sources.native_bridge.actions import NativeBridgeActionClient


class FakeMysqlClient:
    mysql_bin_path = "mysql"

    def __init__(self) -> None:
        self.sql: list[str] = []
        self.request_status = "pending"

    def query(self, **kwargs):  # type: ignore[no-untyped-def]
        sql = str(kwargs["sql"])
        self.sql.append(sql)
        if "SELECT LAST_INSERT_ID() AS RequestID" in sql:
            return [{"RequestID": "42"}]
        if "SELECT ROW_COUNT() AS Requeued" in sql:
            return [{"Requeued": "1"}]
        if "SELECT ROW_COUNT() AS Failed" in sql:
            return [{"Failed": "2"}]
        if "SELECT ROW_COUNT() AS Deleted" in sql:
            return [{"Deleted": "3"}]
        if "FROM wm_bridge_player_scope" in sql:
            return [{"PlayerGUID": "5406"}]
        if "FROM wm_bridge_action_policy" in sql:
            return [
                {
                    "ActionKind": "quest_add",
                    "Profile": "default",
                    "Enabled": "1",
                    "MaxRiskLevel": "medium",
                    "CooldownMS": "1000",
                    "BurstLimit": "5",
                    "AdminOnly": "0",
                }
            ]
        if "FROM wm_bridge_action_request" in sql and "WHERE RequestID = 42" in sql:
            return [
                {
                    "RequestID": "42",
                    "IdempotencyKey": "idem-1",
                    "PlayerGUID": "5406",
                    "ActionKind": "debug_ping",
                    "PayloadJSON": "{}",
                    "Status": self.request_status,
                    "CreatedBy": "test",
                    "RiskLevel": "low",
                    "CreatedAt": "2026-04-10 00:00:00",
                    "ClaimedAt": None,
                    "ProcessedAt": None,
                    "ResultJSON": "{}",
                    "ErrorText": None,
                }
            ]
        return []


class NativeBridgeActionTests(unittest.TestCase):
    def test_action_kind_catalog_covers_broad_surface(self) -> None:
        expected = {
            "player_apply_aura",
            "player_add_item",
            "quest_add",
            "creature_spawn",
            "gossip_override_set",
            "companion_spawn",
            "creature_set_display_id",
            "creature_set_health_pct",
            "creature_attack_player",
            "player_play_sound",
            "quest_complete",
            "zone_set_weather",
            "context_snapshot_request",
            "world_announce_to_player",
            "debug_ping",
        }

        self.assertTrue(expected.issubset(set(native_action_kind_ids())))
        self.assertTrue(NATIVE_ACTION_KIND_BY_ID["debug_ping"].implemented)
        self.assertTrue(NATIVE_ACTION_KIND_BY_ID["quest_add"].implemented)
        self.assertTrue(NATIVE_ACTION_KIND_BY_ID["world_announce_to_player"].implemented)
        self.assertFalse(NATIVE_ACTION_KIND_BY_ID["player_teleport"].default_enabled)

    def test_primitive_pack_1_catalog_is_implemented_but_policy_disabled_by_default(self) -> None:
        primitive_actions = {
            "player_apply_aura",
            "player_remove_aura",
            "player_restore_health_power",
            "player_add_item",
            "player_add_money",
            "player_add_reputation",
            "creature_say",
            "creature_emote",
            "creature_spawn",
            "creature_despawn",
        }

        for action_kind in primitive_actions:
            with self.subTest(action_kind=action_kind):
                action = NATIVE_ACTION_KIND_BY_ID[action_kind]
                self.assertTrue(action.implemented)
                self.assertFalse(action.default_enabled)

    def test_primitive_pack_1_contracts_are_documented(self) -> None:
        schema_path = Path("control/actions/native/native_bridge_action.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        contracts = schema["payload_contracts"]

        self.assertEqual(contracts["player_apply_aura"]["required"], ["spell_id"])
        self.assertIn("soulbound", contracts["player_add_item"]["optional"])
        self.assertIn("LiveGUIDLow", contracts["creature_spawn"]["notes"])
        self.assertIn("arc_key", contracts["creature_despawn"]["required_any"])

    def test_primitive_pack_1_sql_keeps_mutations_disabled_and_tracks_low_guid(self) -> None:
        sql_path = Path("native_modules/mod-wm-bridge/data/sql/world/updates/2026_04_16_00_wm_bridge_primitive_pack_1.sql")
        sql = sql_path.read_text(encoding="utf-8")

        self.assertIn("LiveGUIDLow INT NULL", sql)
        self.assertIn("idx_wm_bridge_world_object_live_low", sql)
        self.assertIn("('player_apply_aura', 'default', 0, 'medium'", sql)
        self.assertIn("('creature_spawn', 'default', 0, 'medium'", sql)
        self.assertNotIn("Enabled = VALUES(Enabled)", sql)

    def test_primitive_pack_1_cpp_uses_scope_policy_and_wm_owned_creature_guard(self) -> None:
        cpp_path = Path("native_modules/mod-wm-bridge/src/wm_bridge_action_queue.cpp")
        cpp = cpp_path.read_text(encoding="utf-8")

        for action_kind in (
            "player_apply_aura",
            "player_restore_health_power",
            "player_add_item",
            "player_add_reputation",
            "creature_spawn",
            "creature_despawn",
            "creature_say",
            "creature_emote",
        ):
            with self.subTest(action_kind=action_kind):
                self.assertIn(f'actionKind == "{action_kind}"', cpp)

        self.assertIn("ResolveScopedOnlinePlayer", cpp)
        self.assertIn("target_player_must_match_scoped_player", cpp)
        self.assertIn("LoadOwnedCreatureRef", cpp)
        self.assertIn("OwnerPlayerGUID = {}", cpp)
        self.assertIn("DespawnPolicy <> 'despawned'", cpp)
        self.assertIn("WorldDatabase.DirectExecute(", cpp)
        self.assertIn("Spawn result payload needs the WM-owned ObjectID immediately", cpp)

    def test_quest_add_cpp_matches_gm_add_semantics(self) -> None:
        cpp = Path("native_modules/mod-wm-bridge/src/wm_bridge_action_queue.cpp").read_text(encoding="utf-8")
        start = cpp.index('if (actionKind == "quest_add")')
        end = cpp.index('if (actionKind == "player_apply_aura")', start)
        quest_add_block = cpp[start:end]

        self.assertIn("StartQuest == questId", quest_add_block)
        self.assertIn("quest_starts_from_item", quest_add_block)
        self.assertIn("player->IsActiveQuest(questId)", quest_add_block)
        self.assertIn("quest_already_active", quest_add_block)
        self.assertIn("player->CanAddQuest(quest, false)", quest_add_block)
        self.assertIn("Mirror GM .quest add semantics for WM grants", quest_add_block)
        self.assertNotIn("player->CanTakeQuest(quest, false)", quest_add_block)

    def test_client_submits_idempotent_queue_request(self) -> None:
        client = FakeMysqlClient()
        bridge = NativeBridgeActionClient(client=client, settings=Settings())  # type: ignore[arg-type]

        request = bridge.submit(
            idempotency_key="idem-1",
            player_guid=5406,
            action_kind="debug_ping",
            payload={},
            created_by="test",
            sequence_id="seq-1",
            sequence_order=2,
            wait_for_prior=True,
            priority=1,
            target_map_id=0,
            target_x=-8949.95,
            target_y=-132.49,
            target_z=83.53,
            target_o=0.0,
        )

        self.assertEqual(request.request_id, 42)
        self.assertTrue(any("INSERT INTO wm_bridge_action_request" in sql for sql in client.sql))
        self.assertTrue(any("ON DUPLICATE KEY UPDATE" in sql for sql in client.sql))
        joined = "\n".join(client.sql)
        self.assertIn("SequenceID", joined)
        self.assertIn("'seq-1'", joined)
        self.assertIn("TargetMapID", joined)
        self.assertIn("-8949.95", joined)

    def test_client_can_recover_and_cleanup_queue_rows(self) -> None:
        client = FakeMysqlClient()
        bridge = NativeBridgeActionClient(client=client, settings=Settings())  # type: ignore[arg-type]

        recovered = bridge.recover_stale_claims()
        cleaned = bridge.cleanup_terminal_requests()

        self.assertEqual(recovered, {"requeued": 1, "failed": 2})
        self.assertEqual(cleaned, {"deleted": 3})
        joined = "\n".join(client.sql)
        self.assertIn("claim_expired_requeued", joined)
        self.assertIn("claim_expired_max_attempts", joined)
        self.assertIn("PurgeAfter IS NOT NULL", joined)

    def test_client_can_scope_player_and_set_policy(self) -> None:
        client = FakeMysqlClient()
        bridge = NativeBridgeActionClient(client=client, settings=Settings())  # type: ignore[arg-type]

        bridge.enable_player_scope(player_guid=5406, enabled=True, reason="lab")
        bridge.set_action_policy(action_kind="debug_ping", enabled=True)

        joined = "\n".join(client.sql)
        self.assertIn("wm_bridge_player_scope", joined)
        self.assertIn("wm_bridge_action_policy", joined)

    def test_client_can_read_scope_and_policy(self) -> None:
        client = FakeMysqlClient()
        bridge = NativeBridgeActionClient(client=client, settings=Settings())  # type: ignore[arg-type]

        scoped = bridge.is_player_scoped(player_guid=5406)
        policy = bridge.get_action_policy(action_kind="quest_add")

        self.assertTrue(scoped)
        self.assertIsNotNone(policy)
        assert policy is not None
        self.assertTrue(policy["enabled"])
        self.assertEqual(policy["max_risk_level"], "medium")

    def test_reaction_executor_dry_runs_native_bridge_action(self) -> None:
        executor = ReactionExecutor(client=FakeMysqlClient(), settings=Settings(), store=object())  # type: ignore[arg-type]
        plan = ReactionPlan(
            plan_key="plan-1",
            opportunity_type="control:manual_admin_action",
            rule_type="manual_admin_action",
            player_guid=5406,
            subject=SubjectRef(subject_type="control", subject_entry=0),
            actions=[
                PlannedAction(
                    kind="native_bridge_action",
                    payload={"native_action_kind": "debug_ping", "payload": {}},
                )
            ],
        )

        result = executor.preview(plan=plan)

        self.assertEqual(result.status, "preview")
        self.assertEqual(result.steps[0].kind, "native_bridge_action")
        self.assertEqual(result.steps[0].status, "dry-run")

    def test_validator_rejects_unknown_native_action_kind(self) -> None:
        proposal = ControlProposal(
            source_event=None,
            player=ControlPlayer(guid=5406, name="Jecia"),
            selected_recipe="manual_admin_action",
            action=ControlAction(kind="native_bridge_action", payload={"native_action_kind": "run_gm_command", "payload": {}}),
            rationale="Bad native action test.",
            risk=ControlRisk(level="low"),
            expected_effect="Nothing.",
            author=ControlAuthor(kind="manual_admin", name="test", manual_reason="validator test"),
        )

        result = validate_control_proposal(proposal=proposal, registry=ControlRegistry.load("control"))

        self.assertFalse(result.ok)
        self.assertTrue(any(issue.path == "action.payload.native_action_kind" for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
