from __future__ import annotations

import unittest

from wm.candidates.filters import is_candidate_label_allowed


class CandidateFilterTests(unittest.TestCase):
    def test_allows_normal_labels(self) -> None:
        self.assertTrue(is_candidate_label_allowed("item", "Arcane Blade"))
        self.assertTrue(is_candidate_label_allowed("quest", "A Cautious Truce"))
        self.assertTrue(is_candidate_label_allowed("spell", "Arcane Barrage"))

    def test_blocks_deprecated_and_unused_labels(self) -> None:
        self.assertFalse(is_candidate_label_allowed("item", "Deprecated Tauren Recruit's Shirt"))
        self.assertFalse(is_candidate_label_allowed("item", "[UNUSED] Dummy Sword"))
        self.assertFalse(is_candidate_label_allowed("quest", "zzOLDTestQuest"))
        self.assertFalse(is_candidate_label_allowed("spell", "Deprecated Fire Blast"))


if __name__ == "__main__":
    unittest.main()
