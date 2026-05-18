"""Tests for publish_quest / rollback_quest (Phase 4 simple API)."""
from __future__ import annotations


def test_publish_dry_run_does_not_execute():
    from wm.quests.publish import publish_quest
    from wm.quests.compiler import QuestPublishPlan

    executed = []

    class MockDB:
        def execute(self, sql, params=None): executed.append(sql)
        def query(self, sql, params=None): return []

    plan = QuestPublishPlan(
        quest_id=910200,
        quest_template_row={"ID": 910200, "LogTitle": "Test"},
        quest_template_addon_row={"ID": 910200},
        rollback_snapshot={},
        dry_run_commands=["INSERT INTO quest_template ..."],
        apply_commands=["INSERT INTO quest_template ..."],
        verify_queries=["SELECT ID FROM quest_template WHERE ID = 910200"],
        affected_tables=["quest_template"],
    )
    result = publish_quest(plan, db_client=MockDB(), mode="dry_run")
    assert result.mode == "dry_run"
    assert result.executed is False
    assert len(executed) == 0


def test_publish_apply_executes_commands():
    from wm.quests.publish import publish_quest
    from wm.quests.compiler import QuestPublishPlan

    executed = []

    class MockDB:
        def execute(self, sql, params=None): executed.append(sql)
        def query(self, sql, params=None): return [{"ID": 910200}]

    plan = QuestPublishPlan(
        quest_id=910200,
        quest_template_row={"ID": 910200},
        quest_template_addon_row={"ID": 910200},
        rollback_snapshot={},
        dry_run_commands=[],
        apply_commands=["INSERT INTO quest_template ..."],
        verify_queries=["SELECT ID FROM quest_template WHERE ID = 910200"],
        affected_tables=["quest_template"],
    )
    result = publish_quest(plan, db_client=MockDB(), mode="apply")
    assert result.mode == "apply"
    assert result.executed is True
    assert len(executed) >= 1
