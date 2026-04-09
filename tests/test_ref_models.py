import unittest

from wm.quests.bounty import build_bounty_quest_draft
from wm.reactive.models import ReactiveQuestRule
from wm.refs import CreatureRef
from wm.refs import NpcRef
from wm.refs import PlayerRef
from wm.refs import QuestRef
from wm.targets.resolver import TargetProfile


class RefModelCompatibilityTests(unittest.TestCase):
    def _target(self) -> TargetProfile:
        return TargetProfile(
            entry=6,
            name="Kobold Vermin",
            subname=None,
            level_min=3,
            level_max=4,
            faction_id=38,
            faction_label="Defias / Kobold",
            mechanical_type="HUMANOID",
            family=None,
            rank="NORMAL",
            unit_class="WARRIOR",
            service_roles=[],
            has_gossip_menu=False,
        )

    def test_reactive_rule_serializes_nested_refs_with_legacy_scalars(self) -> None:
        rule = ReactiveQuestRule(
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
            player_scope=PlayerRef(guid=5406, name="Jecia"),
            subject=CreatureRef(entry=6, name="Kobold Vermin"),
            quest=QuestRef(id=910000, title="Bounty: Kobold Vermin"),
            turn_in_npc=NpcRef(entry=197, name="Marshal McBride"),
        )

        payload = rule.to_dict()

        self.assertEqual(payload["player_guid_scope"], 5406)
        self.assertEqual(payload["subject_entry"], 6)
        self.assertEqual(payload["quest_id"], 910000)
        self.assertEqual(payload["turn_in_npc_entry"], 197)
        self.assertEqual(payload["player_scope"]["name"], "Jecia")
        self.assertEqual(payload["subject"]["name"], "Kobold Vermin")
        self.assertEqual(payload["quest"]["title"], "Bounty: Kobold Vermin")
        self.assertEqual(payload["turn_in_npc"]["name"], "Marshal McBride")

    def test_bounty_draft_exposes_nested_refs_with_legacy_scalars(self) -> None:
        draft = build_bounty_quest_draft(
            quest_id=910000,
            questgiver_entry=197,
            questgiver_name="Marshal McBride",
            target_profile=self._target(),
            kill_count=4,
            reward_money_copper=900,
            start_npc_entry=None,
            end_npc_entry=197,
            grant_mode="direct_quest_add",
        )

        payload = draft.to_dict()

        self.assertEqual(payload["quest_id"], 910000)
        self.assertEqual(payload["quest"]["title"], "Bounty: Kobold Vermin")
        self.assertEqual(payload["questgiver"]["name"], "Marshal McBride")
        self.assertIsNone(payload["starter_npc"])
        self.assertEqual(payload["ender_npc"]["entry"], 197)
        self.assertEqual(payload["objective"]["target"]["entry"], 6)
        self.assertEqual(payload["objective"]["target"]["name"], "Kobold Vermin")


if __name__ == "__main__":
    unittest.main()
