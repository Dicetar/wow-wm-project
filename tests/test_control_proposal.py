import unittest
from datetime import datetime
from datetime import timezone

from pydantic import ValidationError

from wm.control.builder import build_manual_proposal
from wm.control.models import ControlAuthor
from wm.control.registry import ControlRegistry
from wm.control.validator import validate_control_proposal
from wm.events.models import WMEvent


FRESH_NOW = datetime(2026, 4, 10, 12, 5, tzinfo=timezone.utc)
STALE_NOW = datetime(2026, 4, 10, 12, 11, tzinfo=timezone.utc)


def _event(*, event_type: str = "kill", player_guid: int = 5406) -> WMEvent:
    return WMEvent(
        event_id=12,
        event_class="observed",
        event_type=event_type,
        source="native_bridge",
        source_event_key="native_bridge:12",
        occurred_at="2026-04-10 12:00:00",
        player_guid=player_guid,
        subject_type="creature",
        subject_entry=6,
    )


class ControlProposalTests(unittest.TestCase):
    def test_manual_builder_creates_valid_bounty_grant(self) -> None:
        registry = ControlRegistry.load("control")
        proposal = build_manual_proposal(
            event=_event(),
            registry=registry,
            recipe_id="kill_burst_bounty",
            action_kind="quest_grant",
        )

        result = validate_control_proposal(proposal=proposal, registry=registry, source_event=_event(), now=FRESH_NOW)

        self.assertTrue(result.ok, [issue.message for issue in result.issues])
        self.assertEqual(proposal.action.payload["quest_id"], 910000)
        self.assertEqual(proposal.action.payload["player_guid"], 5406)
        self.assertIn("kill_burst_bounty", proposal.idempotency_key)

    def test_player_mismatch_is_rejected(self) -> None:
        registry = ControlRegistry.load("control")
        proposal = build_manual_proposal(
            event=_event(player_guid=5406),
            registry=registry,
            recipe_id="kill_burst_bounty",
            action_kind="quest_grant",
            payload_overrides={"player_guid": 1111},
        )

        result = validate_control_proposal(
            proposal=proposal,
            registry=registry,
            source_event=_event(player_guid=5406),
            now=FRESH_NOW,
        )

        self.assertFalse(result.ok)
        self.assertTrue(any(issue.path == "player.guid" for issue in result.issues))

    def test_recipe_that_is_not_live_enabled_is_rejected_for_control_apply(self) -> None:
        registry = ControlRegistry.load("control")
        proposal = build_manual_proposal(
            event=_event(event_type="enter_area"),
            registry=registry,
            recipe_id="area_entry_prompt",
            action_kind="noop",
        )

        result = validate_control_proposal(
            proposal=proposal,
            registry=registry,
            source_event=_event(event_type="enter_area"),
            now=FRESH_NOW,
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("not live-enabled" in issue.message for issue in result.issues))

    def test_stale_source_event_is_rejected(self) -> None:
        registry = ControlRegistry.load("control")
        event = _event()
        proposal = build_manual_proposal(
            event=event,
            registry=registry,
            recipe_id="kill_burst_bounty",
            action_kind="quest_grant",
        )

        result = validate_control_proposal(proposal=proposal, registry=registry, source_event=event, now=STALE_NOW)

        self.assertFalse(result.ok)
        self.assertTrue(any(issue.path == "source_event.occurred_at" for issue in result.issues))

    def test_manual_admin_author_requires_reason(self) -> None:
        with self.assertRaises(ValidationError):
            ControlAuthor(kind="manual_admin")


if __name__ == "__main__":
    unittest.main()
