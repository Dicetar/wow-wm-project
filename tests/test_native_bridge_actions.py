from __future__ import annotations

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
            "zone_set_weather",
            "context_snapshot_request",
            "debug_ping",
        }

        self.assertTrue(expected.issubset(set(native_action_kind_ids())))
        self.assertTrue(NATIVE_ACTION_KIND_BY_ID["debug_ping"].implemented)
        self.assertFalse(NATIVE_ACTION_KIND_BY_ID["player_teleport"].default_enabled)

    def test_client_submits_idempotent_queue_request(self) -> None:
        client = FakeMysqlClient()
        bridge = NativeBridgeActionClient(client=client, settings=Settings())  # type: ignore[arg-type]

        request = bridge.submit(
            idempotency_key="idem-1",
            player_guid=5406,
            action_kind="debug_ping",
            payload={},
            created_by="test",
        )

        self.assertEqual(request.request_id, 42)
        self.assertTrue(any("INSERT INTO wm_bridge_action_request" in sql for sql in client.sql))
        self.assertTrue(any("ON DUPLICATE KEY UPDATE" in sql for sql in client.sql))

    def test_client_can_scope_player_and_set_policy(self) -> None:
        client = FakeMysqlClient()
        bridge = NativeBridgeActionClient(client=client, settings=Settings())  # type: ignore[arg-type]

        bridge.enable_player_scope(player_guid=5406, enabled=True, reason="lab")
        bridge.set_action_policy(action_kind="debug_ping", enabled=True)

        joined = "\n".join(client.sql)
        self.assertIn("wm_bridge_player_scope", joined)
        self.assertIn("wm_bridge_action_policy", joined)

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
