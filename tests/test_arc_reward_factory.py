from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wm.arcs.factory import ArcRewardFactory
from wm.arcs.factory import PersonalArcScenario
from wm.arcs.factory import load_personal_arc_scenario
from wm.character.models import CharacterProfile
from wm.character.reader import CharacterStateBundle
from wm.config import Settings
from wm.targets.resolver import TargetProfile


SCENARIO_PATH = Path("control/examples/arcs/jecia_lens_arc_v1.json")
SHADOWMOON_SCENARIO_PATH = Path("control/examples/arcs/jecia_shadowmoon_lens_arc_v9.json")


class FakePublishResult:
    def __init__(self, *, mode: str, draft, applied: bool | None = None) -> None:
        self.mode = mode
        self.draft = draft
        self.applied = bool(mode == "apply" if applied is None else applied)

    def to_dict(self):
        return {
            "mode": self.mode,
            "draft": self.draft.to_dict(),
            "validation": {"ok": True, "issues": []},
            "preflight": {"ok": True, "issues": []},
            "snapshot_preview": {},
            "sql_plan": {"statements": []},
            "applied": self.applied,
        }


class FakeItemPublisher:
    def __init__(self, *, applied: bool | None = None) -> None:
        self.calls = []
        self.applied = applied

    def publish(self, *, draft, mode: str):
        self.calls.append((draft.item_entry, mode))
        return FakePublishResult(mode=mode, draft=draft, applied=self.applied)


class FakeQuestPublisher:
    def __init__(self, *, applied: bool | None = None) -> None:
        self.calls = []
        self.applied = applied
        self.publish_kwargs = []

    def publish(self, *, draft, mode: str, **kwargs):
        self.calls.append((draft, mode))
        self.publish_kwargs.append(kwargs)
        return FakePublishResult(mode=mode, draft=draft, applied=self.applied)


class FakeSlotAllocator:
    def __init__(self) -> None:
        self.allocated = []
        self.released = []

    def peek_next_free_slot(self, *, entity_type: str):
        self.peeked = entity_type
        return type("Slot", (), {"reserved_id": 910200})()

    def allocate_next_free_slot(self, **kwargs):
        self.allocated.append(kwargs)
        return type("Slot", (), {"reserved_id": 910201})()

    def release_slot(self, **kwargs):
        self.released.append(kwargs)
        return None


class FakeCharacterLoader:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready

    def load(self, *, character_guid: int):
        if not self.ready:
            return CharacterStateBundle(status="PARTIAL", notes=["No profile"])
        return CharacterStateBundle(
            profile=CharacterProfile(character_guid=int(character_guid), character_name="Jecia"),
            status="WORKING",
        )


class FakeJourneyStore:
    def __init__(self) -> None:
        self.calls = []

    def apply_plan(self, *, plan, mode: str):
        self.calls.append((plan, mode))

        class Result:
            def to_dict(self_nonlocal):
                return {
                    "schema_version": "wm.character_journey.seed.v1",
                    "player_guid": plan["player_guid"],
                    "mode": mode,
                    "ok": True,
                    "status": "WORKING",
                    "mutated": mode == "apply",
                    "operation_count": 3,
                    "operations": [],
                    "error": None,
                }

        return Result()


class FakeResolveResult:
    def __init__(self, *, entry: int, name: str, level_max: int) -> None:
        self.entry = entry
        self.name = name
        self.profile = TargetProfile(
            entry=entry,
            name=name,
            subname=None,
            level_min=max(1, level_max - 2),
            level_max=level_max,
            faction_id=17,
            faction_label="Defias Brotherhood",
            mechanical_type="HUMANOID",
            family=None,
            rank="NORMAL",
            unit_class="WARRIOR",
        )


class FakeResolver:
    def resolve(self, *, entry: int | None = None, name: str | None = None):
        del name
        if int(entry or 0) == 261:
            return FakeResolveResult(entry=261, name="Guard Thomas", level_max=35)
        return FakeResolveResult(entry=116, name="Defias Bandit", level_max=10)

    def fetch_template_defaults_for_questgiver(self, questgiver_entry: int):
        del questgiver_entry
        return {"QuestType": 2, "Flags": 128, "QuestSortID": 3520, "SpecialFlags": 1}


