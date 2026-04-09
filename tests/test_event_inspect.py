import unittest

from wm.events.inspect import build_inspect_payload
from wm.events.models import ReactionCooldownRecord
from wm.events.models import ReactionLogRecord
from wm.events.models import SubjectRef
from wm.events.models import WMEvent


class FakeInspectStore:
    def list_recent_events(self, *, event_class: str | None = None, player_guid: int | None = None, limit: int = 20, newest_first: bool = True):
        del player_guid, limit, newest_first
        if event_class == "observed":
            return [
                WMEvent(
                    event_id=11,
                    event_class="observed",
                    event_type="kill",
                    source="db_poll",
                    source_event_key="11",
                    occurred_at="2026-04-08 10:01:00",
                    player_guid=5406,
                    subject_type="creature",
                    subject_entry=6,
                ),
                WMEvent(
                    event_id=10,
                    event_class="observed",
                    event_type="kill",
                    source="db_poll",
                    source_event_key="10",
                    occurred_at="2026-04-08 10:00:00",
                    player_guid=5406,
                    subject_type="creature",
                    subject_entry=6,
                ),
            ]
        if event_class == "derived":
            return [
                WMEvent(
                    event_id=12,
                    event_class="derived",
                    event_type="repeat_hunt_detected",
                    source="wm.rules",
                    source_event_key="12",
                    occurred_at="2026-04-08 10:01:00",
                    player_guid=5406,
                    subject_type="creature",
                    subject_entry=6,
                )
            ]
        if event_class == "action":
            return [
                WMEvent(
                    event_id=13,
                    event_class="action",
                    event_type="reaction_planned",
                    source="wm.executor",
                    source_event_key="13",
                    occurred_at="2026-04-08 10:01:00",
                    player_guid=5406,
                    subject_type="creature",
                    subject_entry=6,
                )
            ]
        return []

    def list_recent_reaction_logs(self, *, player_guid: int | None = None, status: str | None = None, limit: int = 20):
        del player_guid, status, limit
        return [
            ReactionLogRecord(
                reaction_id=1,
                reaction_key="repeat_hunt_followup:5406:creature:6",
                rule_type="repeat_hunt_followup",
                status="dry-run",
                player_guid=5406,
                subject=SubjectRef(subject_type="creature", subject_entry=6),
                planned_actions={"plan_key": "repeat_hunt_followup:5406:creature:6"},
                result={"status": "dry-run"},
                created_at="2026-04-08 10:01:30",
            )
        ]

    def list_active_cooldowns(self, *, player_guid: int | None = None, limit: int = 20, at: str | None = None):
        del player_guid, limit, at
        return [
            ReactionCooldownRecord(
                reaction_key="repeat_hunt_followup:5406:creature:6",
                rule_type="repeat_hunt_followup",
                player_guid=5406,
                subject=SubjectRef(subject_type="creature", subject_entry=6),
                cooldown_until="2026-04-08 11:01:30",
                last_triggered_at="2026-04-08 10:01:30",
                metadata={"plan_key": "repeat_hunt_followup:5406:creature:6"},
            )
        ]


class InspectCommandTests(unittest.TestCase):
    def test_build_inspect_payload_groups_recent_state(self) -> None:
        payload = build_inspect_payload(store=FakeInspectStore(), player_guid=5406, limit=5)

        counts = payload["counts"]
        self.assertEqual(counts["observed"], 2)
        self.assertEqual(counts["derived"], 1)
        self.assertEqual(counts["action"], 1)
        self.assertEqual(counts["reaction_logs"], 1)
        self.assertEqual(counts["active_cooldowns"], 1)
        observed = payload["events"]["observed"]
        self.assertEqual(observed[0]["event_id"], 11)
        self.assertEqual(observed[1]["event_id"], 10)


if __name__ == "__main__":
    unittest.main()
