import unittest

from wm.config import Settings
from wm.events.executor import ReactionExecutor
from wm.events.models import PlannedAction
from wm.events.models import ReactionCooldownKey
from wm.events.models import ReactionPlan
from wm.events.models import SubjectRef


class _DummyClient:
    mysql_bin_path = "mysql"


class FakePublishResult:
    def __init__(self, *, mode: str) -> None:
        self.mode = mode
        self.applied = mode == "apply"

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "applied": self.applied,
            "validation": {"ok": True, "issues": []},
            "preflight": {
                "ok": False,
                "issues": [
                    {
                        "path": "reserved_slot.status",
                        "message": "Reserved slot for quest 910001 has status `free`; expected `staged` for fresh publish or `active` for already-published managed content.",
                        "severity": "error",
                    }
                ],
                "reserved_slot": {
                    "EntityType": "quest",
                    "ReservedID": "910001",
                    "SlotStatus": "free",
                    "ArcKey": None,
                    "CharacterGUID": None,
                    "SourceQuestID": None,
                    "NotesJSON": None,
                },
            },
        }


class FakePublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []

    def publish(self, *, draft, mode: str):
        self.calls.append((draft, mode))
        return FakePublishResult(mode=mode)


class FakeExecutionStore:
    def __init__(self) -> None:
        self.recorded_events = []
        self.logged_reactions = []
        self.cooldowns = []

    def record(self, events):
        self.recorded_events.extend(events)
        return None

    def log_reaction(self, *, plan, status: str, result: dict[str, object]) -> None:
        self.logged_reactions.append((plan, status, result))

    def set_cooldown(self, *, key, cooldown_seconds: int, metadata=None) -> None:
        self.cooldowns.append((key, cooldown_seconds, metadata))


class FakeSlotAllocator:
    def __init__(self) -> None:
        self.calls = []

    def ensure_slot_prepared(
        self,
        *,
        entity_type: str,
        reserved_id: int,
        arc_key: str | None = None,
        character_guid: int | None = None,
        source_quest_id: int | None = None,
        notes=None,
    ):
        self.calls.append((entity_type, reserved_id, arc_key, character_guid, source_quest_id, notes))
        return None


class ReactionExecutorTests(unittest.TestCase):
    def _plan(self) -> ReactionPlan:
        return ReactionPlan(
            plan_key="repeat_hunt_followup:42:creature:46",
            opportunity_type="repeat_hunt_followup",
            rule_type="repeat_hunt_followup",
            player_guid=42,
            subject=SubjectRef(subject_type="creature", subject_entry=46),
            actions=[
                PlannedAction(
                    kind="quest_publish",
                    payload={
                        "quest_id": 910001,
                        "quest_level": 10,
                        "min_level": 8,
                        "questgiver_entry": 1498,
                        "questgiver_name": "Bethor Iceshard",
                        "title": "Bounty: Murloc Forager",
                        "quest_description": "Cull them.",
                        "objective_text": "Slay them.",
                        "offer_reward_text": "Well done.",
                        "request_items_text": "Did you do it?",
                        "objective": {"target_entry": 46, "target_name": "Murloc Forager", "kill_count": 8},
                        "reward": {"money_copper": 1200, "reward_item_count": 1},
                        "_wm_reserved_slot": {"entity_type": "quest", "reserved_id": 910001, "arc_key": "wm_event:repeat_hunt_followup"},
                    },
                ),
                PlannedAction(
                    kind="item_publish",
                    payload={"item_entry": 910100, "base_item_entry": 6948, "name": "WM Token"},
                ),
                PlannedAction(
                    kind="spell_publish",
                    payload={"spell_entry": 940000, "slot_kind": "visible_spell_slot", "name": "WM Passive", "base_visible_spell_id": 133},
                ),
            ],
            cooldown_key=ReactionCooldownKey(
                rule_type="repeat_hunt_followup",
                player_guid=42,
                subject_type="creature",
                subject_entry=46,
            ),
            cooldown_seconds=3600,
        )

    def test_dry_run_uses_publishers_without_setting_cooldown(self) -> None:
        store = FakeExecutionStore()
        slot_allocator = FakeSlotAllocator()
        executor = ReactionExecutor(client=_DummyClient(), settings=Settings(), store=store, slot_allocator=slot_allocator)
        executor.quest_publisher = FakePublisher()
        executor.item_publisher = FakePublisher()
        executor.spell_publisher = FakePublisher()

        result = executor.execute(plan=self._plan(), mode="dry-run")

        self.assertEqual(result.status, "dry-run")
        self.assertEqual([step.status for step in result.steps], ["dry-run", "dry-run", "dry-run"])
        self.assertEqual(store.cooldowns, [])
        self.assertEqual([event.event_type for event in store.recorded_events], ["reaction_planned"])
        self.assertEqual(slot_allocator.calls, [])
        quest_details = result.steps[0].details
        self.assertTrue(quest_details["dry_run_ready"])
        self.assertEqual(quest_details["slot_preparation"]["current_status"], "free")
        self.assertTrue(quest_details["slot_preparation"]["will_stage_on_apply"])
        self.assertTrue(any("would be staged automatically" in note for note in quest_details["dry_run_notes"]))

    def test_apply_logs_action_events_and_sets_cooldown(self) -> None:
        store = FakeExecutionStore()
        slot_allocator = FakeSlotAllocator()
        executor = ReactionExecutor(client=_DummyClient(), settings=Settings(), store=store, slot_allocator=slot_allocator)
        executor.quest_publisher = FakePublisher()
        executor.item_publisher = FakePublisher()
        executor.spell_publisher = FakePublisher()

        result = executor.execute(plan=self._plan(), mode="apply")

        self.assertEqual(result.status, "applied")
        self.assertEqual(
            [event.event_type for event in store.recorded_events],
            ["reaction_planned", "quest_published", "item_published", "spell_published"],
        )
        self.assertEqual(len(store.logged_reactions), 1)
        self.assertEqual(len(store.cooldowns), 1)
        self.assertEqual(slot_allocator.calls[0][0], "quest")
        self.assertEqual(slot_allocator.calls[0][1], 910001)


if __name__ == "__main__":
    unittest.main()
