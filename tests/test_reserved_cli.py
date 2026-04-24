from __future__ import annotations

import unittest

from wm.reserved.cli import ReservedCliError, ensure_status, parse_notes_arg, render_slot, render_summary
from wm.reserved.models import ReservedSlot


class ReservedCliTests(unittest.TestCase):
    def test_parse_notes_arg_strips_empty_values(self) -> None:
        self.assertEqual(parse_notes_arg(None), [])
        self.assertEqual(parse_notes_arg([" a ", "", "  ", "b"]), ["a", "b"])

    def test_render_slot_none(self) -> None:
        self.assertEqual(render_slot(None), {"slot": None})

    def test_render_slot_object(self) -> None:
        slot = ReservedSlot(entity_type="quest_template", reserved_id=910000)
        data = render_slot(slot)
        self.assertEqual(data["entity_type"], "quest_template")
        self.assertEqual(data["reserved_id"], 910000)

    def test_render_summary(self) -> None:
        rows = [
            {"EntityType": "spell", "SlotStatus": "free", "CountRows": "10"},
            {"EntityType": "spell", "SlotStatus": "active", "CountRows": "1"},
            {"EntityType": "item_template", "SlotStatus": "free", "CountRows": "5"},
        ]
        summary = render_summary(rows)
        self.assertEqual(summary["spell"]["free"], 10)
        self.assertEqual(summary["spell"]["active"], 1)
        self.assertEqual(summary["item_template"]["free"], 5)

    def test_ensure_status(self) -> None:
        self.assertEqual(ensure_status(" ACTIVE "), "active")
        with self.assertRaises(ReservedCliError):
            ensure_status("broken")


if __name__ == "__main__":
    unittest.main()
