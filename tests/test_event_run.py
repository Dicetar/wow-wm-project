from argparse import Namespace
import unittest

from wm.config import Settings
from wm.events.models import ReactionPlan
from wm.events.models import SubjectRef
from wm.events.run import _apply_settings_overrides
from wm.events.run import _validate_apply_plan_scope
from wm.events.run import _validate_run_arguments


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


if __name__ == "__main__":
    unittest.main()
