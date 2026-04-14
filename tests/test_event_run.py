from argparse import Namespace
import unittest
from unittest.mock import patch

from wm.config import Settings
from wm.events.models import ExecutionResult
from wm.events.models import ExecutionStepResult
from wm.events.models import PlannedAction
from wm.events.models import ProjectionResult
from wm.events.models import ReactionOpportunity
from wm.events.models import ReactionPlan
from wm.events.models import RecordResult
from wm.events.models import RuleEvaluationResult
from wm.events.models import SubjectRef
from wm.events.models import WMEvent
from wm.events.run import _apply_settings_overrides
from wm.events.run import _validate_apply_plan_scope
from wm.events.run import _validate_run_arguments
from wm.events.run import execute_event_spine


class _DummyClient:
    mysql_bin_path = "mysql"


class FakeSpineStore:
    def __init__(self) -> None:
        self.recorded_batches: list[list[WMEvent]] = []
        self.cursor_updates: list[tuple[str, str, str]] = []
        self.marked_evaluated: list[int] = []
        self._observed_events: list[WMEvent] = []
        self._next_event_id = 1

    def record(self, events: list[WMEvent]) -> RecordResult:
        recorded: list[WMEvent] = []
        for event in events:
            if event.event_id is None:
                event.event_id = self._next_event_id
                self._next_event_id += 1
            if event.event_class == "observed":
                self._observed_events.append(event)
            recorded.append(event)
        self.recorded_batches.append(list(recorded))
        return RecordResult(recorded=recorded)

    def set_cursor(self, *, adapter_name: str, cursor_key: str = "last_seen", cursor_value: str) -> None:
        self.cursor_updates.append((adapter_name, cursor_key, cursor_value))

    def list_unprojected_observed_events(self, *, limit: int = 100) -> list[WMEvent]:
        return list(self._observed_events[:limit])

    def list_unevaluated_observed_events(self, *, limit: int = 100) -> list[WMEvent]:
        return [event for event in self._observed_events if event.event_id not in self.marked_evaluated][:limit]

    def mark_evaluated(self, *, event_id: int) -> None:
        self.marked_evaluated.append(event_id)


class FakeAdapter:
    name = "native_bridge"
    cursor_key = "last_seen"

    def __init__(self, events: list[WMEvent], *, cursor_value: str = "44") -> None:
        self._events = list(events)
        self.last_cursor_value = cursor_value

    def poll(self) -> list[WMEvent]:
        return list(self._events)


class FakeProjector:
    def __init__(self) -> None:
        self.calls: list[int | None] = []

    def apply(self, event: WMEvent) -> ProjectionResult:
        self.calls.append(event.event_id)
        return ProjectionResult(event_id=event.event_id, status="projected", subject_id=1)


class FakeRuntimeSyncResult:
    def __init__(self, event: WMEvent) -> None:
        self.checked_rules = 1
        self.observed_transitions = [event]


class FakeRuntimeSynchronizer:
    def __init__(self, event: WMEvent) -> None:
        self.event = event
        self.calls: list[tuple[int | None, bool]] = []

    def poll(self, *, player_guid: int | None = None, preview: bool = False) -> FakeRuntimeSyncResult:
        self.calls.append((player_guid, preview))
        return FakeRuntimeSyncResult(self.event)


class FakeRuleEngine:
    def __init__(self, *, derived_event: WMEvent, opportunity: ReactionOpportunity) -> None:
        self.derived_event = derived_event
        self.opportunity = opportunity
        self.calls: list[tuple[str, bool, bool]] = []

    def _evaluate(self, event: WMEvent, *, preview: bool = False, mark_evaluated: bool = False) -> RuleEvaluationResult:
        self.calls.append((event.event_type, preview, mark_evaluated))
        if event.event_type == "kill":
            return RuleEvaluationResult(
                derived_events=[self.derived_event],
                opportunities=[self.opportunity],
            )
        return RuleEvaluationResult()


