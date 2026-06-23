import unittest

from wm.quests.template_publish import ReputationReward, RichBountyQuestDraft, build_extra_reward_preflight


class TemplatePublishTests(unittest.TestCase):
    def test_extra_reward_preflight_maps_xp_rep_and_spell_columns(self) -> None:
        draft = RichBountyQuestDraft(
            quest_id=910500,
            quest_level=10,
            min_level=8,
            questgiver_entry=240,
            questgiver_name="Marshal Dughan",
            title="Marshal Dughan: Break the Murloc Push",
            quest_description="Drive the murlocs back.",
            objective_text="Slay 5 more Murloc Foragers.",
            offer_reward_text="Stormwind remembers this service.",
            request_items_text="Return to Marshal Dughan.",
            target_entry=46,
            target_name="Murloc Forager",
            kill_count=5,
            reward_money_copper=3500,
            reward_item_entry=45574,
            reward_item_name="Stormwind Tabard",
            reward_item_count=1,
            reward_experience=300,
            reward_spell_cast_id=22888,
            reward_reputations=[ReputationReward(faction_id=72, value=75)],
        )

        preflight = build_extra_reward_preflight(
            draft=draft,
            quest_template_columns={
                "RewardXPDifficulty",
                "RewardSpellCast",
                "RewardFactionId1",
                "RewardFactionValueIdOverride1",
            },
        )

        self.assertTrue(preflight.ok)
        self.assertEqual(preflight.update_fields["RewardXPDifficulty"], 300)
        self.assertEqual(preflight.update_fields["RewardSpellCast"], 22888)
        self.assertEqual(preflight.update_fields["RewardFactionId1"], 72)
        self.assertEqual(preflight.update_fields["RewardFactionValueIdOverride1"], 75)
        self.assertEqual(
            preflight.sql_statements,
            [
                "UPDATE `quest_template` SET `RewardXPDifficulty` = 300, `RewardSpellCast` = 22888, `RewardFactionId1` = 72, `RewardFactionValueIdOverride1` = 75 WHERE `ID` = 910500;"
            ],
        )


if __name__ == "__main__":
    unittest.main()
