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
    "LogDescription",
    "QuestDescription",
    "QuestCompletionLog",
    "ObjectiveText1",
    "OfferRewardText",
    "RequestItemsText",
    "RewardMoney",
    "RewardItem1",
    "RewardAmount1",
    "RewardChoiceItemID1",
    "RewardChoiceItemQuantity1",
    "RewardXPDifficulty",
    "RewardSpell",
    "RewardDisplaySpell",
    "RewardFactionID1",
    "RewardFactionOverride1",
    "RequiredNpcOrGo1",
    "RequiredNpcOrGoCount1",
}

_XP_REWARD_COLUMNS = ("RewardXPDifficulty", "RewardXPId", "RewardXP")
_REWARD_CHOICE_ITEM_ID_COLUMNS = ("RewardChoiceItemID{index}", "RewardChoiceItemId{index}")
_REWARD_CHOICE_ITEM_COUNT_COLUMNS = ("RewardChoiceItemQuantity{index}", "RewardChoiceItemCount{index}")
_REPUTATION_SLOT_COUNT = 5
_REPUTATION_FACTION_COLUMNS = ("RewardFactionID{index}", "RewardFactionId{index}")
_REPUTATION_VALUE_COLUMNS = (
    "RewardFactionOverride{index}",
    "RewardFactionValue{index}",
    "RewardFactionValueIdOverride{index}",
    "RewardFactionValueId{index}",
)

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
    quest_template_addon_columns: set[str] | None = None,
    available_tables: set[str] | None = None,
    quest_offer_reward_columns: set[str] | None = None,
    quest_request_items_columns: set[str] | None = None,
) -> QuestSqlPlan:
    quest_template_columns = set(quest_template_columns or DEFAULT_QUEST_TEMPLATE_COLUMNS)
    quest_template_addon_columns = set(quest_template_addon_columns or set())
    available_tables = set(available_tables or set())
    quest_offer_reward_columns = set(quest_offer_reward_columns or set())
    quest_request_items_columns = set(quest_request_items_columns or set())
    template_defaults = {str(k): v for k, v in getattr(draft, "template_defaults", {}).items()}

    reward_item_entry = draft.reward.reward_item_entry or 0
    reward_item_count = draft.reward.reward_item_count if draft.reward.reward_item_entry is not None else 0
    reward_item_mode = str(getattr(draft.reward, "reward_item_mode", "fixed") or "fixed")
    fixed_reward_item_entry = reward_item_entry if reward_item_mode == "fixed" else 0
    fixed_reward_item_count = reward_item_count if reward_item_mode == "fixed" else 0
    choice_reward_item_entry = reward_item_entry if reward_item_mode == "choice" else 0
    choice_reward_item_count = reward_item_count if reward_item_mode == "choice" else 0
    reward_spell_id = draft.reward.reward_spell_id or 0
    reward_spell_display_id = draft.reward.reward_spell_display_id or 0

    statements = [
        f"-- WM staged bounty quest {draft.quest_id}: {draft.title}",
        f"DELETE FROM creature_queststarter WHERE quest = {draft.quest_id};",
        f"DELETE FROM creature_questender WHERE quest = {draft.quest_id};",
    ]

    if "quest_offer_reward" in available_tables:
        statements.append(f"DELETE FROM quest_offer_reward WHERE ID = {draft.quest_id};")
    if "quest_request_items" in available_tables:
        statements.append(f"DELETE FROM quest_request_items WHERE ID = {draft.quest_id};")
    if "quest_template_addon" in available_tables:
        statements.append(f"DELETE FROM quest_template_addon WHERE ID = {draft.quest_id};")

    statements.append(f"DELETE FROM quest_template WHERE ID = {draft.quest_id};")

    insert_columns: list[str] = []
    insert_values: list[str] = []
    addon_insert_columns: list[str] = []
    addon_insert_values: list[str] = []

    def add_column(column_name: str, sql_value: str) -> None:
        if column_name in quest_template_columns and column_name not in insert_columns:
            insert_columns.append(column_name)
            insert_values.append(sql_value)

    def add_addon_column(column_name: str, sql_value: str) -> None:
        if column_name in quest_template_addon_columns and column_name not in addon_insert_columns:
            addon_insert_columns.append(column_name)
            addon_insert_values.append(sql_value)

    def add_default_column(column_name: str, fallback_sql_value: str | None = None) -> None:
        if column_name not in quest_template_columns:
            return
        if column_name in template_defaults and template_defaults[column_name] not in (None, ""):
            add_column(column_name, _sql_literal(template_defaults[column_name]))
            return
        if fallback_sql_value is not None:
            add_column(column_name, fallback_sql_value)

    def add_addon_default_column(column_name: str, fallback_sql_value: str | None = None) -> None:
        if column_name not in quest_template_addon_columns:
            return
        if column_name in template_defaults and template_defaults[column_name] not in (None, ""):
            add_addon_column(column_name, _sql_literal(template_defaults[column_name]))
            return
        if fallback_sql_value is not None:
            add_addon_column(column_name, fallback_sql_value)

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
    if "SpecialFlags" not in quest_template_columns:
        add_addon_default_column("SpecialFlags")
    add_column("LogTitle", _sql_quote(draft.title))
    add_column("LogDescription", _sql_quote(draft.request_items_text))

    if "QuestDescription" in quest_template_columns:
        add_column("QuestDescription", _sql_quote(draft.quest_description))
    elif "Details" in quest_template_columns:
        add_column("Details", _sql_quote(draft.quest_description))

    if "QuestCompletionLog" in quest_template_columns:
        add_column("QuestCompletionLog", _sql_quote(draft.request_items_text))

    if "ObjectiveText1" in quest_template_columns:
        add_column("ObjectiveText1", _sql_quote(draft.objective_text))
    elif "Objectives" in quest_template_columns:
        add_column("Objectives", _sql_quote(draft.objective_text))

    if "OfferRewardText" in quest_template_columns:
        add_column("OfferRewardText", _sql_quote(draft.offer_reward_text))

    if "RequestItemsText" in quest_template_columns:
        add_column("RequestItemsText", _sql_quote(draft.request_items_text))

    add_column("RewardMoney", str(draft.reward.money_copper))
    add_column("RewardItem1", str(fixed_reward_item_entry))
    add_column("RewardAmount1", str(fixed_reward_item_count))
    choice_item_column = _first_available_column(
        tuple(template.format(index=1) for template in _REWARD_CHOICE_ITEM_ID_COLUMNS),
        quest_template_columns,
    )
    choice_count_column = _first_available_column(
        tuple(template.format(index=1) for template in _REWARD_CHOICE_ITEM_COUNT_COLUMNS),
        quest_template_columns,
    )
    if choice_item_column is not None:
        add_column(choice_item_column, str(choice_reward_item_entry))
    if choice_count_column is not None:
        add_column(choice_count_column, str(choice_reward_item_count))
    if draft.reward.reward_xp_difficulty is not None:
        xp_column = _first_available_column(_XP_REWARD_COLUMNS, quest_template_columns)
        if xp_column is not None:
            add_column(xp_column, str(int(draft.reward.reward_xp_difficulty)))
    add_column("RewardSpell", str(reward_spell_id))
    add_column("RewardDisplaySpell", str(reward_spell_display_id))
    for index, reward in enumerate(draft.reward.reward_reputations[:_REPUTATION_SLOT_COUNT], start=1):
        faction_column = _first_available_column(
            tuple(template.format(index=index) for template in _REPUTATION_FACTION_COLUMNS),
            quest_template_columns,
        )
        value_column = _first_available_column(
            tuple(template.format(index=index) for template in _REPUTATION_VALUE_COLUMNS),
            quest_template_columns,
        )
        if faction_column is not None and value_column is not None:
            add_column(faction_column, str(int(reward.faction_id)))
            add_column(value_column, str(int(reward.value)))
    add_column("RequiredNpcOrGo1", str(draft.objective.target_entry))
    add_column("RequiredNpcOrGoCount1", str(draft.objective.kill_count))

    for column_name in sorted(
        set(template_defaults) & quest_template_addon_columns - set(quest_template_columns) - {"ID", "SpecialFlags"}
    ):
        add_addon_default_column(column_name)

    statements.append(
        "INSERT INTO quest_template "
        f"({', '.join(insert_columns)}) VALUES "
        f"({', '.join(insert_values)});"
    )

    if addon_insert_columns:
        statements.append(
            "INSERT INTO quest_template_addon "
            f"(ID, {', '.join(addon_insert_columns)}) VALUES "
            f"({draft.quest_id}, {', '.join(addon_insert_values)});"
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

    if draft.start_npc_entry is not None:
        statements.append(
            "INSERT INTO creature_queststarter (id, quest) VALUES "
            f"({int(draft.start_npc_entry)}, {draft.quest_id});"
        )
    if draft.end_npc_entry is not None:
        statements.append(
            "INSERT INTO creature_questender (id, quest) VALUES "
            f"({int(draft.end_npc_entry)}, {draft.quest_id});"
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


def _first_available_column(candidates: tuple[str, ...], available_columns: set[str]) -> str | None:
    for column in candidates:
        if column in available_columns:
            return column
    return None


@dataclass
class QuestPublishPlan:
    quest_id: int
    quest_template_row: dict
    quest_template_addon_row: dict
    rollback_snapshot: dict
    dry_run_commands: list[str]
    apply_commands: list[str]
    verify_queries: list[str]
    affected_tables: list[str]


class QuestCompiler:
    """Generates clean quest_template rows from a draft dict. No clone source."""

    def compile(self, draft: dict, schema: "Any") -> QuestPublishPlan:
        from wm.quests.schema import QuestTemplateSchema
        quest_id = draft["quest_id"]
        row = self._build_quest_template_row(draft)

        if isinstance(schema, QuestTemplateSchema):
            errors = schema.validate_draft(row)
            if errors:
                raise ValueError(f"Draft validation failed: {errors}")
        addon_row = self._build_quest_template_addon_row(draft)

        insert_sql = self._to_insert_sql("quest_template", row)
        addon_sql = self._to_insert_sql("quest_template_addon", addon_row)

        return QuestPublishPlan(
            quest_id=quest_id,
            quest_template_row=row,
            quest_template_addon_row=addon_row,
            rollback_snapshot={},
            dry_run_commands=[insert_sql, addon_sql],
            apply_commands=[insert_sql, addon_sql],
            verify_queries=[
                f"SELECT ID FROM quest_template WHERE ID = {quest_id}",
            ],
            affected_tables=["quest_template", "quest_template_addon"],
        )

    def _build_quest_template_row(self, draft: dict) -> dict:
        return {
            "ID": draft["quest_id"],
            "QuestType": 2,
            "QuestLevel": draft.get("level", 1),
            "MinLevel": draft.get("min_level", 1),
            "QuestSortID": draft.get("sort_id", 1),
            "QuestInfoID": 0,
            "SuggestedGroupNum": 0,
            "RequiredFactionId1": 0, "RequiredFactionValue1": 0,
            "RewardNextQuest": draft.get("reward_next_quest") or 0,
            "RewardXPDifficulty": draft.get("xp_difficulty", 1),
            "RewardMoney": draft.get("reward_money", 0),
            "RewardBonusMoney": 0,
            "RewardDisplaySpell": 0, "RewardSpell": 0,
            "RewardHonor": 0, "RewardKillHonor": 0,
            "StartItem": 0,
            "RequiredPlayerKills": 0,
            "RewardItem1": draft.get("reward_item_entry") or 0,
            "RewardAmount1": draft.get("reward_item_count") or 0,
            "RewardItem2": 0, "RewardAmount2": 0,
            "RewardItem3": 0, "RewardAmount3": 0,
            "RewardItem4": 0, "RewardAmount4": 0,
            "LogTitle": draft.get("title", ""),
            "LogDescription": draft.get("log_description") or "",
            "QuestDescription": draft.get("description") or "",
            "AreaDescription": draft.get("area_description") or "",
            "QuestCompletionLog": draft.get("completion_log") or "",
        }

    def _build_quest_template_addon_row(self, draft: dict) -> dict:
        return {
            "ID": draft["quest_id"],
            "MaxLevel": 0, "AllowableClasses": 0,
            "SourceSpellID": 0, "PrevQuestID": 0,
            "NextQuestID": draft.get("reward_next_quest") or 0,
            "ExclusiveGroup": 0, "RewardMailTemplateID": 0,
            "RewardMailDelay": 0, "RequiredSkillID": 0,
            "RequiredSkillPoints": 0, "RequiredMinRepFaction": 0,
            "RequiredMaxRepFaction": 0, "RequiredMinRepValue": 0,
            "RequiredMaxRepValue": 0, "ProvidedItemCount": 0,
            "SpecialFlags": 0,
        }

    def _to_insert_sql(self, table: str, row: dict) -> str:
        cols = ", ".join(row.keys())
        vals = ", ".join(
            f"'{v}'" if isinstance(v, str) else str(v)
            for v in row.values()
        )
        return f"INSERT INTO {table} ({cols}) VALUES ({vals});"
