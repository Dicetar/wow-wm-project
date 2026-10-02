from types import SimpleNamespace

import pytest

from wm.autoplay.quest_feasibility import assess_quest_plan, discover_quest_candidates
from wm.config import Settings


class FakeDatabase:
    def __init__(self, *, enemy_group=1, spawn_count=6):
        self.enemy_group = enemy_group
        self.spawn_count = spawn_count

    def query(self, *, sql, **kwargs):
        if "FROM characters" in sql:
            return [{"race": 1}]
        if "FROM wm_bridge_player_presence" in sql:
            return [{"Online": 1, "MapID": 0, "ZoneName": "Westfall", "PosX": -10500,
                     "PosY": 870, "Level": 20, "AgeSeconds": 2}]
        if "SELECT COUNT(*) AS n FROM creature c" in sql:
            return [{"n": 1}]
        if "ct.entry AS entry" in sql:
            return [{"entry": 234, "name": "Gryan", "x": -10500, "y": 870}]
        if "JOIN creature_template ct ON ct.entry=c.id1" in sql:
            return [{"target_entry": 449, "target_name": "Defias Knuckleduster", "target_level": 20,
                     "spawn_count": self.spawn_count, "x": -10500, "y": 870}]
        if "FROM creature_template" in sql:
            return [{"name": "Defias Test", "minlevel": 20, "maxlevel": 20,
                     "EnemyGroup": self.enemy_group}]
        if "AVG(position_x)" in sql:
            return [{"n": self.spawn_count, "x": -10500, "y": 870}]
        if "FROM creature" in sql:
            return [{"n": 1}]
        raise AssertionError(sql)


def _plan():
    payload = {
        "objective": {"target_entry": 1669, "kill_count": 3},
        "end_npc_entry": 234, "start_npc_entry": 234,
        "questgiver_name": "Gryan", "grant_mode": "direct_grant",
        "reward": {"money_copper": 100},
    }
    return SimpleNamespace(player_guid=5405, actions=[SimpleNamespace(kind="quest_publish", payload=payload)])


def test_quest_feasibility_rejects_friendly_target():
    with pytest.raises(ValueError, match="not verified hostile"):
        assess_quest_plan(plan=_plan(), settings=Settings(), client=FakeDatabase(enemy_group=0))


def test_quest_feasibility_rejects_too_few_spawns():
    with pytest.raises(ValueError, match="only 1"):
        assess_quest_plan(plan=_plan(), settings=Settings(), client=FakeDatabase(spawn_count=1))


def test_quest_feasibility_writes_concrete_directions():
    plan = _plan()
    evidence = assess_quest_plan(plan=plan, settings=Settings(), client=FakeDatabase())
    assert evidence["spawn_count"] == 6
    assert "Kill 3 Defias Test" in plan.actions[0].payload["objective_text"]
    assert "map 0 near -10500, 870" in plan.actions[0].payload["objective_text"]


def test_discovery_returns_hostile_cluster_and_nearby_questgiver():
    result = discover_quest_candidates(player_guid=5405, settings=Settings(), client=FakeDatabase())
    assert result["player"]["level"] == 20
    assert result["candidates"][0]["target_entry"] == 449
    assert result["candidates"][0]["questgiver_entry"] == 234
