import unittest
from unittest.mock import patch

from wm.config import Settings
from wm.events.models import WMEvent
from wm.events.rules import DeterministicRuleEngine
from wm.journal.models import JournalCounters
from wm.journal.models import JournalSummary
from wm.journal.models import SubjectCard
from wm.journal.reader import SubjectJournalBundle
from wm.reactive.models import PlayerQuestRuntimeState
from wm.reactive.models import ReactiveQuestRule


class _DummyClient:
    pass


class FakeRuleStore:
    def __init__(self) -> None:
        self.marked_evaluated: list[int] = []
        self.cooldown_active = False
        self.subject_events: list[WMEvent] = []

    def is_evaluated(self, *, event_id: int) -> bool:
        return event_id in self.marked_evaluated

    def mark_evaluated(self, *, event_id: int) -> None:
        self.marked_evaluated.append(event_id)

    def is_cooldown_active(self, key, *, at: str | None = None) -> bool:
        del key, at
        return self.cooldown_active

    def list_subject_events(
        self,
        *,
        player_guid: int,
        subject_type: str,
        subject_entry: int,
        event_type: str | None = None,
        event_class: str = "observed",
        limit: int = 200,
        newest_first: bool = False,
    ):
        del limit, newest_first
        rows = [
            event
            for event in self.subject_events
            if event.player_guid == player_guid
            and event.subject_type == subject_type
            and event.subject_entry == subject_entry
            and event.event_class == event_class
        ]
        if event_type is not None:
            rows = [event for event in rows if event.event_type == event_type]
        return rows

    def list_recent_events(
        self,
        *,
        event_class: str | None = None,
        player_guid: int | None = None,
        limit: int = 20,
        newest_first: bool = True,
    ):
        del limit
        rows = list(self.subject_events)
        if event_class is not None:
            rows = [event for event in rows if event.event_class == event_class]
        if player_guid is not None:
            rows = [event for event in rows if event.player_guid == player_guid]
        if newest_first:
            rows = list(reversed(rows))
        return rows


class FakeReactiveStore:
    def __init__(self) -> None:
        self.rules = []
        self.runtime_state = "none"
        self.snapshot = None

    def list_active_rules(self, *, subject_type=None, subject_entry=None, trigger_event_type=None, player_guid=None):
        rows = list(self.rules)
        if subject_type is not None:
            rows = [rule for rule in rows if rule.subject_type == subject_type]
        if subject_entry is not None:
            rows = [rule for rule in rows if rule.subject_entry == subject_entry]
        if trigger_event_type is not None:
            rows = [rule for rule in rows if rule.trigger_event_type == trigger_event_type]
        if player_guid is not None:
            rows = [rule for rule in rows if rule.player_guid_scope in (None, player_guid)]
        return rows

    def fetch_character_quest_status(self, *, player_guid: int, quest_id: int) -> str:
        del player_guid, quest_id
        return self.runtime_state

    def get_player_quest_runtime_state(self, *, player_guid: int, quest_id: int):
        del player_guid, quest_id
        return self.snapshot


class FakeAutoBountyManager:
    def __init__(self, reactive_store: FakeReactiveStore, rule: ReactiveQuestRule | None) -> None:
        self.reactive_store = reactive_store
        self.rule = rule
        self.calls: list[WMEvent] = []

    def ensure_rule_for_event(self, event: WMEvent) -> ReactiveQuestRule | None:
        self.calls.append(event)
        if self.rule is not None:
            self.reactive_store.rules = [self.rule]
        return self.rule


