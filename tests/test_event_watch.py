from __future__ import annotations

import unittest
from unittest.mock import patch

from wm.events.watch import _has_activity
from wm.events.watch import main


class _ArmBacklogStore:
    def __init__(self) -> None:
        self.max_calls: list[int | None] = []
        self.mark_calls: list[tuple[int | None, int | None]] = []

    def max_observed_event_id(self, *, player_guid: int | None = None) -> int:
        self.max_calls.append(player_guid)
        return 42

    def mark_unevaluated_observed_events_evaluated(
        self,
        *,
        player_guid: int | None = None,
        max_event_id: int | None = None,
    ) -> int:
        self.mark_calls.append((player_guid, max_event_id))
        return 3


class EventWatchTests(unittest.TestCase):
    def test_has_activity_detects_nonzero_counts(self) -> None:
        self.assertTrue(_has_activity({"execution_count": 1}))
        self.assertFalse(_has_activity({"execution_count": 0, "plan_count": 0}))

    def test_watch_runs_single_iteration(self) -> None:
        payload = {
            "adapter": "combat_log",
            "mode": "apply",
            "player_guid_filter": 5406,
            "questgiver_entry": 197,
            "polled_count": 0,
            "recorded_count": 0,
            "runtime_state_event_count": 0,
            "runtime_state_recorded_count": 0,
            "projected_count": 0,
            "derived_event_count": 0,
            "opportunity_count": 0,
            "plan_count": 0,
            "execution_count": 0,
            "executions": [],
        }

        with (
            patch("wm.events.watch.execute_event_spine", return_value=payload) as execute_mock,
            patch("wm.events.watch._emit_output") as emit_mock,
        ):
            result = main(
                [
                    "--adapter",
                    "combat_log",
                    "--mode",
                    "apply",
                    "--player-guid",
                    "5406",
                    "--confirm-live-apply",
                    "--summary",
                    "--max-iterations",
                    "1",
                ]
            )

        self.assertEqual(result, 0)
        execute_mock.assert_called_once()
        emit_mock.assert_not_called()

    def test_watch_can_arm_from_end_before_loop(self) -> None:
        payload = {
            "adapter": "combat_log",
            "mode": "apply",
            "player_guid_filter": 5406,
            "questgiver_entry": 197,
            "polled_count": 0,
            "recorded_count": 0,
            "runtime_state_event_count": 0,
            "runtime_state_recorded_count": 0,
            "projected_count": 0,
            "derived_event_count": 0,
            "opportunity_count": 0,
            "plan_count": 0,
            "execution_count": 0,
            "executions": [],
        }

        with (
            patch("wm.events.watch.EventStore"),
            patch("wm.events.watch.MysqlCliClient"),
            patch("wm.events.watch.arm_combat_log_cursor") as arm_mock,
            patch("wm.events.watch.execute_event_spine", return_value=payload),
            patch("wm.events.watch._emit_output"),
        ):
            arm_mock.return_value = type(
                "ArmResult",
                (),
                {"file_exists": True, "previous_offset": 10, "armed_offset": 20},
            )()
            result = main(
                [
                    "--adapter",
                    "combat_log",
                    "--mode",
                    "apply",
                    "--player-guid",
                    "5406",
                    "--confirm-live-apply",
                    "--max-iterations",
                    "1",
                    "--arm-from-end",
                ]
            )

        self.assertEqual(result, 0)
        arm_mock.assert_called_once()

    def test_watch_can_arm_addon_log_before_loop(self) -> None:
        payload = {
            "adapter": "addon_log",
            "mode": "apply",
            "player_guid_filter": 5406,
            "questgiver_entry": None,
            "polled_count": 0,
            "recorded_count": 0,
            "runtime_state_event_count": 0,
            "runtime_state_recorded_count": 0,
            "projected_count": 0,
            "derived_event_count": 0,
            "opportunity_count": 0,
            "plan_count": 0,
            "execution_count": 0,
            "executions": [],
        }

        with (
            patch("wm.events.watch.EventStore"),
            patch("wm.events.watch.MysqlCliClient"),
            patch("wm.events.watch.arm_addon_log_cursor") as arm_mock,
            patch("wm.events.watch.execute_event_spine", return_value=payload),
            patch("wm.events.watch._emit_output"),
        ):
            arm_mock.return_value = type(
                "ArmResult",
                (),
                {"file_exists": True, "previous_offset": 12, "armed_offset": 24},
            )()
            result = main(
                [
                    "--adapter",
                    "addon_log",
                    "--mode",
                    "apply",
                    "--player-guid",
                    "5406",
                    "--confirm-live-apply",
                    "--max-iterations",
                    "1",
                    "--arm-from-end",
                ]
            )

        self.assertEqual(result, 0)
        arm_mock.assert_called_once()

    def test_watch_can_arm_native_bridge_before_loop(self) -> None:
        payload = {
            "adapter": "native_bridge",
            "mode": "apply",
            "player_guid_filter": 5406,
            "questgiver_entry": None,
            "polled_count": 0,
            "recorded_count": 0,
            "runtime_state_event_count": 0,
            "runtime_state_recorded_count": 0,
            "projected_count": 0,
            "derived_event_count": 0,
            "opportunity_count": 0,
            "plan_count": 0,
            "execution_count": 0,
            "executions": [],
        }

        with (
            patch("wm.events.watch.EventStore"),
            patch("wm.events.watch.MysqlCliClient"),
            patch("wm.events.watch.arm_native_bridge_cursor") as arm_mock,
            patch("wm.events.watch.execute_event_spine", return_value=payload),
            patch("wm.events.watch._emit_output"),
        ):
            arm_mock.return_value = type(
                "ArmResult",
                (),
                {"table_exists": True, "player_guid": 5406, "previous_last_seen": 12, "armed_last_seen": 24},
            )()
            result = main(
                [
                    "--adapter",
                    "native_bridge",
                    "--mode",
                    "apply",
                    "--player-guid",
                    "5406",
                    "--confirm-live-apply",
                    "--max-iterations",
                    "1",
                    "--arm-from-end",
                ]
            )

        self.assertEqual(result, 0)
        arm_mock.assert_called_once()

    def test_watch_can_mark_existing_backlog_evaluated_when_arming(self) -> None:
        payload = {
            "adapter": "native_bridge",
            "mode": "apply",
            "player_guid_filter": 5406,
            "questgiver_entry": None,
            "polled_count": 0,
            "recorded_count": 0,
            "runtime_state_event_count": 0,
            "runtime_state_recorded_count": 0,
            "projected_count": 0,
            "derived_event_count": 0,
            "opportunity_count": 0,
            "plan_count": 0,
            "execution_count": 0,
            "executions": [],
        }
        store = _ArmBacklogStore()

        with (
            patch("wm.events.watch.EventStore", return_value=store),
            patch("wm.events.watch.MysqlCliClient"),
            patch("wm.events.watch.arm_native_bridge_cursor") as arm_mock,
            patch("wm.events.watch.execute_event_spine", return_value=payload),
            patch("wm.events.watch._emit_output"),
        ):
            arm_mock.return_value = type(
                "ArmResult",
                (),
                {"table_exists": True, "player_guid": 5406, "previous_last_seen": 12, "armed_last_seen": 24},
            )()
            result = main(
                [
                    "--adapter",
                    "native_bridge",
                    "--mode",
                    "apply",
                    "--player-guid",
                    "5406",
                    "--confirm-live-apply",
                    "--max-iterations",
                    "1",
                    "--arm-from-end",
                    "--mark-existing-evaluated-on-arm",
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(store.max_calls, [5406])
        self.assertEqual(store.mark_calls, [(5406, 42)])

    def test_watch_rejects_backlog_mark_without_arm_from_end(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main(
                [
                    "--adapter",
                    "native_bridge",
                    "--mode",
                    "apply",
                    "--player-guid",
                    "5406",
                    "--confirm-live-apply",
                    "--max-iterations",
                    "1",
                    "--mark-existing-evaluated-on-arm",
                ]
            )

        self.assertIn("--arm-from-end", str(ctx.exception))

    def test_watch_prints_when_activity_present(self) -> None:
        payload = {
            "adapter": "combat_log",
            "mode": "apply",
            "player_guid_filter": 5406,
            "questgiver_entry": 197,
            "polled_count": 4,
            "recorded_count": 4,
            "runtime_state_event_count": 0,
            "runtime_state_recorded_count": 0,
            "projected_count": 4,
            "derived_event_count": 1,
            "opportunity_count": 1,
            "plan_count": 1,
            "execution_count": 1,
            "executions": [],
        }

        with (
            patch("wm.events.watch.execute_event_spine", return_value=payload),
            patch("wm.events.watch._emit_output") as emit_mock,
        ):
            result = main(
                [
                    "--adapter",
                    "combat_log",
                    "--mode",
                    "apply",
                    "--player-guid",
                    "5406",
                    "--confirm-live-apply",
                    "--summary",
                    "--max-iterations",
                    "1",
                ]
            )

        self.assertEqual(result, 0)
        emit_mock.assert_called_once()

    def test_watch_continues_after_iteration_error(self) -> None:
        failure = SystemExit("Apply mode produced 2 plans. Narrow the run.")
        payload = {
            "adapter": "native_bridge",
            "mode": "apply",
            "player_guid_filter": 5406,
            "questgiver_entry": None,
            "polled_count": 4,
            "recorded_count": 4,
            "runtime_state_event_count": 0,
            "runtime_state_recorded_count": 0,
            "projected_count": 4,
            "derived_event_count": 1,
            "opportunity_count": 1,
            "plan_count": 1,
            "execution_count": 1,
            "executions": [],
        }

        with (
            patch("wm.events.watch.execute_event_spine", side_effect=[failure, payload]) as execute_mock,
            patch("wm.events.watch._emit_output") as emit_mock,
            patch("wm.events.watch._emit_watch_iteration_error") as error_mock,
            patch("wm.events.watch.time.sleep"),
        ):
            result = main(
                [
                    "--adapter",
                    "native_bridge",
                    "--mode",
                    "apply",
                    "--player-guid",
                    "5406",
                    "--confirm-live-apply",
                    "--summary",
                    "--max-iterations",
                    "2",
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(execute_mock.call_count, 2)
        error_mock.assert_called_once()
        emit_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
