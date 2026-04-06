from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from wm.quests.models import BountyQuestDraft


@dataclass(slots=True)
class QuestSqlPlan:
    quest_id: int
    statements: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_bounty_quest_sql_plan(draft: BountyQuestDraft) -> QuestSqlPlan:
    reward_item_entry = draft.reward.reward_item_entry or 0
    reward_item_count = draft.reward.reward_item_count if draft.reward.reward_item_entry is not None else 0

    statements = [
        f"-- WM staged bounty quest {draft.quest_id}: {draft.title}",
        f"DELETE FROM creature_queststarter WHERE quest = {draft.quest_id};",
        f"DELETE FROM creature_questender WHERE quest = {draft.quest_id};",
        f"DELETE FROM quest_template WHERE ID = {draft.quest_id};",
        (
            "INSERT INTO quest_template "
            "(ID, QuestType, QuestLevel, MinLevel, LogTitle, QuestDescription, ObjectiveText1, "
            "OfferRewardText, RequestItemsText, RewardMoney, RewardItem1, RewardAmount1, "
            "RequiredNpcOrGo1, RequiredNpcOrGoCount1) VALUES "
            f"({draft.quest_id}, 0, {draft.quest_level}, {draft.min_level}, "
            f"{_sql_quote(draft.title)}, {_sql_quote(draft.quest_description)}, {_sql_quote(draft.objective_text)}, "
            f"{_sql_quote(draft.offer_reward_text)}, {_sql_quote(draft.request_items_text)}, "
            f"{draft.reward.money_copper}, {reward_item_entry}, {reward_item_count}, "
            f"{draft.objective.target_entry}, {draft.objective.kill_count});"
        ),
        (
            "INSERT INTO creature_queststarter (id, quest) VALUES "
            f"({draft.questgiver_entry}, {draft.quest_id});"
        ),
        (
            "INSERT INTO creature_questender (id, quest) VALUES "
            f"({draft.questgiver_entry}, {draft.quest_id});"
        ),
    ]
    return QuestSqlPlan(quest_id=draft.quest_id, statements=statements)


def _sql_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"
