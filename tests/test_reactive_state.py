import unittest

from wm.reactive.models import PlayerQuestRuntimeState
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.state import ReactiveQuestRuntimeSynchronizer


class FakeEventStore:
    def __init__(self) -> None:
        self.cooldown_calls = []

    def set_cooldown(self, *, key, cooldown_seconds: int, triggered_at: str | None = None, metadata=None) -> None:
        self.cooldown_calls.append((key, cooldown_seconds, triggered_at, metadata))


class FakeReactiveStore:
    def __init__(self) -> None:
        self.rules = [
            ReactiveQuestRule(
                rule_key="reactive_bounty:kobold_vermin",
                is_active=True,
                player_guid_scope=5406,
                subject_type="creature",
                subject_entry=6,
                trigger_event_type="kill",
                kill_threshold=4,
                window_seconds=120,
                quest_id=910000,
                turn_in_npc_entry=197,
                grant_mode="direct_quest_add",
                post_reward_cooldown_seconds=60,
                metadata={},
                notes=[],
            )
        ]
        self.runtime_state = "none"
        self.snapshot = None
        self.saved_states: list[PlayerQuestRuntimeState] = []

    def list_active_rules(self, *, player_guid: int | None = None):
        del player_guid
        return list(self.rules)

    def fetch_character_quest_status(self, *, player_guid: int, quest_id: int) -> str:
        del player_guid, quest_id
        return self.runtime_state

    def get_player_quest_runtime_state(self, *, player_guid: int, quest_id: int):
        del player_guid, quest_id
        return self.snapshot

    def set_player_quest_runtime_state(self, state: PlayerQuestRuntimeState) -> None:
        self.snapshot = state
        self.saved_states.append(state)


class ReactiveQuestRuntimeSynchronizerTests(unittest.TestCase):
    def test_rewarded_transition_emits_event_and_sets_cooldown(self) -> None:
        event_store = FakeEventStore()
        reactive_store = FakeReactiveStore()
        reactive_store.snapshot = PlayerQuestRuntimeState(
            player_guid=5406,
            quest_id=910000,
            current_state="complete",
            last_transition_at="2026-04-08 12:00:00",
        )
        reactive_store.runtime_state = "rewarded"
        synchronizer = ReactiveQuestRuntimeSynchronizer(
            store=event_store,  # type: ignore[arg-type]
            reactive_store=reactive_store,  # type: ignore[arg-type]
        )

        result = synchronizer.poll(player_guid=5406, preview=False)

        self.assertEqual(result.checked_rules, 1)
        self.assertEqual(len(result.observed_transitions), 1)
        self.assertEqual(result.observed_transitions[0].event_type, "quest_rewarded")
        self.assertEqual(len(event_store.cooldown_calls), 1)
        self.assertEqual(event_store.cooldown_calls[0][1], 60)
        self.assertEqual(reactive_store.saved_states[-1].current_state, "rewarded")

    def test_preview_does_not_write_state_or_cooldown(self) -> None:
        event_store = FakeEventStore()
        reactive_store = FakeReactiveStore()
        reactive_store.snapshot = PlayerQuestRuntimeState(
            player_guid=5406,
            quest_id=910000,
            current_state="none",
        )
        reactive_store.runtime_state = "incomplete"
        synchronizer = ReactiveQuestRuntimeSynchronizer(
            store=event_store,  # type: ignore[arg-type]
            reactive_store=reactive_store,  # type: ignore[arg-type]
        )

        result = synchronizer.poll(player_guid=5406, preview=True)

        self.assertEqual(len(result.observed_transitions), 1)
        self.assertEqual(result.observed_transitions[0].event_type, "quest_granted")
        self.assertEqual(event_store.cooldown_calls, [])
        self.assertEqual(reactive_store.saved_states, [])


if __name__ == "__main__":
    unittest.main()