class FakePlanner:
    def __init__(self, plan: ReactionPlan) -> None:
        self.planned_reaction = plan
        self.calls: list[ReactionOpportunity] = []

    def plan(self, opportunity: ReactionOpportunity) -> ReactionPlan:
        self.calls.append(opportunity)
        return self.planned_reaction


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[ReactionPlan, str]] = []

    def execute(self, *, plan: ReactionPlan, mode: str) -> ExecutionResult:
        self.calls.append((plan, mode))
        return ExecutionResult(
            mode=mode,
            plan=plan,
            status="applied",
            steps=[
                ExecutionStepResult(
                    kind="quest_grant",
                    status="applied",
                    details={"selected_transport": "native_bridge"},
                )
            ],
        )


class EventRunValidationTests(unittest.TestCase):
    def test_apply_settings_overrides_questgiver(self) -> None:
        settings = Settings()
        args = Namespace(questgiver_entry=197)

        _apply_settings_overrides(args=args, settings=settings)

        self.assertEqual(settings.event_default_questgiver_entry, 197)

    def test_dry_run_does_not_require_confirmation(self) -> None:
        settings = Settings()
        args = Namespace(mode="dry-run", confirm_live_apply=False, player_guid=None)

        _validate_run_arguments(args=args, settings=settings)

    def test_apply_requires_confirmation(self) -> None:
        settings = Settings(event_default_questgiver_entry=197)
        args = Namespace(mode="apply", confirm_live_apply=False, player_guid=5406, adapter="db")

        with self.assertRaises(SystemExit) as ctx:
            _validate_run_arguments(args=args, settings=settings)

        self.assertIn("--confirm-live-apply", str(ctx.exception))

    def test_apply_requires_player_guid(self) -> None:
        settings = Settings(event_default_questgiver_entry=197)
        args = Namespace(mode="apply", confirm_live_apply=True, player_guid=None, adapter="db")

        with self.assertRaises(SystemExit) as ctx:
            _validate_run_arguments(args=args, settings=settings)

        self.assertIn("--player-guid", str(ctx.exception))

    def test_apply_does_not_require_questgiver_for_reactive_flows(self) -> None:
        settings = Settings()
        args = Namespace(mode="apply", confirm_live_apply=True, player_guid=5406, adapter="db")

        _validate_run_arguments(args=args, settings=settings)

    def test_combat_log_requires_player_guid_even_for_dry_run(self) -> None:
        settings = Settings()
        args = Namespace(mode="dry-run", confirm_live_apply=False, player_guid=None, adapter="combat_log")

        with self.assertRaises(SystemExit) as ctx:
            _validate_run_arguments(args=args, settings=settings)

        self.assertIn("Combat log runs require --player-guid", str(ctx.exception))

    def test_addon_log_requires_player_guid_even_for_dry_run(self) -> None:
        settings = Settings()
        args = Namespace(mode="dry-run", confirm_live_apply=False, player_guid=None, adapter="addon_log")

        with self.assertRaises(SystemExit) as ctx:
            _validate_run_arguments(args=args, settings=settings)

        self.assertIn("Addon log runs require --player-guid", str(ctx.exception))

    def test_native_bridge_requires_player_guid_even_for_dry_run(self) -> None:
        settings = Settings()
        args = Namespace(mode="dry-run", confirm_live_apply=False, player_guid=None, adapter="native_bridge")

        with self.assertRaises(SystemExit) as ctx:
            _validate_run_arguments(args=args, settings=settings)

        self.assertIn("Native bridge runs require --player-guid", str(ctx.exception))

    def test_apply_allows_single_scoped_plan(self) -> None:
        plan = ReactionPlan(
            plan_key="repeat_hunt_followup:5406:creature:6",
            opportunity_type="repeat_hunt_followup",
            rule_type="repeat_hunt_followup",
            player_guid=5406,
            subject=SubjectRef(subject_type="creature", subject_entry=6),
        )

        _validate_apply_plan_scope(mode="apply", plans=[plan])

    def test_apply_rejects_multiple_plans(self) -> None:
        plans = [
            ReactionPlan(
                plan_key=f"repeat_hunt_followup:5406:creature:{entry}",
                opportunity_type="repeat_hunt_followup",
                rule_type="repeat_hunt_followup",
                player_guid=5406,
                subject=SubjectRef(subject_type="creature", subject_entry=entry),
            )
            for entry in (6, 299)
        ]

        with self.assertRaises(SystemExit) as ctx:
            _validate_apply_plan_scope(mode="apply", plans=plans)

        self.assertIn("produced 2 plans", str(ctx.exception))

    def test_execute_event_spine_runs_native_bounty_flow_through_native_grant(self) -> None:
        observed_kill = WMEvent(
            event_class="observed",
            event_type="kill",
            source="native_bridge",
            source_event_key="native_bridge:101",
            occurred_at="2026-04-13 10:00:00",
            player_guid=5406,
            subject_type="creature",
            subject_entry=6,
        )
        runtime_transition = WMEvent(
            event_class="observed",
            event_type="quest_granted",
            source="quest_state_poll",
            source_event_key="5406:910000:quest_granted:2026-04-13T10:00:01Z",
            occurred_at="2026-04-13 10:00:01",
            player_guid=5406,
            subject_type="creature",
            subject_entry=6,
            event_value="910000",
            metadata={"quest_id": 910000},
        )
        derived_event = WMEvent(
            event_class="derived",
            event_type="kill_burst_detected",
            source="wm.rules",
            source_event_key="native_bridge:native_bridge:101:kill_burst_detected",
            occurred_at="2026-04-13 10:00:00",
            player_guid=5406,
            subject_type="creature",
            subject_entry=6,
            metadata={"quest_id": 910000},
        )
        opportunity = ReactionOpportunity(
            opportunity_type="reactive_bounty_grant",
            rule_type="reactive_bounty:kobold_vermin",
            player_guid=5406,
            subject=SubjectRef(subject_type="creature", subject_entry=6),
            source_event_key=observed_kill.source_event_key,
            metadata={"quest_id": 910000},
        )
        plan = ReactionPlan(
            plan_key="reactive_bounty:kobold_vermin:5406:creature:6",
            opportunity_type="reactive_bounty_grant",
            rule_type="reactive_bounty:kobold_vermin",
            player_guid=5406,
            subject=SubjectRef(subject_type="creature", subject_entry=6),
            actions=[
                PlannedAction(
                    kind="quest_grant",
                    payload={"quest_id": 910000, "player_guid": 5406},
                )
            ],
        )

        store = FakeSpineStore()
        adapter = FakeAdapter([observed_kill])
        projector = FakeProjector()
        runtime_synchronizer = FakeRuntimeSynchronizer(runtime_transition)
        engine = FakeRuleEngine(derived_event=derived_event, opportunity=opportunity)
        planner = FakePlanner(plan)
        executor = FakeExecutor()

        with (
            patch("wm.events.run.MysqlCliClient", return_value=_DummyClient()),
            patch("wm.events.run.EventStore", return_value=store),
            patch("wm.events.run.ReactiveQuestStore", return_value=object()),
            patch("wm.events.run.build_event_adapter", return_value=adapter),
            patch("wm.events.run.JournalProjector", return_value=projector),
            patch("wm.events.run.ReactiveQuestRuntimeSynchronizer", return_value=runtime_synchronizer),
            patch("wm.events.run.DeterministicRuleEngine", return_value=engine),
            patch("wm.events.run.DeterministicContentFactory", return_value=object()),
            patch("wm.events.run.DeterministicReactionPlanner", return_value=planner),
            patch("wm.events.run.ReactionExecutor", return_value=executor),
        ):
            payload = execute_event_spine(
                settings=Settings(),
                adapter_name="native_bridge",
                mode="apply",
                player_guid=5406,
                batch_size=25,
            )

        self.assertEqual(payload["adapter"], "native_bridge")
        self.assertEqual(payload["mode"], "apply")
        self.assertEqual(payload["polled_count"], 1)
        self.assertEqual(payload["recorded_count"], 1)
        self.assertEqual(payload["runtime_state_event_count"], 1)
        self.assertEqual(payload["runtime_state_recorded_count"], 1)
        self.assertEqual(payload["projected_count"], 2)
        self.assertEqual(payload["derived_event_count"], 1)
        self.assertEqual(payload["opportunity_count"], 1)
        self.assertEqual(payload["plan_count"], 1)
        self.assertEqual(payload["execution_count"], 1)
        self.assertEqual(payload["executions"][0]["steps"][0]["details"]["selected_transport"], "native_bridge")
        self.assertEqual(store.cursor_updates, [("native_bridge", "last_seen", "44")])
        self.assertEqual(runtime_synchronizer.calls, [(5406, False)])
        self.assertEqual(engine.calls, [("kill", False, False), ("quest_granted", False, False)])
        self.assertEqual(len(planner.calls), 1)
        self.assertEqual(executor.calls[0][1], "apply")
        self.assertEqual([event.event_id for event in store.recorded_batches[0]], [1])
        self.assertEqual([event.event_id for event in store.recorded_batches[1]], [2])
        self.assertEqual([event.event_type for event in store.recorded_batches[2]], ["kill_burst_detected"])
        self.assertEqual(store.marked_evaluated, [1, 2])
        self.assertEqual(projector.calls, [1, 2])

    def test_execute_event_spine_leaves_events_unevaluated_when_apply_scope_validation_fails(self) -> None:
        observed_kills = [
            WMEvent(
                event_class="observed",
                event_type="kill",
                source="native_bridge",
                source_event_key=f"native_bridge:{event_id}",
                occurred_at=f"2026-04-13 10:00:0{event_id}",
                player_guid=5406,
                subject_type="creature",
                subject_entry=6,
            )
            for event_id in (101, 102)
        ]
        runtime_transition = WMEvent(
            event_class="observed",
            event_type="quest_granted",
            source="quest_state_poll",
            source_event_key="5406:910000:quest_granted:2026-04-13T10:00:01Z",
            occurred_at="2026-04-13 10:00:01",
            player_guid=5406,
            subject_type="creature",
            subject_entry=6,
            event_value="910000",
            metadata={"quest_id": 910000},
        )
        derived_event = WMEvent(
            event_class="derived",
            event_type="kill_burst_detected",
            source="wm.rules",
            source_event_key="native_bridge:native_bridge:101:kill_burst_detected",
            occurred_at="2026-04-13 10:00:00",
            player_guid=5406,
            subject_type="creature",
            subject_entry=6,
            metadata={"quest_id": 910000},
        )
        opportunity = ReactionOpportunity(
            opportunity_type="reactive_bounty_grant",
            rule_type="reactive_bounty:kobold_vermin",
            player_guid=5406,
            subject=SubjectRef(subject_type="creature", subject_entry=6),
            source_event_key=observed_kills[0].source_event_key,
            metadata={"quest_id": 910000},
        )
        plan = ReactionPlan(
            plan_key="reactive_bounty:kobold_vermin:5406:creature:6",
            opportunity_type="reactive_bounty_grant",
            rule_type="reactive_bounty:kobold_vermin",
            player_guid=5406,
            subject=SubjectRef(subject_type="creature", subject_entry=6),
            actions=[
                PlannedAction(
                    kind="quest_grant",
                    payload={"quest_id": 910000, "player_guid": 5406},
                )
            ],
        )

        store = FakeSpineStore()
        adapter = FakeAdapter(observed_kills)
        projector = FakeProjector()
        runtime_synchronizer = FakeRuntimeSynchronizer(runtime_transition)
        engine = FakeRuleEngine(derived_event=derived_event, opportunity=opportunity)
        planner = FakePlanner(plan)
        executor = FakeExecutor()

        with (
            patch("wm.events.run.MysqlCliClient", return_value=_DummyClient()),
            patch("wm.events.run.EventStore", return_value=store),
            patch("wm.events.run.ReactiveQuestStore", return_value=object()),
            patch("wm.events.run.build_event_adapter", return_value=adapter),
            patch("wm.events.run.JournalProjector", return_value=projector),
            patch("wm.events.run.ReactiveQuestRuntimeSynchronizer", return_value=runtime_synchronizer),
            patch("wm.events.run.DeterministicRuleEngine", return_value=engine),
            patch("wm.events.run.DeterministicContentFactory", return_value=object()),
            patch("wm.events.run.DeterministicReactionPlanner", return_value=planner),
            patch("wm.events.run.ReactionExecutor", return_value=executor),
        ):
            with self.assertRaises(SystemExit) as ctx:
                execute_event_spine(
                    settings=Settings(),
                    adapter_name="native_bridge",
                    mode="apply",
                    player_guid=5406,
                    batch_size=25,
                )

        self.assertIn("produced 2 plans", str(ctx.exception))
        self.assertEqual(store.marked_evaluated, [])
        self.assertEqual(executor.calls, [])


if __name__ == "__main__":
    unittest.main()
