import unittest

from wm.spells.models import ManagedSpellDraft, ManagedSpellLink, ManagedSpellProcRule
from wm.spells.validator import validate_managed_spell_draft


class ManagedSpellDraftValidationTests(unittest.TestCase):
    def test_requires_visible_base_for_visible_slot(self) -> None:
        draft = ManagedSpellDraft(
            spell_entry=940000,
            slot_kind="visible_spell_slot",
            name="Visible Test Slot",
        )
        result = validate_managed_spell_draft(draft)
        self.assertFalse(result.ok)

    def test_accepts_item_trigger_slot_with_required_fields(self) -> None:
        draft = ManagedSpellDraft(
            spell_entry=940000,
            slot_kind="item_trigger_slot",
            name="Marshal Token Trigger",
            helper_spell_id=133,
            trigger_item_entry=910000,
            proc_rules=[ManagedSpellProcRule(spell_id=940000, chance=25.0)],
            linked_spells=[ManagedSpellLink(trigger_spell_id=940000, effect_spell_id=133)],
        )
        result = validate_managed_spell_draft(draft)
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
