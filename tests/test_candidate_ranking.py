from __future__ import annotations

import unittest

from wm.candidates.ranking import CandidateContext, annotate_summary_with_score, build_candidate_context, score_spell_candidate


class CandidateRankingTests(unittest.TestCase):
    def test_build_candidate_context_extracts_terms(self) -> None:
        context = build_candidate_context(
            target_profile={
                "name": "Murloc Forager",
                "faction_label": "Murloc",
                "mechanical_type": "HUMANOID",
                "family": None,
                "level_min": 9,
                "level_max": 10,
            },
            character_profile={
                "preferred_themes": ["arcane experimentation", "ironforge politics"],
                "avoided_themes": ["holy zealotry"],
            },
        )
        self.assertEqual(context.target_level_hint, 9)
        self.assertIn("murloc", context.positive_terms)
        self.assertIn("arcane", context.positive_terms)
        self.assertIn("holy", context.negative_terms)

    def test_spell_ranking_penalizes_passive_gossip_noise(self) -> None:
        context = CandidateContext(target_level_hint=10, positive_terms=["arcane"], negative_terms=[])
        good = score_spell_candidate({"ManaCost": 50, "Effect_1": 6, "DurationIndex": 0}, "Arcane Burst", context)
        bad = score_spell_candidate({"ManaCost": 0, "Effect_1": 6, "DurationIndex": 0}, "Mine Slave - On Gossip Passive", context)
        self.assertGreater(good, bad)

    def test_annotate_summary_with_score(self) -> None:
        self.assertEqual(annotate_summary_with_score("ManaCost=50", 23), "score=23; ManaCost=50")
        self.assertEqual(annotate_summary_with_score(None, -5), "score=-5")


if __name__ == "__main__":
    unittest.main()
