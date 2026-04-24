import unittest
from pathlib import Path

from wm.spells.models import ManagedSpellDraft, ManagedSpellLink, ManagedSpellProcRule
from wm.spells.publish import load_managed_spell_draft
from wm.spells.shell_bank import load_spell_shell_bank
from wm.spells.validator import validate_managed_spell_draft


class ManagedSpellDraftValidationTests(unittest.TestCase):
    def test_requires_visible_base_for_visible_slot(self) -> None:
        draft = ManagedSpellDraft(
            spell_entry=947000,
            slot_kind="visible_spell_slot",
            name="Visible Test Slot",
        )
        result = validate_managed_spell_draft(draft)
        self.assertFalse(result.ok)

    def test_accepts_item_trigger_slot_with_required_fields(self) -> None:
        draft = ManagedSpellDraft(
            spell_entry=947000,
            slot_kind="item_trigger_slot",
            name="Marshal Token Trigger",
            helper_spell_id=133,
            trigger_item_entry=910000,
            proc_rules=[ManagedSpellProcRule(spell_id=947000, chance=25.0)],
            linked_spells=[ManagedSpellLink(trigger_spell_id=947000, effect_spell_id=133)],
        )
        result = validate_managed_spell_draft(draft)
        self.assertTrue(result.ok)

    def test_rejects_named_shell_id_collision(self) -> None:
        draft = ManagedSpellDraft(
            spell_entry=940000,
            slot_kind="visible_spell_slot",
            name="Bad Collision",
            base_visible_spell_id=133,
        )
        result = validate_managed_spell_draft(draft)

        self.assertFalse(result.ok)
        self.assertTrue(any("named shell" in issue.message for issue in result.issues))

    def test_bundled_example_uses_managed_slot_not_named_shell_id(self) -> None:
        draft = load_managed_spell_draft(
            Path(__file__).resolve().parents[1].joinpath("control", "examples", "spells", "defias_pursuit_instinct.json")
        )
        named_shell = load_spell_shell_bank().shell_by_spell_id(draft.spell_entry)

        self.assertEqual(draft.spell_entry, 947000)
        self.assertIsNone(named_shell)


if __name__ == "__main__":
    unittest.main()
