import unittest

from wm.events.models import ExecutionResult
from wm.events.models import ExecutionStepResult
from wm.events.models import PlannedAction
from wm.events.models import ReactionOpportunity
from wm.events.models import ReactionPlan
from wm.events.models import RuleEvaluationResult
from wm.events.models import SubjectRef
from wm.events.models import WMEvent
from wm.events.plan import build_plan_payload


class FakePlanStore:
    def __init__(self) -> None:
        self.list_calls = 0

    def list_recent_events(self, *, event_class: str | None = None, player_guid: int | None = None, limit: int = 20, newest_first: bool = True):
        self.list_calls += 1
        self.last_args = (event_class, player_guid, limit, newest_first)
        return [
            WMEvent(
                event_id=21,
                event_class="observed",
                event_type="kill",
                source="db_poll",
                source_event_key="21",
                occurred_at="2026-04-08 10:05:00",
                player_guid=5406,
                subject_type="creature",
                subject_entry=6,
            )
        ]


class FakePreviewEngine:
    def __init__(self) -> None:
        self.preview_flags: list[bool] = []

    def evaluate(self, event: WMEvent, *, preview: bool = False) -> RuleEvaluationResult:
        del event
        self.preview_flags.append(preview)
        return RuleEvaluationResult(
            derived_events=[
                WMEvent(
                    event_class="derived",
                    event_type="repeat_hunt_detected",
                    source="wm.rules",
                    source_event_key="derived:21:repeat_hunt_detected",
                    occurred_at="2026-04-08 10:05:00",
                    player_guid=5406,
                    subject_type="creature",
                    subject_entry=6,
                )
            ],
            opportunities=[
                ReactionOpportunity(
                    opportunity_type="repeat_hunt_followup",
                    rule_type="repeat_hunt_followup",
                    player_guid=5406,
                    subject=SubjectRef(subject_type="creature", subject_entry=6),
                    source_event_key="21",
                    metadata={"subject_name": "Kobold Vermin"},
                    cooldown_seconds=3600,
                )
            ],
        )


class FakePreviewPlanner:
    def plan(self, opportunity: ReactionOpportunity) -> ReactionPlan:
        del opportunity
        return ReactionPlan(
            plan_key="repeat_hunt_followup:5406:creature:6",
            opportunity_type="repeat_hunt_followup",
            rule_type="repeat_hunt_followup",
            player_guid=5406,
            subject=SubjectRef(subject_type="creature", subject_entry=6),
            actions=[
                PlannedAction(
                    kind="quest_publish",
                    payload={"quest_id": 910000, "title": "Bounty: Kobold Vermin"},
                )
            ],
        )


class FakePreviewExecutor:
    def __init__(self) -> None:
        self.previewed_plans: list[str] = []

    def preview(self, *, plan: ReactionPlan) -> ExecutionResult:
        self.previewed_plans.append(plan.plan_key)
        return ExecutionResult(
            mode="preview",
            plan=plan,
            status="preview",
            steps=[
                ExecutionStepResult(
                    kind="quest_publish",
                    status="dry-run",
                    details={
                        "draft": {"quest_id": 910000, "title": "Bounty: Kobold Vermin"},
                        "preflight": {"ok": False},
                        "dry_run_ready": True,
                        "dry_run_notes": [
                            "Reserved slot is still `free` during dry-run and would be staged automatically immediately before apply."
                        ],
                    },
                )
            ],
        )


class PlanCommandTests(unittest.TestCase):
    def test_build_plan_payload_previews_repeat_hunt_plan_without_mutation(self) -> None:
        store = FakePlanStore()
        engine = FakePreviewEngine()
        planner = FakePreviewPlanner()
        executor = FakePreviewExecutor()

        payload = build_plan_payload(
            store=store,
            engine=engine,
            planner=planner,
            executor=executor,
            player_guid=5406,
            limit=5,
            questgiver_entry=197,
        )

        self.assertEqual(payload["mode"], "preview")
        self.assertEqual(payload["player_guid_filter"], 5406)
        self.assertEqual(payload["questgiver_entry"], 197)
        self.assertEqual(payload["event_count"], 1)
        self.assertEqual(payload["derived_event_count"], 1)
        self.assertEqual(payload["opportunity_count"], 1)
        self.assertEqual(payload["plan_count"], 1)
        self.assertEqual(payload["preview_count"], 1)
        self.assertEqual(engine.preview_flags, [True])
        self.assertEqual(executor.previewed_plans, ["repeat_hunt_followup:5406:creature:6"])
        preview = payload["previews"][0]
        self.assertEqual(preview["status"], "preview")
        self.assertTrue(preview["steps"][0]["details"]["dry_run_ready"])


if __name__ == "__main__":
    unittest.main()
