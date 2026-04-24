from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.config import Settings
from wm.content.playcycle import ItemEffectPlaycycle
from wm.content.playcycle import ItemEffectScenario
from wm.content.playcycle import load_item_effect_scenario


SCENARIO_PATH = Path("control/examples/content_playcycles/night_watchers_lens_item_effect.json")


class FakePublishResult:
    def __init__(self, *, mode: str, draft, applied: bool | None = None) -> None:
        self.payload = {
            "mode": mode,
            "draft": draft.to_dict(),
            "validation": {"ok": True, "issues": []},
            "preflight": {
                "ok": True,
                "issues": [],
                "reserved_slot": {"EntityType": "item", "ReservedID": str(draft.item_entry), "SlotStatus": "staged"},
            },
            "snapshot_preview": {"existing_item_template": []},
            "sql_plan": {"statements": []},
            "final_row_preview": {"entry": draft.item_entry, "name": draft.name},
            "applied": mode == "apply" if applied is None else applied,
        }

    def to_dict(self):
        return self.payload


class FakeItemPublisher:
    def __init__(self) -> None:
        self.calls = []

    def publish(self, *, draft, mode: str):
        self.calls.append((draft.item_entry, mode))
        return FakePublishResult(mode=mode, draft=draft)


class FakeFailedApplyPublisher(FakeItemPublisher):
    def publish(self, *, draft, mode: str):
        self.calls.append((draft.item_entry, mode))
        return FakePublishResult(mode=mode, draft=draft, applied=False)


class FakeRequest:
    def __init__(self, *, action_kind: str, status: str = "done") -> None:
        self.request_id = 77
        self.idempotency_key = "idem"
        self.player_guid = 5406
        self.action_kind = action_kind
        self.payload = {}
        self.status = status

    def to_dict(self):
        return {
            "request_id": self.request_id,
            "action_kind": self.action_kind,
            "status": self.status,
        }


class FakeNativeBridge:
    def __init__(self) -> None:
        self.submitted = []
        self.scoped = True
        self.policies = {
            "player_add_item": {"enabled": True, "max_risk_level": "medium"},
            "player_remove_item": {"enabled": True, "max_risk_level": "medium"},
        }
        self.last_request: FakeRequest | None = None

    def is_player_scoped(self, *, player_guid: int):
        return self.scoped and player_guid == 5406

    def get_action_policy(self, *, action_kind: str):
        return self.policies.get(action_kind)

    def submit(self, **kwargs):
        self.submitted.append(kwargs)
        self.last_request = FakeRequest(action_kind=kwargs["action_kind"])
        return self.last_request

    def wait(self, *, request_id: int):
        del request_id
        assert self.last_request is not None
        return self.last_request


class FakeClient:
    mysql_bin_path = "mysql"

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "acore_world" and "FROM item_template" in sql:
            return [{"entry": "910006", "name": "Night Watcher's Lens", "description": "Lens"}]
        if database == "acore_world" and "FROM wm_publish_log" in sql:
            return [{"id": "10", "action": "publish", "status": "success", "notes": "ok"}]
        if database == "acore_world" and "FROM wm_rollback_snapshot" in sql:
            return [{"id": "11"}]
        if database == "acore_world" and "FROM wm_reserved_slot" in sql:
            return [{"EntityType": "item", "ReservedID": "910006", "SlotStatus": "active"}]
        if database == "acore_characters" and "FROM character_inventory" in sql:
            return [{"OwnerGUID": "5406", "ItemGuid": "999", "ItemEntry": "910006"}]
        raise AssertionError(f"Unexpected SQL for {database}: {sql}")


class FakeSlotAllocator:
    def __init__(self) -> None:
        self.allocated = []
        self.released = []

    def allocate_next_free_slot(self, **kwargs):
        self.allocated.append(kwargs)
        return type("Slot", (), {"reserved_id": 910123})()

    def release_slot(self, **kwargs):
        self.released.append(kwargs)
        return None


class FakeReactiveStore:
    def fetch_character_name(self, *, player_guid: int):
        self.player_guid = player_guid
        return "Jecia"


class FakeResolveResult:
    def __init__(self, *, entry: int, name: str) -> None:
        self.entry = entry
        self.name = name
        self.profile = type("Profile", (), {"entry": entry, "name": name, "level_max": 10, "mechanical_type": "HUMANOID", "family": None})()


class FakeResolver:
    def resolve(self, *, entry: int | None = None, name: str | None = None):
        del name
        names = {116: "Defias Bandit", 261: "Guard Thomas"}
        return FakeResolveResult(entry=int(entry or 0), name=names.get(int(entry or 0), f"Entry {entry}"))

    def fetch_template_defaults_for_questgiver(self, questgiver_entry: int):
        del questgiver_entry
        return {"QuestType": 2}


class FakeBountyInstaller:
    def __init__(self) -> None:
        self.rules = []

    def install(self, *, rule, mode: str):
        self.rules.append((rule, mode))

        class Result:
            def to_dict(self_nonlocal):
                return {
                    "mode": mode,
                    "rule": rule.to_dict(),
                    "quest_exists": False,
                    "quest_matches_reactive_shape": False,
                    "quest_publish": {"applied": True, "preflight": {"ok": True}},
                    "notes": ["installed"],
                }

        return Result()


