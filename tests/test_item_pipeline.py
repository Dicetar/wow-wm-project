import unittest

from wm.items.compiler import compile_managed_item_sql_plan
from wm.items.models import ItemSpellLine, ItemStatLine, ManagedItemDraft
from wm.items.validator import validate_managed_item_draft


class ManagedItemDraftValidationTests(unittest.TestCase):
    def test_rejects_same_item_and_base_entry(self) -> None:
        draft = ManagedItemDraft(item_entry=910000, base_item_entry=910000, name="Bad Draft")
        result = validate_managed_item_draft(draft)
        self.assertFalse(result.ok)

    def test_accepts_basic_valid_draft(self) -> None:
        draft = ManagedItemDraft(
            item_entry=910000,
            base_item_entry=6948,
            name="WM Prototype Token",
            clear_spells=True,
            stats=[ItemStatLine(stat_type=7, stat_value=5)],
            spells=[ItemSpellLine(spell_id=133, trigger=0)],
        )
        result = validate_managed_item_draft(draft)
        self.assertTrue(result.ok)


class ManagedItemSqlPlanTests(unittest.TestCase):
    def test_compiles_replace_statement(self) -> None:
        plan = compile_managed_item_sql_plan(
            item_entry=910000,
            final_row={"entry": 910000, "name": "WM Prototype Token", "Quality": 2},
            column_order=["entry", "name", "Quality"],
            note="cloned from base item 6948",
        )
        self.assertEqual(plan.item_entry, 910000)
        self.assertTrue(any("REPLACE INTO item_template" in stmt for stmt in plan.statements))
        self.assertTrue(any("WM Prototype Token" in stmt for stmt in plan.statements))


if __name__ == "__main__":
    unittest.main()
