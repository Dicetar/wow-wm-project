"""Tests for QuestTemplateSchema + QuestCompiler (no clone source)."""
from __future__ import annotations


def test_quest_template_schema_validates_draft():
    from wm.quests.schema import QuestTemplateSchema
    schema = QuestTemplateSchema(
        columns=["ID", "LogTitle", "LogDescription", "QuestLevel", "RewardMoney"],
        required_for_visibility={"ID", "LogTitle"},
        safe_to_zero={"RewardMoney"},
    )
    errors = schema.validate_draft({"ID": 910200, "LogTitle": "Test Quest"})
    assert errors == []


def test_quest_template_schema_catches_missing_required():
    from wm.quests.schema import QuestTemplateSchema
    schema = QuestTemplateSchema(
        columns=["ID", "LogTitle"],
        required_for_visibility={"ID", "LogTitle"},
        safe_to_zero=set(),
    )
    errors = schema.validate_draft({"ID": 910200})
    assert any("LogTitle" in e for e in errors)


def test_compiler_produces_plan_with_no_clone_source():
    from wm.quests.schema import QuestTemplateSchema
    from wm.quests.compiler import QuestCompiler
    schema = QuestTemplateSchema(
        columns=["ID", "LogTitle", "QuestLevel", "RewardMoney",
                 "LogDescription", "QuestDescription", "QuestCompletionLog"],
        required_for_visibility={"ID", "LogTitle"},
        safe_to_zero={"RewardMoney"},
    )
    draft = {
        "quest_id": 910200, "title": "Slay Ten Wolves", "level": 10,
        "min_level": 8, "sort_id": 1, "xp_difficulty": 1, "reward_money": 0,
        "log_description": "Wolves prowl Elwynn.", "description": "Kill 10 wolves.",
        "completion_log": "You have slain the wolves.",
    }
    compiler = QuestCompiler()
    plan = compiler.compile(draft, schema)
    assert plan.quest_id == 910200
    plan_str = str(plan.quest_template_row)
    assert "910151" not in plan_str
