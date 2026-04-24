import unittest

from wm.events.models import PlannedAction
from wm.events.models import ReactionOpportunity
from wm.events.models import SubjectRef
from wm.events.planner import DeterministicReactionPlanner


class FakeContentFactory:
    def build_actions(self, opportunity: ReactionOpportunity):
        return (
            [
                PlannedAction(
                    kind="announcement",
                    payload={"text": f"Generated for {opportunity.subject.subject_entry}"},
                )
            ],
            {"factory": "fake"},
        )


class DeterministicReactionPlannerTests(unittest.TestCase):
    def test_plans_multi_artifact_actions_when_payloads_exist(self) -> None:
        planner = DeterministicReactionPlanner()
        opportunity = ReactionOpportunity(
            opportunity_type="repeat_hunt_followup",
            rule_type="repeat_hunt_followup",
            player_guid=42,
            subject=SubjectRef(subject_type="creature", subject_entry=46),
            source_event_key="evt-1",
            metadata={
                "quest_draft": {"quest_id": 910001, "quest_level": 10, "min_level": 8, "questgiver_entry": 1498, "questgiver_name": "Bethor Iceshard", "title": "Bounty: Murloc Forager", "quest_description": "Cull them.", "objective_text": "Slay them.", "offer_reward_text": "Well done.", "request_items_text": "Did you do it?", "objective": {"target_entry": 46, "target_name": "Murloc Forager", "kill_count": 8}, "reward": {"money_copper": 1200, "reward_item_count": 1}, "tags": []},
                "item_draft": {"item_entry": 910100, "base_item_entry": 6948, "name": "WM Token"},
                "spell_draft": {"spell_entry": 947000, "slot_kind": "visible_spell_slot", "name": "WM Passive", "base_visible_spell_id": 133},
                "announcement_text": "The shoreline stirs again.",
            },
            cooldown_seconds=3600,
        )

        plan = planner.plan(opportunity)

        self.assertEqual([action.kind for action in plan.actions], ["quest_publish", "item_publish", "spell_publish", "announcement"])
        self.assertEqual(plan.plan_key, "repeat_hunt_followup:42:creature:46")

    def test_falls_back_to_noop_without_payloads(self) -> None:
        planner = DeterministicReactionPlanner()
        opportunity = ReactionOpportunity(
            opportunity_type="repeat_hunt_followup",
            rule_type="repeat_hunt_followup",
            player_guid=42,
            subject=SubjectRef(subject_type="creature", subject_entry=46),
            source_event_key="evt-2",
        )

        plan = planner.plan(opportunity)

        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(plan.actions[0].kind, "noop")

    def test_uses_content_factory_generated_actions(self) -> None:
        planner = DeterministicReactionPlanner(content_factory=FakeContentFactory())  # type: ignore[arg-type]
        opportunity = ReactionOpportunity(
            opportunity_type="repeat_hunt_followup",
            rule_type="repeat_hunt_followup",
            player_guid=42,
            subject=SubjectRef(subject_type="creature", subject_entry=46),
            source_event_key="evt-3",
        )

        plan = planner.plan(opportunity)

        self.assertEqual([action.kind for action in plan.actions], ["announcement"])
        self.assertEqual(plan.metadata["generated_metadata"]["factory"], "fake")


if __name__ == "__main__":
    unittest.main()
