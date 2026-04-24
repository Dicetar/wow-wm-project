from __future__ import annotations

import unittest

from wm.config import Settings
from wm.events.models import WMEvent
from wm.reactive.random_enchant import RandomEnchantKillRoller
from wm.sources.native_bridge.actions import NativeBridgeActionRequest


class FakeEventStore:
    def __init__(self, events: list[WMEvent]) -> None:
        self.events = events

    def list_recent_events(self, **kwargs):  # type: ignore[no-untyped-def]
        self.kwargs = kwargs
        return list(reversed(self.events)) if kwargs.get("newest_first") else list(self.events)


class FakeNativeActions:
    def __init__(self) -> None:
        self.submitted: list[dict[str, object]] = []

    def submit(self, **kwargs):  # type: ignore[no-untyped-def]
        self.submitted.append(dict(kwargs))
        return NativeBridgeActionRequest(
            request_id=len(self.submitted),
            idempotency_key=str(kwargs["idempotency_key"]),
            player_guid=int(kwargs["player_guid"]),
            action_kind=str(kwargs["action_kind"]),
            payload=dict(kwargs["payload"]),
            status="pending",
            created_by=str(kwargs["created_by"]),
            risk_level=str(kwargs["risk_level"]),
        )


def _kill_event(event_id: int, source_key: str = "native:kill:1") -> WMEvent:
    return WMEvent(
        event_class="observed",
        event_type="kill",
        source="native_bridge",
        source_event_key=source_key,
        player_guid=5406,
        subject_type="creature",
        subject_entry=6,
        metadata={"subject_name": "Kobold Vermin"},
        event_id=event_id,
    )


class RandomEnchantKillRollerTests(unittest.TestCase):
    def test_dry_run_rolls_without_submitting_native_action(self) -> None:
        native = FakeNativeActions()
        roller = RandomEnchantKillRoller(
            settings=Settings(),
            event_store=FakeEventStore([_kill_event(10)]),  # type: ignore[arg-type]
            native_actions=native,  # type: ignore[arg-type]
        )

        results = roller.process_recent_kills(player_guid=5406, chance_pct=100.0, mode="dry-run")

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].selected)
        self.assertEqual(results[0].idempotency_key, "random_enchant_consumable:on_kill:5406:10")
        self.assertEqual(native.submitted, [])

    def test_apply_submits_idempotent_consumable_item_grant(self) -> None:
        native = FakeNativeActions()
        roller = RandomEnchantKillRoller(
            settings=Settings(),
            event_store=FakeEventStore([_kill_event(11, "native:kill:11")]),  # type: ignore[arg-type]
            native_actions=native,  # type: ignore[arg-type]
        )

        results = roller.process_recent_kills(
            player_guid=5406,
            chance_pct=100.0,
            preserve_existing_chance_pct=15.0,
            selector="random_equipped",
            max_enchants=3,
            mode="apply",
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].request_id, 1)
        self.assertEqual(native.submitted[0]["idempotency_key"], "random_enchant_consumable:on_kill:5406:11")
        self.assertEqual(native.submitted[0]["action_kind"], "player_add_item")
        self.assertEqual(native.submitted[0]["risk_level"], "medium")
        payload = native.submitted[0]["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["item_id"], 910007)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["reason"], "random_enchant_consumable_drop")
        self.assertEqual(payload["source_event_id"], 11)
        self.assertEqual(results[0].item_entry, 910007)
        self.assertEqual(results[0].count, 1)

    def test_zero_chance_never_submits(self) -> None:
        native = FakeNativeActions()
        roller = RandomEnchantKillRoller(
            settings=Settings(),
            event_store=FakeEventStore([_kill_event(12)]),  # type: ignore[arg-type]
            native_actions=native,  # type: ignore[arg-type]
        )

        results = roller.process_recent_kills(player_guid=5406, chance_pct=0.0, mode="apply")

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].selected)
        self.assertEqual(native.submitted, [])

    def test_process_events_filters_to_scoped_observed_kills(self) -> None:
        native = FakeNativeActions()
        foreign = _kill_event(20, "native:kill:foreign")
        foreign.player_guid = 9999
        non_kill = _kill_event(21, "native:quest:21")
        non_kill.event_type = "quest_granted"
        roller = RandomEnchantKillRoller(
            settings=Settings(),
            event_store=FakeEventStore([]),  # type: ignore[arg-type]
            native_actions=native,  # type: ignore[arg-type]
        )

        results = roller.process_events(
            events=[foreign, non_kill, _kill_event(22, "native:kill:22")],
            player_guid=5406,
            chance_pct=100.0,
            mode="apply",
        )

        self.assertEqual([result.event_id for result in results], [22])
        self.assertEqual(len(native.submitted), 1)
        self.assertEqual(native.submitted[0]["idempotency_key"], "random_enchant_consumable:on_kill:5406:22")


if __name__ == "__main__":
    unittest.main()
