from __future__ import annotations

import json

from wm.quests.bounty import build_bounty_quest_draft
from wm.quests.compiler import compile_bounty_quest_sql_plan
from wm.quests.validator import validate_bounty_quest_draft
from wm.targets.resolver import TargetProfile


def main() -> None:
    target = TargetProfile(
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

    draft = build_bounty_quest_draft(
        quest_id=910001,
        questgiver_entry=1498,
        questgiver_name="Bethor Iceshard",
        target_profile=target,
        kill_count=8,
        reward_money_copper=1200,
    )
    validation = validate_bounty_quest_draft(draft)
    plan = compile_bounty_quest_sql_plan(draft)

    print(
        json.dumps(
            {
                "draft": draft.to_dict(),
                "validation": validation.to_dict(),
                "sql_plan": plan.to_dict(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
