from __future__ import annotations

import re
import unittest

from wm.quests.bounty import build_bounty_quest_draft
from wm.quests.compiler import compile_bounty_quest_sql_plan
from wm.targets.resolver import TargetProfile

# ADR-0004 action item 4: lock the reward-panel-critical column contract so a
# compiler regression is caught in the repo, not by burning a live BridgeLab
# proof window. These columns are the ones the in-client quest log + reward
# panel + quest cache actually depend on (see WM_PLATFORM_HANDOFF "Known
# footguns" and the arc factory money-as-bogus-item guard).


def _quest_template_insert(statements: list[str]) -> dict[str, str]:
    stmt = next(
        (s for s in statements if s.startswith("INSERT INTO quest_template (")),
        None,
    )
    assert stmt is not None, "no quest_template INSERT in compiled plan"
    match = re.match(
        r"INSERT INTO quest_template \(([^)]*)\) VALUES \((.*)\);$",
        stmt,
        re.DOTALL,
    )
    assert match, f"unparseable quest_template INSERT: {stmt!r}"
    columns = [c.strip() for c in match.group(1).split(",")]
    # Values can contain commas inside quoted strings; split on top-level commas.
    raw = match.group(2)
    values: list[str] = []
    depth_quote = False
    current = ""
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "'":
            depth_quote = not depth_quote
            current += ch
        elif ch == "," and not depth_quote:
            values.append(current.strip())
            current = ""
        else:
            current += ch
        i += 1
    if current.strip():
        values.append(current.strip())
    assert len(columns) == len(values), f"column/value arity mismatch: {columns} vs {values}"
    return dict(zip(columns, values))


class ArcCompilerContractTests(unittest.TestCase):
    def _target(self) -> TargetProfile:
        return TargetProfile(
            entry=46,
            name="Murloc Forager",
            subname=None,
            level_min=9,
            level_max=10,
            faction_id=18,
            faction_label="Murloc",
            mechanical_type="HUMANOID",
            family=None,
            rank="NORMAL",
            unit_class="WARRIOR",
            service_roles=[],
            has_gossip_menu=False,
        )

    def _arc_draft(self, *, reward_item_mode: str = "fixed"):
        # Mirrors the arc factory shape: fixed managed reward item, money
        # cleared to 0 (repack surfaces RewardMoney as a bogus visible item),
        # structural defaults harvested from a working questgiver quest.
        draft = build_bounty_quest_draft(
            quest_id=910171,
            questgiver_entry=11856,
            questgiver_name="Earthmender Wilda",
            target_profile=self._target(),
            kill_count=4,
            reward_money_copper=0,
            reward_item_entry=910013,
            reward_item_name="Shadowmoon Watcher's Lens",
            reward_item_count=1,
            reward_item_mode=reward_item_mode,
            reward_xp_difficulty=5,
            template_defaults={"QuestSortID": 3520, "QuestInfoID": 41, "SpecialFlags": 0},
        )
        draft.title = "Shadowmoon Watcher's Bounty"
        draft.objective_text = "Slay 4 Shadowmoon Watchers."
        return draft

    def test_fixed_reward_panel_columns_present_and_correct(self) -> None:
        plan = compile_bounty_quest_sql_plan(self._arc_draft())
        cols = _quest_template_insert(plan.statements)

        self.assertEqual(cols["ID"], "910171")
        self.assertIn("LogTitle", cols)
        self.assertNotEqual(cols["LogTitle"], "''")
        self.assertIn("ObjectiveText1", cols)
        self.assertNotEqual(cols["ObjectiveText1"], "''")
        # Reward delivery: fixed item must land in RewardItem1/RewardAmount1.
        self.assertEqual(cols["RewardItem1"], "910013")
        self.assertEqual(cols["RewardAmount1"], "1")
        # Money-as-bogus-item guard: arc clears visible money.
        self.assertEqual(cols["RewardMoney"], "0")
        # Stale source-text footgun: these must be overwritten, never inherited.
        self.assertIn("LogDescription", cols)
        self.assertIn("QuestCompletionLog", cols)

    def test_choice_reward_routes_to_choice_columns_not_fixed(self) -> None:
        plan = compile_bounty_quest_sql_plan(self._arc_draft(reward_item_mode="choice"))
        cols = _quest_template_insert(plan.statements)

        # In choice mode the fixed slot must be empty and the choice slot set,
        # or the reward panel shows the wrong reward identity.
        self.assertEqual(cols["RewardItem1"], "0")
        self.assertEqual(cols["RewardAmount1"], "0")
        self.assertEqual(cols.get("RewardChoiceItemID1"), "910013")

    def test_repeatable_special_flag_is_emitted(self) -> None:
        # Repeatable semantics (SpecialFlags |= 1) must reach the DB so a
        # rewarded bounty can be turned in again after cache reload.
        draft = self._arc_draft()
        draft.template_defaults["SpecialFlags"] = 1
        plan = compile_bounty_quest_sql_plan(
            draft,
            available_tables={"quest_template_addon"},
            quest_template_addon_columns={"ID", "SpecialFlags"},
        )
        joined = "\n".join(plan.statements)
        self.assertIn("quest_template_addon (ID, SpecialFlags) VALUES (910171, 1)", joined)

    def test_fresh_id_delete_precedes_insert(self) -> None:
        # The plan must clear any prior row on the fresh id before insert, or a
        # re-published arc quest collides with a stale cached row.
        plan = compile_bounty_quest_sql_plan(self._arc_draft())
        joined = "\n".join(plan.statements)
        del_idx = joined.index("DELETE FROM quest_template WHERE ID = 910171;")
        ins_idx = joined.index("INSERT INTO quest_template")
        self.assertLess(del_idx, ins_idx)


if __name__ == "__main__":
    unittest.main()
