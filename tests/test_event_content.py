import unittest

from wm.config import Settings
from wm.events.content import DeterministicContentFactory
from wm.events.models import ReactionOpportunity
from wm.events.models import SubjectRef
from wm.targets.resolver import TargetProfile


class FakeSlot:
    def __init__(self, reserved_id: int) -> None:
        self.reserved_id = reserved_id


class FakeAllocator:
    def __init__(self, slot: FakeSlot | None) -> None:
        self.slot = slot

    def peek_next_free_slot(self, *, entity_type: str):
        self.entity_type = entity_type
        return self.slot


class FakeResolveResult:
    def __init__(self, *, entry: int, name: str, profile: TargetProfile) -> None:
        self.entry = entry
        self.name = name
        self.profile = profile


class FakeResolver:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def resolve(self, *, entry: int | None = None, name: str | None = None):
        del name
        assert entry is not None
        self.calls.append(entry)
        if entry == 1498:
            return FakeResolveResult(
                entry=1498,
                name="Bethor Iceshard",
                profile=TargetProfile(
                    entry=1498,
                    name="Bethor Iceshard",
                    subname=None,
                    level_min=30,
                    level_max=30,
                    faction_id=68,
                    faction_label="Undercity / Forsaken",
                    mechanical_type="HUMANOID",
                    family=None,
                    rank="NORMAL",
                    unit_class="MAGE",
                    service_roles=["QUEST_GIVER"],
                    has_gossip_menu=True,
                ),
            )
        return FakeResolveResult(
            entry=46,
            name="Murloc Forager",
            profile=TargetProfile(
                entry=46,
                name="Murloc Forager",
                subname=None,
                level_min=9,
                level_max=10,
                faction_id=18,
                faction_label="Murloc",
                mechanical_type="HUMANOID",
                family=None,
                rank="NORMAL",
                unit_class="WARRIOR",
                service_roles=[],
                has_gossip_menu=False,
            ),
        )

    def fetch_template_defaults_for_questgiver(self, questgiver_entry: int) -> dict[str, object]:
        self.template_defaults_for = questgiver_entry
        return {"QuestType": 2}


class DeterministicContentFactoryTests(unittest.TestCase):
    def test_repeat_hunt_builds_bounty_action_when_slot_and_questgiver_exist(self) -> None:
        factory = DeterministicContentFactory(
            client=None,  # type: ignore[arg-type]
            settings=Settings(event_default_questgiver_entry=1498, event_followup_kill_count=6, event_default_reward_money_copper=1400),
            slot_allocator=FakeAllocator(FakeSlot(910010)),  # type: ignore[arg-type]
            resolver=FakeResolver(),  # type: ignore[arg-type]
        )
        opportunity = ReactionOpportunity(
            opportunity_type="repeat_hunt_followup",
            rule_type="repeat_hunt_followup",
            player_guid=42,
            subject=SubjectRef(subject_type="creature", subject_entry=46),
            source_event_key="evt-100",
            metadata={"subject_name": "Murloc Forager", "kill_count": 10},
        )

        actions, notes = factory.build_actions(opportunity)

        self.assertEqual([action.kind for action in actions], ["quest_publish", "announcement"])
        self.assertEqual(actions[0].payload["quest_id"], 910010)
        self.assertEqual(actions[0].payload["_wm_reserved_slot"]["reserved_id"], 910010)
        self.assertEqual(actions[0].payload["reward"]["money_copper"], 1400)
        self.assertEqual(notes["quest_generation"], "ready")

    def test_repeat_hunt_falls_back_to_announcement_without_questgiver(self) -> None:
        factory = DeterministicContentFactory(
            client=None,  # type: ignore[arg-type]
            settings=Settings(),
            slot_allocator=FakeAllocator(FakeSlot(910010)),  # type: ignore[arg-type]
            resolver=FakeResolver(),  # type: ignore[arg-type]
        )
        opportunity = ReactionOpportunity(
            opportunity_type="repeat_hunt_followup",
            rule_type="repeat_hunt_followup",
            player_guid=42,
            subject=SubjectRef(subject_type="creature", subject_entry=46),
            source_event_key="evt-101",
            metadata={"subject_name": "Murloc Forager"},
        )

        actions, notes = factory.build_actions(opportunity)

        self.assertEqual([action.kind for action in actions], ["announcement"])
        self.assertEqual(notes["quest_generation"], "skipped_missing_default_questgiver")

    def test_reactive_bounty_builds_direct_grant_action(self) -> None:
        factory = DeterministicContentFactory(
            client=None,  # type: ignore[arg-type]
            settings=Settings(),
            slot_allocator=FakeAllocator(FakeSlot(910010)),  # type: ignore[arg-type]
            resolver=FakeResolver(),  # type: ignore[arg-type]
        )
        opportunity = ReactionOpportunity(
            opportunity_type="reactive_bounty_grant",
            rule_type="reactive_bounty:kobold_vermin",
            player_guid=5406,
            subject=SubjectRef(subject_type="creature", subject_entry=6),
            source_event_key="evt-200",
            metadata={
                "subject_name": "Kobold Vermin",
                "reactive_rule": {
                    "rule_key": "reactive_bounty:kobold_vermin",
                    "quest_id": 910000,
                    "turn_in_npc_entry": 197,
                    "grant_mode": "direct_quest_add",
                    "kill_threshold": 4,
                    "window_seconds": 120,
                },
            },
        )

        actions, notes = factory.build_actions(opportunity)

        self.assertEqual([action.kind for action in actions], ["quest_grant"])
        self.assertEqual(actions[0].payload["quest_id"], 910000)
        self.assertEqual(actions[0].payload["player_guid"], 5406)
        self.assertEqual(notes["grant_generation"], "ready")


if __name__ == "__main__":
    unittest.main()
