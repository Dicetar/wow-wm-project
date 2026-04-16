import unittest

from wm.config import Settings
from wm.events.models import WMEvent
from wm.reactive.auto_bounty import AutoBountyTarget
from wm.reactive.auto_bounty import ReactiveAutoBountyManager
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.turn_in_selector import ZoneQuestTurnInCandidate
from wm.reactive.turn_in_selector import ZoneQuestTurnInSelector


class _SelectorClient:
    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str):
        del host, port, user, password
        if database == "acore_characters" and "SELECT race FROM characters" in sql:
            return [{"race": "1"}]
        if database == "acore_world" and "QuestSortID = 10" in sql:
            return [
                {
                    "entry": "264",
                    "name": "Commander Althea Ebonlocke",
                    "subname": "",
                    "faction": "84",
                    "faction_name": "Stormwind Guard",
                    "spawn_count": "1",
                    "quest_starter_count": "6",
                    "quest_ender_count": "4",
                },
                {
                    "entry": "679",
                    "name": "Innkeeper Trelayne",
                    "subname": "",
                    "faction": "35",
                    "faction_name": "Friendly / Passive / Generic",
                    "spawn_count": "1",
                    "quest_starter_count": "3",
                    "quest_ender_count": "2",
                },
            ]
        if database == "acore_world" and "WHERE c.zoneId = 10" in sql:
            return []
        raise AssertionError(f"Unexpected SQL for {database}: {sql}")


class _FakeResolveResult:
    def __init__(self, *, entry: int, name: str) -> None:
        self.entry = entry
        self.name = name
        self.profile = type(
            "Profile",
            (),
            {
                "entry": entry,
                "name": name,
                "level_max": 24,
                "mechanical_type": "HUMANOID",
                "family": None,
            },
        )()


class _FakeResolver:
    def resolve(self, *, entry: int | None = None, name: str | None = None):
        del name
        mapping = {
            533: _FakeResolveResult(entry=533, name="Nightbane Shadow Weaver"),
            264: _FakeResolveResult(entry=264, name="Commander Althea Ebonlocke"),
            240: _FakeResolveResult(entry=240, name="Marshal Dughan"),
        }
        if entry not in mapping:
            raise AssertionError(f"Unexpected resolver entry: {entry}")
        return mapping[int(entry)]


class _FakeInstaller:
    def __init__(self) -> None:
        self.calls: list[tuple[ReactiveQuestRule, str]] = []

    def install(self, *, rule: ReactiveQuestRule, mode: str):
        self.calls.append((rule, mode))
        return None


class _FakeReactiveStore:
    def __init__(self) -> None:
        self.rules_by_key: dict[str, ReactiveQuestRule] = {}
        self.deactivated: list[tuple[int, str | None]] = []

    def get_rule_by_key(self, *, rule_key: str) -> ReactiveQuestRule | None:
        return self.rules_by_key.get(rule_key)

    def fetch_character_name(self, *, player_guid: int) -> str | None:
        if int(player_guid) == 5406:
            return "Jecia"
        return None

    def deactivate_player_auto_bounty_rules(self, *, player_guid: int, except_rule_key: str | None = None) -> None:
        self.deactivated.append((int(player_guid), except_rule_key))


class _FakeSlotAllocator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def allocate_next_free_slot(self, **kwargs):
        self.calls.append(kwargs)
        return type("Slot", (), {"reserved_id": 910321})()


class _FakeTurnInSelector:
    def __init__(self, candidate: ZoneQuestTurnInCandidate | None) -> None:
        self.candidate = candidate
        self.calls: list[tuple[int, int | None]] = []

    def select(self, *, player_guid: int, zone_id: int | None):
        self.calls.append((int(player_guid), zone_id))
        return self.candidate