class FakeClient:
    mysql_bin_path = "mysql"

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "acore_characters" and "FROM wm_character_arc_state" in sql:
            return [{"CharacterGUID": "5406", "ArcKey": "jecia_lens_turns_v1", "StageKey": "lens_arc_quest_published", "Status": "active"}]
        if database == "acore_characters" and "SELECT SourceQuestID" in sql:
            return []
        if database == "acore_characters" and "FROM wm_character_reward_instance" in sql:
            return [{"CharacterGUID": "5406", "RewardKind": "item", "TemplateID": "910006", "SourceArcKey": "jecia_lens_turns_v1", "SourceQuestID": "910201"}]
        if database == "acore_world" and "FROM quest_template" in sql:
            return [{"ID": "910201", "LogTitle": "Jecia: The Lens Turns", "RewardItem1": "910006", "RewardAmount1": "1"}]
        if database == "acore_world" and "FROM wm_reserved_slot" in sql:
            return [{"EntityType": "quest", "ReservedID": "910201", "SlotStatus": "active", "ArcKey": "jecia_lens_turns_v1", "CharacterGUID": "5406"}]
        if database == "acore_world" and "FROM wm_publish_log" in sql:
            return [{"id": "99", "artifact_type": "quest", "artifact_entry": "910201", "action": "publish", "status": "success"}]
        if database == "acore_world" and "FROM item_template" in sql:
            return [{"entry": "910006", "name": "Night Watcher's Lens"}]
        raise AssertionError(f"Unexpected SQL for {database}: {sql}")


class FakeExistingArcClient(FakeClient):
    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        if database == "acore_characters" and "SELECT SourceQuestID" in sql:
            return [{"SourceQuestID": "910201"}]
        return super().query(host=host, port=port, user=user, password=password, database=database, sql=sql)


def _scenario() -> PersonalArcScenario:
    return load_personal_arc_scenario(SCENARIO_PATH)


def _factory(
    *,
    character_loader: FakeCharacterLoader | None = None,
    item_publisher: FakeItemPublisher | None = None,
    quest_publisher: FakeQuestPublisher | None = None,
    slot_allocator: FakeSlotAllocator | None = None,
    journey_store: FakeJourneyStore | None = None,
) -> ArcRewardFactory:
    return ArcRewardFactory(
        client=FakeClient(),  # type: ignore[arg-type]
        settings=Settings(world_db_port=33307, char_db_port=33307, soap_enabled=False),
        character_loader=character_loader or FakeCharacterLoader(),
        item_publisher=item_publisher or FakeItemPublisher(),
        quest_publisher=quest_publisher or FakeQuestPublisher(),
        slot_allocator=slot_allocator or FakeSlotAllocator(),
        journey_store=journey_store or FakeJourneyStore(),
        resolver=FakeResolver(),
    )


def _existing_factory() -> ArcRewardFactory:
    return ArcRewardFactory(
        client=FakeExistingArcClient(),  # type: ignore[arg-type]
        settings=Settings(world_db_port=33307, char_db_port=33307, soap_enabled=False),
        character_loader=FakeCharacterLoader(),
        item_publisher=FakeItemPublisher(),
        quest_publisher=FakeQuestPublisher(),
        slot_allocator=FakeSlotAllocator(),
        journey_store=FakeJourneyStore(),
        resolver=FakeResolver(),
    )


class ArcRewardFactoryScenarioTests(unittest.TestCase):
    def test_loads_v1_personal_arc_scenario(self) -> None:
        scenario = _scenario()

        self.assertEqual(scenario.schema_version, "wm.arc_reward_factory.personal_arc.v1")
        self.assertEqual(scenario.player_guid, 5406)
        self.assertEqual(scenario.arc_key, "jecia_lens_turns_v1")
        self.assertEqual(len(scenario.beats), 3)
        self.assertEqual(scenario.reward["item_entry"], 910006)
        self.assertTrue(Path(scenario.reward["item_draft_path"]).is_absolute())

    def test_loads_shadowmoon_level_fitting_personal_arc_scenario(self) -> None:
        scenario = load_personal_arc_scenario(SHADOWMOON_SCENARIO_PATH)

        self.assertEqual(scenario.schema_version, "wm.arc_reward_factory.personal_arc.v1")
        self.assertEqual(scenario.player_guid, 5406)
        self.assertEqual(scenario.arc_key, "jecia_shadowmoon_lens_v9")
        self.assertEqual(scenario.target["creature_entry"], 21059)
        self.assertEqual(scenario.target["kill_count"], 6)
        self.assertEqual(scenario.turn_in_npc["entry"], 21027)
        self.assertEqual(scenario.quest["quest_level"], 70)
        self.assertEqual(scenario.quest["min_level"], 68)
        self.assertEqual(scenario.reward["item_entry"], 910013)
        self.assertEqual(scenario.reward["item_count"], 1)
        self.assertEqual(scenario.reward["reward_item_mode"], "fixed")
        self.assertEqual(scenario.runtime_sync["item_commands"], [".reload item_template"])
        self.assertTrue(Path(scenario.reward["item_draft_path"]).is_absolute())

    def test_rejects_freeform_mutation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).joinpath("bad_arc.json")
            payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
            payload["gm_command"] = ".quest add 1"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_personal_arc_scenario(path)

    def test_requires_two_or_three_beats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).joinpath("bad_arc.json")
            payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
            payload["beats"] = [payload["beats"][0]]
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_personal_arc_scenario(path)


