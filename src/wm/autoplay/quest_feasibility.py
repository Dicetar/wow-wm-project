"""Conservative live-world checks for automatically published kill quests."""
from __future__ import annotations

from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient


ALLIANCE_RACES = {1, 3, 4, 7, 11}
HORDE_RACES = {2, 5, 6, 8, 10}


def assess_quest_plan(*, plan: Any, settings: Settings, client: MysqlCliClient | None = None) -> dict[str, Any]:
    if not plan.actions or plan.actions[0].kind != "quest_publish":
        raise ValueError("quest plan has no publish action")
    published = plan.actions[0].payload
    objective = published.get("objective") or {}
    target = int(objective.get("target_entry") or 0)
    count = int(objective.get("kill_count") or 0)
    ender = int(published.get("end_npc_entry") or 0)
    if target <= 0 or count <= 0 or ender <= 0:
        raise ValueError("quest needs an explicit kill target, count, and turn-in NPC")
    reward = published.get("reward") or {}
    if not (int(reward.get("money_copper") or 0) > 0 or reward.get("reward_item_entry") or reward.get("reward_spell_id")):
        raise ValueError("quest needs a deliverable reward before automatic publication")
    db = client or MysqlCliClient()

    def query(database: str, sql: str) -> list[dict[str, Any]]:
        return db.query(
            host=settings.world_db_host if database == "world" else settings.char_db_host,
            port=settings.world_db_port if database == "world" else settings.char_db_port,
            user=settings.world_db_user if database == "world" else settings.char_db_user,
            password=settings.world_db_password if database == "world" else settings.char_db_password,
            database=settings.world_db_name if database == "world" else settings.char_db_name,
            sql=sql,
        )

    player = query("characters", f"SELECT map, race, level FROM characters WHERE guid={int(plan.player_guid)} LIMIT 1")
    if len(player) != 1:
        raise ValueError("selected character was not found")
    map_id, race = int(player[0]["map"]), int(player[0]["race"])
    faction_bit = 1 if race in ALLIANCE_RACES else 2 if race in HORDE_RACES else 0
    if not faction_bit:
        raise ValueError("character faction could not be resolved")
    rows = query("world", "SELECT ct.name, ct.minlevel, ct.maxlevel, ft.EnemyGroup "
                 "FROM creature_template ct JOIN factiontemplate_dbc ft ON ft.ID=ct.faction "
                 f"WHERE ct.entry={target} LIMIT 1")
    if len(rows) != 1 or int(rows[0]["EnemyGroup"]) & faction_bit == 0:
        raise ValueError("objective target is not verified hostile to the selected character")
    if abs(int(rows[0]["minlevel"]) - int(player[0]["level"])) > 15:
        raise ValueError("objective target level is not suitable for this character")
    spawns = query("world", "SELECT COUNT(*) AS n, MIN(position_x) AS x, MIN(position_y) AS y "
                   f"FROM creature WHERE id1={target} AND map={map_id} AND (phaseMask & 1)<>0")
    available = int(spawns[0]["n"]) if spawns else 0
    if available < count:
        raise ValueError(f"objective needs {count} kills but only {available} reachable map spawns exist")
    ender_spawns = query("world", "SELECT COUNT(*) AS n FROM creature "
                         f"WHERE id1={ender} AND map={map_id} AND (phaseMask & 1)<>0")
    if not ender_spawns or int(ender_spawns[0]["n"]) < 1:
        raise ValueError("turn-in NPC has no reachable spawn on the selected character's map")
    if published.get("grant_mode") != "direct_grant":
        starter = int(published.get("start_npc_entry") or 0)
        starter_spawns = query("world", "SELECT COUNT(*) AS n FROM creature "
                               f"WHERE id1={starter} AND map={map_id} AND (phaseMask & 1)<>0")
        if not starter_spawns or int(starter_spawns[0]["n"]) < 1:
            raise ValueError("quest starter has no reachable spawn")
    if reward.get("reward_item_entry") or reward.get("reward_spell_id"):
        raise ValueError("item and spell rewards require operator review of client/server truth")
    target_name = str(rows[0]["name"])
    published["objective_text"] = (
        f"Kill {count} {target_name} on map {map_id} near "
        f"{float(spawns[0]['x']):.0f}, {float(spawns[0]['y']):.0f}; return to "
        f"{published.get('questgiver_name') or 'the quest giver'} (NPC {ender})."
    )
    return {
        "target_entry": target, "target_name": target_name, "target_level": int(rows[0]["minlevel"]),
        "enemy_group": int(rows[0]["EnemyGroup"]), "player_faction_bit": faction_bit,
        "map_id": map_id, "spawn_count": available, "kill_count": count,
        "turn_in_entry": ender, "reward_money_copper": int(reward["money_copper"]),
    }