class FakeRollbackResult:
    def to_dict(self):
        return {
            "item_entry": 910006,
            "mode": "apply",
            "snapshot_found": True,
            "snapshot_id": 11,
            "restored_action": "delete_slot",
            "applied": True,
            "runtime_sync": {"restart_recommended": True},
            "restart_recommended": True,
            "ok": True,
            "issues": [],
        }


class FakeRollback:
    def __init__(self) -> None:
        self.calls = []

    def rollback(self, **kwargs):
        self.calls.append(kwargs)
        return FakeRollbackResult()


def _scenario() -> ItemEffectScenario:
    return load_item_effect_scenario(SCENARIO_PATH)


def _service(
    *,
    publisher: FakeItemPublisher | None = None,
    native_bridge: FakeNativeBridge | None = None,
    slot_allocator: FakeSlotAllocator | None = None,
    bounty_installer: FakeBountyInstaller | None = None,
    rollback: FakeRollback | None = None,
) -> ItemEffectPlaycycle:
    return ItemEffectPlaycycle(
        client=FakeClient(),  # type: ignore[arg-type]
        settings=Settings(world_db_port=33307, char_db_port=33307, soap_enabled=False),
        item_publisher=publisher or FakeItemPublisher(),
        native_bridge=native_bridge or FakeNativeBridge(),
        item_rollback=rollback or FakeRollback(),
        slot_allocator=slot_allocator or FakeSlotAllocator(),
        reactive_store=FakeReactiveStore(),
        resolver=FakeResolver(),
        bounty_installer=bounty_installer or FakeBountyInstaller(),
    )


class ContentPlaycycleScenarioTests(unittest.TestCase):
    def test_loads_v1_item_effect_scenario(self) -> None:
        scenario = _scenario()

        self.assertEqual(scenario.schema_version, "wm.content_playcycle.item_effect.v1")
        self.assertEqual(scenario.player_guid, 5406)
        self.assertEqual(scenario.item_entry, 910006)
        self.assertTrue(scenario.item_draft_path.is_absolute())

    def test_rejects_freeform_mutation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).joinpath("bad.json")
            payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
            payload["freeform_sql"] = "DELETE FROM item_template"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_item_effect_scenario(path)


class ContentPlaycycleServiceTests(unittest.TestCase):
    def test_dry_run_checks_readiness_without_submitting_native_action(self) -> None:
        publisher = FakeItemPublisher()
        native = FakeNativeBridge()
        service = _service(publisher=publisher, native_bridge=native)

        result = service.dry_run(scenario=_scenario(), runtime_sync_mode="scenario")

        self.assertTrue(result.ok)
        self.assertEqual(publisher.calls, [(910006, "dry-run")])
        self.assertEqual(native.submitted, [])
        self.assertTrue(result.direct_grant["ready"])

    def test_apply_publishes_and_submits_typed_native_grant(self) -> None:
        publisher = FakeItemPublisher()
        native = FakeNativeBridge()
        service = _service(publisher=publisher, native_bridge=native)

        result = service.apply(scenario=_scenario(), runtime_sync_mode="off")

        self.assertTrue(result.ok)
        self.assertTrue(result.restart_recommended)
        self.assertEqual(publisher.calls, [(910006, "apply")])
        self.assertEqual(native.submitted[0]["action_kind"], "player_add_item")
        self.assertEqual(native.submitted[0]["payload"]["item_id"], 910006)
        self.assertIn("direct_grant:publish:10", native.submitted[0]["idempotency_key"])

    def test_apply_does_not_grant_when_publish_did_not_apply(self) -> None:
        publisher = FakeFailedApplyPublisher()
        native = FakeNativeBridge()
        service = _service(publisher=publisher, native_bridge=native)

        result = service.apply(scenario=_scenario(), runtime_sync_mode="off")

        self.assertFalse(result.ok)
        self.assertEqual(native.submitted, [])
        self.assertEqual(result.direct_grant["status"], "skipped")
        self.assertEqual(result.runtime_sync["note"], "Item publish did not apply; runtime sync and direct grant were skipped.")

    def test_verify_checks_publish_snapshot_slot_and_inventory_evidence(self) -> None:
        result = _service().verify(scenario=_scenario())

        self.assertTrue(result.ok)
        assert result.verification is not None
        self.assertEqual(result.verification["inventory_rows"][0]["ItemEntry"], "910006")

    def test_promote_quest_uses_fresh_reserved_slot_and_item_reward(self) -> None:
        slot_allocator = FakeSlotAllocator()
        installer = FakeBountyInstaller()
        service = _service(slot_allocator=slot_allocator, bounty_installer=installer)

        result = service.promote_quest(scenario=_scenario())

        self.assertTrue(result.ok)
        self.assertEqual(slot_allocator.allocated[0]["entity_type"], "quest")
        rule, mode = installer.rules[0]
        self.assertEqual(mode, "apply")
        self.assertEqual(rule.quest_id, 910123)
        self.assertEqual(rule.metadata["reward_item_entry"], 910006)
        self.assertEqual(rule.metadata["reward_item_count"], 1)

    def test_rollback_reports_inventory_cleanup_as_partial_until_requested_and_proven(self) -> None:
        rollback = FakeRollback()
        service = _service(rollback=rollback)

        result = service.rollback(
            scenario=_scenario(),
            runtime_sync_mode="off",
            cleanup_player_item=False,
            admin_override_remove_item=False,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.outcome, "PARTIAL")
        self.assertEqual(result.cleanup["status"], "skipped")
        self.assertEqual(rollback.calls[0]["mode"], "apply")


if __name__ == "__main__":
    unittest.main()