class ReactiveAutoBountyTests(unittest.TestCase):
    def test_zone_selector_prefers_player_faction_hub_candidate(self) -> None:
        selector = ZoneQuestTurnInSelector(
            client=_SelectorClient(),  # type: ignore[arg-type]
            settings=Settings(),
        )

        candidate = selector.select(player_guid=5406, zone_id=10)

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.entry, 264)
        self.assertEqual(candidate.name, "Commander Althea Ebonlocke")

    def test_dynamic_auto_bounty_builds_rule_for_observed_entry_and_zone(self) -> None:
        reactive_store = _FakeReactiveStore()
        installer = _FakeInstaller()
        slot_allocator = _FakeSlotAllocator()
        turn_in_selector = _FakeTurnInSelector(
            ZoneQuestTurnInCandidate(
                entry=264,
                name="Commander Althea Ebonlocke",
                subname=None,
                faction_id=84,
                faction_label="Stormwind Guard",
                starter_count=6,
                ender_count=4,
                spawn_count=1,
            )
        )
        manager = ReactiveAutoBountyManager(
            client=object(),  # type: ignore[arg-type]
            settings=Settings(),
            reactive_store=reactive_store,  # type: ignore[arg-type]
            installer=installer,  # type: ignore[arg-type]
            resolver=_FakeResolver(),  # type: ignore[arg-type]
            slot_allocator=slot_allocator,  # type: ignore[arg-type]
            turn_in_selector=turn_in_selector,  # type: ignore[arg-type]
        )
        event = WMEvent(
            event_class="observed",
            event_type="kill",
            source="native_bridge",
            source_event_key="native_bridge:kill:1",
            player_guid=5406,
            subject_type="creature",
            subject_entry=533,
            zone_id=10,
            metadata={"payload": {"subject_name": "Nightbane Shadow Weaver"}},
        )

        rule = manager.ensure_rule_for_event(event)

        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertEqual(rule.rule_key, "reactive_bounty:auto:zone:10:subject:533")
        self.assertEqual(rule.quest_id, 910321)
        self.assertEqual(rule.turn_in_npc_entry, 264)
        self.assertEqual(rule.quest.title, "Bounty: Nightbane Shadow Weaver")
        self.assertTrue(bool(rule.metadata.get("require_consecutive_kills")))
        self.assertEqual(rule.metadata.get("auto_bounty_turn_in_strategy"), "zone_quest_ties")
        self.assertEqual(installer.calls[0][1], "apply")
        self.assertEqual(turn_in_selector.calls, [(5406, 10)])
        self.assertEqual(reactive_store.deactivated, [(5406, "reactive_bounty:auto:zone:10:subject:533")])

    def test_override_target_keeps_explicit_turn_in_npc_and_quest_id(self) -> None:
        reactive_store = _FakeReactiveStore()
        installer = _FakeInstaller()
        slot_allocator = _FakeSlotAllocator()
        turn_in_selector = _FakeTurnInSelector(None)
        manager = ReactiveAutoBountyManager(
            client=object(),  # type: ignore[arg-type]
            settings=Settings(),
            reactive_store=reactive_store,  # type: ignore[arg-type]
            installer=installer,  # type: ignore[arg-type]
            resolver=_FakeResolver(),  # type: ignore[arg-type]
            slot_allocator=slot_allocator,  # type: ignore[arg-type]
            turn_in_selector=turn_in_selector,  # type: ignore[arg-type]
            targets=(
                AutoBountyTarget(
                    subject_entry=533,
                    zone_id=10,
                    turn_in_npc_entry=240,
                    quest_id=910999,
                    quest_title="Bounty: Shadow Weavers",
                    objective_target_name="Nightbane Shadow Weavers",
                ),
            ),
        )
        event = WMEvent(
            event_class="observed",
            event_type="kill",
            source="native_bridge",
            source_event_key="native_bridge:kill:2",
            player_guid=5406,
            subject_type="creature",
            subject_entry=533,
            zone_id=10,
            metadata={"payload": {"subject_name": "Nightbane Shadow Weaver"}},
        )

        rule = manager.ensure_rule_for_event(event)

        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertEqual(rule.quest_id, 910999)
        self.assertEqual(rule.turn_in_npc_entry, 240)
        self.assertEqual(rule.quest.title, "Bounty: Shadow Weavers")
        self.assertEqual(turn_in_selector.calls, [])
        self.assertEqual(slot_allocator.calls, [])


if __name__ == "__main__":
    unittest.main()