class DeterministicRuleEngineTests(unittest.TestCase):
    def _bundle(self, *, kill_count: int = 0, talk_count: int = 0) -> SubjectJournalBundle:
        return SubjectJournalBundle(
            subject_id=9001,
            subject_card=SubjectCard(subject_name="Murloc Forager", short_description="A shoreline pest."),
            counters=JournalCounters(kill_count=kill_count, talk_count=talk_count),
            events=[],
            summary=JournalSummary(
                title="Murloc Forager",
                description="A shoreline pest.",
                history_lines=["Player killed 10"],
                raw={"kill_count": kill_count, "talk_count": talk_count},
            ),
        )

    def test_auto_bounty_manager_is_not_created_by_default(self) -> None:
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(),
            store=FakeRuleStore(),
            reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
        )

        self.assertIsNone(engine.auto_bounty)

    def test_auto_bounty_manager_is_opt_in(self) -> None:
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(reactive_auto_bounty_enabled=True),
            store=FakeRuleStore(),
            reactive_store=FakeReactiveStore(),  # type: ignore[arg-type]
        )

        self.assertIsNotNone(engine.auto_bounty)

    def test_kill_threshold_emits_derived_events_and_opportunity(self) -> None:
        store = FakeRuleStore()
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=None,  # type: ignore[arg-type]
            store=store,
            repeat_kill_threshold=10,
        )
        event = WMEvent(
            event_id=5,
            event_class="observed",
            event_type="kill",
            source="db_poll",
            source_event_key="5",
            occurred_at="2026-04-08 12:00:00",
            player_guid=42,
            subject_type="creature",
            subject_entry=46,
        )

        with patch("wm.events.rules.load_subject_journal_for_creature", return_value=self._bundle(kill_count=10)):
            result = engine.evaluate(event)

        self.assertEqual({item.event_type for item in result.derived_events}, {"repeat_hunt_detected", "followup_eligible"})
        self.assertEqual(len(result.opportunities), 1)
        self.assertEqual(result.opportunities[0].rule_type, "repeat_hunt_followup")
        self.assertEqual(store.marked_evaluated, [5])

    def test_cooldown_suppresses_opportunity(self) -> None:
        store = FakeRuleStore()
        store.cooldown_active = True
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=None,  # type: ignore[arg-type]
            store=store,
            repeat_kill_threshold=10,
        )
        event = WMEvent(
            event_id=6,
            event_class="observed",
            event_type="kill",
            source="db_poll",
            source_event_key="6",
            occurred_at="2026-04-08 12:00:00",
            player_guid=42,
            subject_type="creature",
            subject_entry=46,
        )

        with patch("wm.events.rules.load_subject_journal_for_creature", return_value=self._bundle(kill_count=10)):
            result = engine.evaluate(event)

        self.assertEqual(len(result.derived_events), 2)
        self.assertEqual(result.opportunities, [])
        self.assertEqual(len(result.suppressed_opportunities), 1)
        self.assertEqual(result.suppressed_opportunities[0].metadata["suppression_reason"], "cooldown_active")

    def test_preview_does_not_mark_event_evaluated(self) -> None:
        store = FakeRuleStore()
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=None,  # type: ignore[arg-type]
            store=store,
            repeat_kill_threshold=10,
        )
        event = WMEvent(
            event_id=7,
            event_class="observed",
            event_type="kill",
            source="db_poll",
            source_event_key="7",
            occurred_at="2026-04-08 12:00:00",
            player_guid=42,
            subject_type="creature",
            subject_entry=46,
        )

        with patch("wm.events.rules.load_subject_journal_for_creature", return_value=self._bundle(kill_count=10)):
            result = engine.evaluate(event, preview=True)

        self.assertEqual(len(result.opportunities), 1)
        self.assertEqual(store.marked_evaluated, [])

    def test_kill_burst_rule_triggers_once_on_fourth_kill(self) -> None:
        store = FakeRuleStore()
        store.subject_events = [
            WMEvent(
                event_id=index,
                event_class="observed",
                event_type="kill",
                source="db_poll",
                source_event_key=str(index),
                occurred_at=f"2026-04-08 12:00:0{index}",
                player_guid=5406,
                subject_type="creature",
                subject_entry=6,
            )
            for index in range(1, 5)
        ]
        reactive_store = FakeReactiveStore()
        reactive_store.rules = [
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
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            reactive_store=reactive_store,  # type: ignore[arg-type]
        )
        event = store.subject_events[-1]

        result = engine.evaluate(event)

        self.assertEqual({item.event_type for item in result.derived_events}, {"kill_burst_detected"})
        self.assertEqual(len(result.opportunities), 1)
        self.assertEqual(result.opportunities[0].opportunity_type, "reactive_bounty_grant")
        self.assertEqual(result.opportunities[0].metadata["quest_id"], 910000)

    def test_kill_burst_fifth_kill_does_not_retrigger(self) -> None:
        store = FakeRuleStore()
        store.subject_events = [
            WMEvent(
                event_id=index,
                event_class="observed",
                event_type="kill",
                source="db_poll",
                source_event_key=str(index),
                occurred_at=f"2026-04-08 12:00:0{index}",
                player_guid=5406,
                subject_type="creature",
                subject_entry=6,
            )
            for index in range(1, 6)
        ]
        reactive_store = FakeReactiveStore()
        reactive_store.rules = [
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
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            reactive_store=reactive_store,  # type: ignore[arg-type]
        )

        result = engine.evaluate(store.subject_events[-1])

        self.assertEqual(result.opportunities, [])

    def test_reactive_rule_suppresses_active_and_rewarded_states(self) -> None:
        store = FakeRuleStore()
        store.subject_events = [
            WMEvent(
                event_id=index,
                event_class="observed",
                event_type="kill",
                source="db_poll",
                source_event_key=str(index),
                occurred_at=f"2026-04-08 12:00:0{index}",
                player_guid=5406,
                subject_type="creature",
                subject_entry=6,
            )
            for index in range(1, 5)
        ]
        reactive_store = FakeReactiveStore()
        reactive_store.rules = [
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
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            reactive_store=reactive_store,  # type: ignore[arg-type]
        )
        event = store.subject_events[-1]

        reactive_store.runtime_state = "incomplete"
        active_result = engine.evaluate(event, preview=True)
        self.assertEqual(active_result.opportunities, [])
        self.assertEqual(active_result.suppressed_opportunities[0].metadata["suppression_reason"], "quest_active")

        reactive_store.runtime_state = "complete"
        complete_result = engine.evaluate(event, preview=True)
        self.assertEqual(complete_result.suppressed_opportunities[0].metadata["suppression_reason"], "quest_complete_pending_turnin")

        reactive_store.runtime_state = "rewarded"
        reactive_store.snapshot = PlayerQuestRuntimeState(
            player_guid=5406,
            quest_id=910000,
            current_state="rewarded",
            last_transition_at="2026-04-08 12:00:05",
        )
        rewarded_result = engine.evaluate(event, preview=True)
        self.assertEqual(rewarded_result.suppressed_opportunities[0].metadata["suppression_reason"], "post_reward_cooldown_active")

    def test_rewarded_state_reopens_after_post_reward_cooldown_expires(self) -> None:
        store = FakeRuleStore()
        store.subject_events = [
            WMEvent(
                event_id=index,
                event_class="observed",
                event_type="kill",
                source="db_poll",
                source_event_key=str(index),
                occurred_at=f"2026-04-08 12:00:0{index}",
                player_guid=5406,
                subject_type="creature",
                subject_entry=6,
            )
            for index in range(1, 5)
        ]
        reactive_store = FakeReactiveStore()
        reactive_store.rules = [
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
        reactive_store.runtime_state = "rewarded"
        reactive_store.snapshot = PlayerQuestRuntimeState(
            player_guid=5406,
            quest_id=910000,
            current_state="rewarded",
            last_transition_at="2026-04-08 11:58:00",
        )
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            reactive_store=reactive_store,  # type: ignore[arg-type]
        )

        result = engine.evaluate(store.subject_events[-1], preview=True)

        self.assertEqual({item.event_type for item in result.derived_events}, {"kill_burst_detected"})
        self.assertEqual(len(result.suppressed_opportunities), 0)
        self.assertEqual(len(result.opportunities), 1)
        self.assertEqual(result.opportunities[0].metadata["runtime_state"], "rewarded")

    def test_derived_event_key_is_compacted_for_long_source_keys(self) -> None:
        store = FakeRuleStore()
        reactive_store = FakeReactiveStore()
        reactive_store.rules = [
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
        long_key = "combat_log:" + ("x" * 400)
        store.subject_events = [
            WMEvent(
                event_id=index,
                event_class="observed",
                event_type="kill",
                source="combat_log",
                source_event_key=f"{long_key}:{index}",
                occurred_at=f"2026-04-08 12:00:0{index}",
                player_guid=5406,
                subject_type="creature",
                subject_entry=6,
            )
            for index in range(1, 5)
        ]
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            reactive_store=reactive_store,  # type: ignore[arg-type]
        )

        result = engine.evaluate(store.subject_events[-1], preview=True)

        self.assertEqual(len(result.derived_events), 1)
        self.assertLessEqual(len(result.derived_events[0].source_event_key), 120)

    def test_auto_bounty_rule_is_attached_on_first_matching_kill(self) -> None:
        store = FakeRuleStore()
        store.subject_events = [
            WMEvent(
                event_id=index,
                event_class="observed",
                event_type="kill",
                source="native_bridge",
                source_event_key=f"native_bridge:{index}",
                occurred_at=f"2026-04-08 12:00:0{index}",
                player_guid=5406,
                subject_type="creature",
                subject_entry=116,
            )
            for index in range(1, 5)
        ]
        reactive_store = FakeReactiveStore()
        auto_rule = ReactiveQuestRule(
            rule_key="reactive_bounty:auto:defias_bandit",
            is_active=True,
            player_guid_scope=5406,
            subject_type="creature",
            subject_entry=116,
            trigger_event_type="kill",
            kill_threshold=4,
            window_seconds=120,
            quest_id=910000,
            turn_in_npc_entry=261,
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=60,
            metadata={"auto_bounty": True},
            notes=["auto_bounty"],
        )
        auto_bounty = FakeAutoBountyManager(reactive_store=reactive_store, rule=auto_rule)
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            reactive_store=reactive_store,  # type: ignore[arg-type]
            auto_bounty=auto_bounty,  # type: ignore[arg-type]
        )

        result = engine.evaluate(store.subject_events[-1])

        self.assertEqual(len(auto_bounty.calls), 1)
        self.assertEqual(result.opportunities[0].metadata["quest_id"], 910000)
        self.assertEqual(result.opportunities[0].metadata["turn_in_npc_entry"], 261)

    def test_defias_cutpurse_rule_triggers_from_exact_kills(self) -> None:
        store = FakeRuleStore()
        store.subject_events = [
            WMEvent(
                event_id=index,
                event_class="observed",
                event_type="kill",
                source="native_bridge",
                source_event_key=f"native_bridge:defias-cutpurse:{index}",
                occurred_at=f"2026-04-08 12:00:0{index}",
                player_guid=5406,
                subject_type="creature",
                subject_entry=94,
                metadata={"payload": {"subject_name": "Defias Cutpurse"}},
            )
            for index in range(1, 5)
        ]
        reactive_store = FakeReactiveStore()
        reactive_store.rules = [
            ReactiveQuestRule(
                rule_key="reactive_bounty:auto:defias:94",
                is_active=True,
                player_guid_scope=5406,
                subject_type="creature",
                subject_entry=94,
                trigger_event_type="kill",
                kill_threshold=4,
                window_seconds=120,
                quest_id=910001,
                turn_in_npc_entry=261,
                grant_mode="direct_quest_add",
                post_reward_cooldown_seconds=60,
                metadata={"auto_bounty": True, "auto_bounty_source_name_prefix": "Defias "},
                notes=["auto_bounty"],
            )
        ]
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            reactive_store=reactive_store,  # type: ignore[arg-type]
        )

        result = engine.evaluate(store.subject_events[-1])

        self.assertEqual(len(result.opportunities), 1)
        self.assertEqual(result.opportunities[0].metadata["quest_id"], 910001)

    def test_template_rule_can_match_by_subject_name_prefix(self) -> None:
        store = FakeRuleStore()
        store.subject_events = [
            WMEvent(
                event_id=index,
                event_class="observed",
                event_type="kill",
                source="native_bridge",
                source_event_key=f"native_bridge:murloc:{index}",
                occurred_at=f"2026-04-08 12:00:0{index}",
                player_guid=5406,
                subject_type="creature",
                subject_entry=285 + index,
                metadata={"payload": {"subject_name": "Murloc Coastrunner"}},
            )
            for index in range(1, 5)
        ]
        reactive_store = FakeReactiveStore()
        reactive_store.rules = [
            ReactiveQuestRule(
                rule_key="reactive_bounty:template:murloc",
                is_active=True,
                player_guid_scope=5406,
                subject_type="creature",
                subject_entry=0,
                trigger_event_type="kill",
                kill_threshold=4,
                window_seconds=120,
                quest_id=910021,
                turn_in_npc_entry=240,
                grant_mode="direct_quest_add",
                post_reward_cooldown_seconds=60,
                metadata={"subject_name_prefix": "Murloc"},
                notes=["template"],
            )
        ]
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            reactive_store=reactive_store,  # type: ignore[arg-type]
        )

        result = engine.evaluate(store.subject_events[-1])

        self.assertEqual(len(result.opportunities), 1)
        self.assertEqual(result.opportunities[0].metadata["quest_id"], 910021)

    def test_auto_bounty_can_replace_non_matching_exact_rule_with_defias_cutpurse_rule(self) -> None:
        store = FakeRuleStore()
        store.subject_events = [
            WMEvent(
                event_id=index,
                event_class="observed",
                event_type="kill",
                source="native_bridge",
                source_event_key=f"native_bridge:defias-cutpurse:{index}",
                occurred_at=f"2026-04-08 12:00:0{index}",
                player_guid=5406,
                subject_type="creature",
                subject_entry=94,
                metadata={"payload": {"subject_name": "Defias Cutpurse"}},
            )
            for index in range(1, 5)
        ]
        reactive_store = FakeReactiveStore()
        reactive_store.rules = [
            ReactiveQuestRule(
                rule_key="reactive_bounty:auto:defias_bandit",
                is_active=True,
                player_guid_scope=5406,
                subject_type="creature",
                subject_entry=116,
                trigger_event_type="kill",
                kill_threshold=4,
                window_seconds=120,
                quest_id=910000,
                turn_in_npc_entry=261,
                grant_mode="direct_quest_add",
                post_reward_cooldown_seconds=60,
                metadata={},
                notes=["auto_bounty"],
            )
        ]
        family_rule = ReactiveQuestRule(
            rule_key="reactive_bounty:auto:defias:94",
            is_active=True,
            player_guid_scope=5406,
            subject_type="creature",
            subject_entry=94,
            trigger_event_type="kill",
            kill_threshold=4,
            window_seconds=120,
            quest_id=910002,
            turn_in_npc_entry=261,
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=60,
            metadata={"auto_bounty": True, "auto_bounty_source_name_prefix": "Defias "},
            notes=["auto_bounty"],
        )
        auto_bounty = FakeAutoBountyManager(reactive_store=reactive_store, rule=family_rule)
        engine = DeterministicRuleEngine(
            client=_DummyClient(),
            settings=Settings(),
            store=store,
            reactive_store=reactive_store,  # type: ignore[arg-type]
            auto_bounty=auto_bounty,  # type: ignore[arg-type]
        )

        result = engine.evaluate(store.subject_events[-1])

        self.assertEqual(len(auto_bounty.calls), 1)
        self.assertEqual(len(result.opportunities), 1)
        self.assertEqual(result.opportunities[0].metadata["quest_id"], 910002)


if __name__ == "__main__":
    unittest.main()
