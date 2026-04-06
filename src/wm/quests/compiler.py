from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class QuestSqlPlan:
    quest_id: int
    statements: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_QUEST_TEMPLATE_COLUMNS = {
    "ID",
    "QuestType",
    "QuestLevel",
    "MinLevel",
    "LogTitle",
    "QuestDescription",
    "ObjectiveText1",
    "OfferRewardText",
    "RequestItemsText",
    "RewardMoney",
    "RewardItem1",
    "RewardAmount1",
    "RequiredNpcOrGo1",
    "RequiredNpcOrGoCount1",
}

_TEMPLATE_DEFAULT_COPY_COLUMNS = {
    "Method",
    "QuestMethod",
    "Type",
    "QuestType",
    "QuestFlags",
    "Flags",
    "SpecialFlags",
    "QuestInfoID",
    "QuestSortID",
    "ZoneOrSort",
    "SuggestedPlayers",
}


def compile_bounty_quest_sql_plan(
    draft,
    *,
    quest_template_columns: set[str] | None = None,
    available_tables: set[str] | None = None,
    quest_offer_reward_columns: set[str] | None = None,
    quest_request_items_columns: set[str] | None = None,
) -> QuestSqlPlan:
    quest_template_columns = set(quest_template_columns or DEFAULT_QUEST_TEMPLATE_COLUMNS)
    available_tables = set(available_tables or set())
    quest_offer_reward_columns = set(quest_offer_reward_columns or set())
    quest_request_items_columns = set(quest_request_items_columns or set())
    template_defaults = {str(k): v for k, v in getattr(draft, "template_defaults", {}).items()}

    reward_item_entry = draft.reward.reward_item_entry or 0
    reward_item_count = draft.reward.reward_item_count if draft.reward.reward_item_entry is not None else 0

    statements = [
        f"-- WM staged bounty quest {draft.quest_id}: {draft.title}",
        f"DELETE FROM creature_queststarter WHERE quest = {draft.quest_id};",
        f"DELETE FROM creature_questender WHERE quest = {draft.quest_id};",
    ]

    if "quest_offer_reward" in available_tables:
        statements.append(f"DELETE FROM quest_offer_reward WHERE ID = {draft.quest_id};")
    if "quest_request_items" in available_tables:
        statements.append(f"DELETE FROM quest_request_items WHERE ID = {draft.quest_id};")

    statements.append(f"DELETE FROM quest_template WHERE ID = {draft.quest_id};")

    insert_columns: list[str] = []
    insert_values: list[str] = []

    def add_column(column_name: str, sql_value: str) -> None:
        if column_name in quest_template_columns:
            insert_columns.append(column_name)
            insert_values.append(sql_value)

    def add_default_column(column_name: str, fallback_sql_value: str | None = None) -> None:
        if column_name not in quest_template_columns:
            return
        if column_name in template_defaults and template_defaults[column_name] not in (None, ""):
            add_column(column_name, _sql_literal(template_defaults[column_name]))
            return
        if fallback_sql_value is not None:
            add_column(column_name, fallback_sql_value)

    add_column("ID", str(draft.quest_id))
    add_default_column("Method", "2")
    add_default_column("QuestMethod", "2")
    add_default_column("Type", "0")
    add_default_column("QuestType", "0")
    add_column("QuestLevel", str(draft.quest_level))
    add_column("MinLevel", str(draft.min_level))
    add_default_column("ZoneOrSort")
    add_default_column("QuestSortID")
    add_default_column("QuestInfoID")
    add_default_column("SuggestedPlayers")
    add_default_column("Flags")
    add_default_column("QuestFlags")
    add_default_column("SpecialFlags")
    add_column("LogTitle", _sql_quote(draft.title))

    if "QuestDescription" in quest_template_columns:
        add_column("QuestDescription", _sql_quote(draft.quest_description))
    elif "Details" in quest_template_columns:
        add_column("Details", _sql_quote(draft.quest_description))

    if "ObjectiveText1" in quest_template_columns:
        add_column("ObjectiveText1", _sql_quote(draft.objective_text))
    elif "Objectives" in quest_template_columns:
        add_column("Objectives", _sql_quote(draft.objective_text))

    if "OfferRewardText" in quest_template_columns:
        add_column("OfferRewardText", _sql_quote(draft.offer_reward_text))

    if "RequestItemsText" in quest_template_columns:
        add_column("RequestItemsText", _sql_quote(draft.request_items_text))

    add_column("RewardMoney", str(draft.reward.money_copper))
    add_column("RewardItem1", str(reward_item_entry))
    add_column("RewardAmount1", str(reward_item_count))
    add_column("RequiredNpcOrGo1", str(draft.objective.target_entry))
    add_column("RequiredNpcOrGoCount1", str(draft.objective.kill_count))

    statements.append(
        "INSERT INTO quest_template "
        f"({', '.join(insert_columns)}) VALUES "
        f"({', '.join(insert_values)});"
    )

    if (
        "OfferRewardText" not in quest_template_columns
        and "quest_offer_reward" in available_tables
        and "RewardText" in quest_offer_reward_columns
    ):
        statements.append(
            "INSERT INTO quest_offer_reward (ID, RewardText) VALUES "
            f"({draft.quest_id}, {_sql_quote(draft.offer_reward_text)});"
        )

    if (
        "RequestItemsText" not in quest_template_columns
        and "quest_request_items" in available_tables
        and "CompletionText" in quest_request_items_columns
    ):
        statements.append(
            "INSERT INTO quest_request_items (ID, CompletionText) VALUES "
            f"({draft.quest_id}, {_sql_quote(draft.request_items_text)});"
        )

    statements.extend(
        [
            "INSERT INTO creature_queststarter (id, quest) VALUES "
            f"({draft.questgiver_entry}, {draft.quest_id});",
            "INSERT INTO creature_questender (id, quest) VALUES "
            f"({draft.questgiver_entry}, {draft.quest_id});",
        ]
    )

    return QuestSqlPlan(quest_id=draft.quest_id, statements=statements)


def _sql_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return _sql_quote(str(value))