class ArcRewardFactoryServiceTests(unittest.TestCase):
    def test_dry_run_previews_fresh_quest_slot_without_mutation(self) -> None:
        item_publisher = FakeItemPublisher()
        quest_publisher = FakeQuestPublisher()
        slot_allocator = FakeSlotAllocator()
        journey_store = FakeJourneyStore()
        factory = _factory(
            item_publisher=item_publisher,
            quest_publisher=quest_publisher,
            slot_allocator=slot_allocator,
            journey_store=journey_store,
        )

        result = factory.dry_run(scenario=_scenario(), runtime_sync_mode="off")

        self.assertTrue(result.ok)
        self.assertEqual(result.preview_quest_id, 910200)
        self.assertEqual(item_publisher.calls, [(910006, "dry-run")])
        self.assertEqual(quest_publisher.calls[0][1], "dry-run")
        self.assertEqual(quest_publisher.publish_kwargs[0], {"allow_free_reserved_slot_preview": True})
        self.assertEqual(slot_allocator.allocated, [])
        self.assertEqual(journey_store.calls, [])
        self.assertEqual(result.journey["mode"], "dry-run")

    def test_apply_allocates_fresh_slot_publishes_quest_and_records_journey(self) -> None:
        slot_allocator = FakeSlotAllocator()
        journey_store = FakeJourneyStore()
        quest_publisher = FakeQuestPublisher()
        factory = _factory(
            slot_allocator=slot_allocator,
            journey_store=journey_store,
            quest_publisher=quest_publisher,
        )

        result = factory.apply(scenario=_scenario(), runtime_sync_mode="off")

        self.assertTrue(result.ok)
        self.assertEqual(result.allocated_quest_id, 910201)
        self.assertEqual(slot_allocator.allocated[0]["entity_type"], "quest")
        self.assertEqual(slot_allocator.allocated[0]["arc_key"], "jecia_lens_turns_v1")
        self.assertEqual(slot_allocator.allocated[0]["character_guid"], 5406)
        quest_draft = quest_publisher.calls[0][0]
        self.assertEqual(quest_draft.quest_id, 910201)
        self.assertEqual(quest_draft.title, "Jecia: The Lens Turns")
        self.assertEqual(quest_draft.reward.reward_item_entry, 910006)
        self.assertEqual(quest_draft.reward.money_copper, 0)
        self.assertEqual(quest_draft.template_defaults["Flags"], 8)
        self.assertEqual(quest_draft.template_defaults["QuestFlags"], 8)
        self.assertEqual(quest_draft.template_defaults["QuestSortID"], 3520)
        self.assertEqual(quest_draft.template_defaults["SpecialFlags"], 1)
        self.assertEqual(journey_store.calls[0][1], "apply")
        plan = journey_store.calls[0][0]
        self.assertEqual(plan["arc_states"][0]["arc_key"], "jecia_lens_turns_v1")
        self.assertEqual(plan["reward_instances"][0]["source_quest_id"], 910201)

    def test_apply_stops_before_mutation_when_journey_not_ready(self) -> None:
        slot_allocator = FakeSlotAllocator()
        item_publisher = FakeItemPublisher()
        quest_publisher = FakeQuestPublisher()
        factory = _factory(
            character_loader=FakeCharacterLoader(ready=False),
            item_publisher=item_publisher,
            quest_publisher=quest_publisher,
            slot_allocator=slot_allocator,
        )

        result = factory.apply(scenario=_scenario(), runtime_sync_mode="off")

        self.assertFalse(result.ok)
        self.assertEqual(item_publisher.calls, [])
        self.assertEqual(quest_publisher.calls, [])
        self.assertEqual(slot_allocator.allocated, [])

    def test_apply_releases_slot_when_quest_publish_fails(self) -> None:
        slot_allocator = FakeSlotAllocator()
        factory = _factory(
            slot_allocator=slot_allocator,
            quest_publisher=FakeQuestPublisher(applied=False),
        )

        result = factory.apply(scenario=_scenario(), runtime_sync_mode="off")

        self.assertFalse(result.ok)
        self.assertEqual(slot_allocator.released, [{"entity_type": "quest", "reserved_id": 910201}])

    def test_verify_checks_arc_reward_quest_slot_and_item_rows(self) -> None:
        result = _factory().verify(scenario=_scenario())

        self.assertTrue(result.ok)
        assert result.verification is not None
        self.assertEqual(result.verification["source_quest_ids"], [910201])
        self.assertEqual(result.verification["quest_template_rows"][0]["RewardItem1"], "910006")

    def test_apply_is_idempotent_when_arc_reward_is_already_recorded(self) -> None:
        factory = _existing_factory()

        result = factory.apply(scenario=_scenario(), runtime_sync_mode="off")

        self.assertTrue(result.ok)
        self.assertFalse(result.applied)
        self.assertEqual(result.allocated_quest_id, 910201)
        self.assertIn("already recorded", result.notes[0])


if __name__ == "__main__":
    unittest.main()
