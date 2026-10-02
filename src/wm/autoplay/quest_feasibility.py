"""Conservative live-world checks for automatically published kill quests."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient


ALLIANCE_RACES = {1, 3, 4, 7, 11}
HORDE_RACES = {2, 5, 6, 8, 10}


def _query(client: MysqlCliClient, settings: Settings, database: str, sql: str) -> list[dict[str, Any]]:
    world = database == "world"
    return client.query(
        host=settings.world_db_host if world else settings.char_db_host,
        port=settings.world_db_port if world else settings.char_db_port,
        user=settings.world_db_user if world else settings.char_db_user,
        password=settings.world_db_password if world else settings.char_db_password,
        database=settings.world_db_name if world else settings.char_db_name,
        sql=sql,
    )


def _player_facts(*, player_guid: int, settings: Settings, client: MysqlCliClient) -> dict[str, Any]:
    characters = _query(client, settings, "characters",
                        f"SELECT race FROM characters WHERE guid={int(player_guid)} LIMIT 1")
    presence = _query(client, settings, "world",
                      "SELECT Online, MapID, ZoneName, PosX, PosY, Level, "
                      "TIMESTAMPDIFF(SECOND, UpdatedAt, NOW()) AS AgeSeconds "
                      f"FROM wm_bridge_player_presence WHERE PlayerGUID={int(player_guid)} LIMIT 1")
    if len(characters) != 1 or len(presence) != 1:
        raise ValueError("selected character or live presence was not found")
    row = presence[0]
    if not int(row["Online"]) or row["AgeSeconds"] is None or int(row["AgeSeconds"]) > 15:
        raise ValueError("selected character has no fresh online presence")
    race = int(characters[0]["race"])
    faction_bit = 3 if race in ALLIANCE_RACES else 5 if race in HORDE_RACES else 0
    if not faction_bit:
        raise ValueError("character faction could not be resolved")
    if row["MapID"] is None or row["PosX"] is None or row["PosY"] is None or row["Level"] is None:
        raise ValueError("live position or level is unavailable")
    return {"map_id": int(row["MapID"]), "x": float(row["PosX"]), "y": float(row["PosY"]),
            "level": int(row["Level"]), "zone_name": str(row.get("ZoneName") or ""),
            "faction_bit": faction_bit, "presence_age_seconds": int(row["AgeSeconds"])}


def discover_quest_candidates(
    *, player_guid: int, settings: Settings, client: MysqlCliClient | None = None,
) -> dict[str, Any]:
    db = client or MysqlCliClient()
    player = _player_facts(player_guid=player_guid, settings=settings, client=db)
    map_id, bit, level = player["map_id"], player["faction_bit"], player["level"]
    x, y = player["x"], player["y"]
    clusters = _query(db, settings, "world", (
        "SELECT ct.entry AS target_entry, ct.name AS target_name, ct.minlevel AS target_level, "
        "COUNT(*) AS spawn_count, AVG(c.position_x) AS x, AVG(c.position_y) AS y "
        "FROM creature c JOIN creature_template ct ON ct.entry=c.id1 "
        "JOIN factiontemplate_dbc ft ON ft.ID=ct.faction "
        f"WHERE c.map={map_id} AND (c.phaseMask & 1)<>0 AND (c.spawnMask & 1)<>0 "
        f"AND (ft.EnemyGroup & {bit})<>0 "
        f"AND ct.npcflag=0 AND ct.minlevel BETWEEN {max(1, level-8)} AND {level+3} "
        f"AND ABS(c.position_x - {x:.2f})<=1800 AND ABS(c.position_y - {y:.2f})<=1800 "
        "GROUP BY ct.entry, ct.name, ct.minlevel, FLOOR(c.position_x/300), FLOOR(c.position_y/300) "
        "HAVING COUNT(*)>=3 ORDER BY COUNT(*) DESC LIMIT 40"
    ))
    questgivers = _query(db, settings, "world", (
        "SELECT ct.entry AS entry, ct.name AS name, c.position_x AS x, c.position_y AS y "
        "FROM creature c JOIN creature_template ct ON ct.entry=c.id1 "
        "JOIN factiontemplate_dbc ft ON ft.ID=ct.faction "
        f"WHERE c.map={map_id} AND (c.phaseMask & 1)<>0 AND (c.spawnMask & 1)<>0 "
        "AND (ct.npcflag & 2)<>0 "
        f"AND (ft.EnemyGroup & {bit})=0 "
        f"AND ((ft.FactionGroup & {bit})<>0 OR (ft.FriendGroup & {bit})<>0) "
        f"AND ABS(c.position_x - {x:.2f})<=1800 AND ABS(c.position_y - {y:.2f})<=1800 "
        f"ORDER BY POW(c.position_x - {x:.2f},2)+POW(c.position_y - {y:.2f},2) LIMIT 100"
    ))
    candidates = []
    for cluster in clusters:
        cx, cy = float(cluster["x"]), float(cluster["y"])
        nearby = [npc for npc in questgivers
                  if (float(npc["x"])-cx)**2 + (float(npc["y"])-cy)**2 <= 2000**2]
        if not nearby:
            continue
        npc = min(nearby, key=lambda row: (float(row["x"])-cx)**2 + (float(row["y"])-cy)**2)
        candidates.append({
            "target_entry": int(cluster["target_entry"]), "target_name": str(cluster["target_name"]),
            "target_level": int(cluster["target_level"]), "spawn_count": int(cluster["spawn_count"]),
            "x": round(cx, 1), "y": round(cy, 1), "map_id": map_id,
            "questgiver_entry": int(npc["entry"]), "questgiver_name": str(npc["name"]),
            "questgiver_x": round(float(npc["x"]), 1), "questgiver_y": round(float(npc["y"]), 1),
        })
    candidates.sort(key=lambda row: ((row["x"]-x)**2 + (row["y"]-y)**2, -row["spawn_count"]))
    return {"observed_at": datetime.now(timezone.utc).isoformat(), "player_guid": player_guid,
            "player": player, "candidates": candidates[:12]}


def assess_quest_plan(*, plan: Any, settings: Settings, client: MysqlCliClient | None = None) -> dict[str, Any]:
    if not plan.actions or plan.actions[0].kind != "quest_publish":
        raise ValueError("quest plan has no publish action")
    published = plan.actions[0].payload
    objective = published.get("objective") or {}
    if objective.get("kind") == "deliver":
        return assess_delivery_plan(plan=plan, settings=settings, client=client)
    target = int(objective.get("target_entry") or 0)
    count = int(objective.get("kill_count") or 0)
    ender = int(published.get("end_npc_entry") or 0)
    if target <= 0 or count <= 0 or ender <= 0:
        raise ValueError("quest needs an explicit kill target, count, and turn-in NPC")
    reward = published.get("reward") or {}
    if not (int(reward.get("money_copper") or 0) > 0 or reward.get("reward_item_entry") or reward.get("reward_spell_id")):
        raise ValueError("quest needs a deliverable reward before automatic publication")
    db = client or MysqlCliClient()
    player = _player_facts(player_guid=int(plan.player_guid), settings=settings, client=db)
    map_id, faction_bit = player["map_id"], player["faction_bit"]
    rows = _query(db, settings, "world", "SELECT ct.name, ct.minlevel, ct.maxlevel, ft.EnemyGroup "
                 "FROM creature_template ct JOIN factiontemplate_dbc ft ON ft.ID=ct.faction "
                 f"WHERE ct.entry={target} LIMIT 1")
    if len(rows) != 1 or int(rows[0]["EnemyGroup"]) & faction_bit == 0:
        raise ValueError("objective target is not verified hostile to the selected character")
    if abs(int(rows[0]["minlevel"]) - player["level"]) > 8:
        raise ValueError("objective target level is not suitable for this character")
    clusters = _query(db, settings, "world", "SELECT COUNT(*) AS n, AVG(position_x) AS x, AVG(position_y) AS y "
                      f"FROM creature WHERE id1={target} AND map={map_id} "
                      "AND (phaseMask & 1)<>0 AND (spawnMask & 1)<>0 "
                      f"AND ABS(position_x - {player['x']:.2f})<=1800 "
                      f"AND ABS(position_y - {player['y']:.2f})<=1800 "
                      "GROUP BY FLOOR(position_x/300), FLOOR(position_y/300) "
                      "ORDER BY COUNT(*) DESC LIMIT 1")
    spawns = clusters[0] if clusters else None
    available = int(spawns["n"]) if spawns else 0
    if available < count:
        raise ValueError(f"objective needs {count} kills but only {available} reachable map spawns exist")
    ender_spawns = _query(db, settings, "world", "SELECT COUNT(*) AS n FROM creature c "
                           "JOIN creature_template ct ON ct.entry=c.id1 "
                           "JOIN factiontemplate_dbc ft ON ft.ID=ct.faction "
                           f"WHERE c.id1={ender} AND c.map={map_id} "
                           "AND (c.phaseMask & 1)<>0 AND (c.spawnMask & 1)<>0 "
                           "AND (ct.npcflag & 2)<>0 "
                           f"AND (ft.EnemyGroup & {faction_bit})=0 "
                           f"AND ((ft.FactionGroup & {faction_bit})<>0 OR (ft.FriendGroup & {faction_bit})<>0) "
                           f"AND ABS(c.position_x - {float(spawns['x']):.2f})<=2000 "
                           f"AND ABS(c.position_y - {float(spawns['y']):.2f})<=2000")
    if not ender_spawns or int(ender_spawns[0]["n"]) < 1:
        raise ValueError("turn-in NPC has no reachable spawn on the selected character's map")
    if published.get("grant_mode") != "direct_grant":
        starter = int(published.get("start_npc_entry") or 0)
        starter_spawns = _query(db, settings, "world", "SELECT COUNT(*) AS n FROM creature "
                               f"WHERE id1={starter} AND map={map_id} AND (phaseMask & 1)<>0")
        if not starter_spawns or int(starter_spawns[0]["n"]) < 1:
            raise ValueError("quest starter has no reachable spawn")
    if reward.get("reward_item_entry") or reward.get("reward_spell_id"):
        raise ValueError("item and spell rewards require operator review of client/server truth")
    target_name = str(rows[0]["name"])
    published["objective_text"] = (
        f"Kill {count} {target_name} on map {map_id} near "
        f"{float(spawns['x']):.0f}, {float(spawns['y']):.0f}; return to "
        f"{published.get('questgiver_name') or 'the quest giver'} (NPC {ender})."
    )
    return {
        "target_entry": target, "target_name": target_name, "target_level": int(rows[0]["minlevel"]),
        "enemy_group": int(rows[0]["EnemyGroup"]), "player_faction_bit": faction_bit,
        "map_id": map_id, "spawn_count": available, "kill_count": count,
        "presence_age_seconds": player["presence_age_seconds"],
        "turn_in_entry": ender, "reward_money_copper": int(reward["money_copper"]),
    }


def discover_delivery_candidates(
    *, player_guid: int, settings: Settings, client: MysqlCliClient | None = None,
) -> dict[str, Any]:
    from wm.autoplay.activities import read_activity_context

    db = client or MysqlCliClient()
    player = _player_facts(player_guid=player_guid, settings=settings, client=db)
    activity = read_activity_context(player_guid=player_guid, settings=settings, client=db)
    candidates = []
    if not activity["inventory_fresh"] or not activity["phase_mask"]:
        return {"player": player, "candidates": [], "activity": activity}
    phase = activity["phase_mask"]
    npcs = _query(db, settings, "world", (
        "SELECT ct.entry, ct.name, c.position_x AS x, c.position_y AS y FROM creature c "
        "JOIN creature_template ct ON ct.entry=c.id1 JOIN factiontemplate_dbc ft ON ft.ID=ct.faction "
        f"WHERE c.map={player['map_id']} AND (c.phaseMask & {phase})<>0 AND (c.spawnMask & 1)<>0 "
        f"AND (ct.npcflag & 2)<>0 AND (ft.EnemyGroup & {player['faction_bit']})=0 "
        f"AND ((ft.FriendGroup & {player['faction_bit']})<>0 OR (ft.FactionGroup & {player['faction_bit']})<>0) "
        f"AND POW(c.position_x-({player['x']}),2)+POW(c.position_y-({player['y']}),2)<=1800*1800 "
        f"ORDER BY POW(c.position_x-({player['x']}),2)+POW(c.position_y-({player['y']}),2) LIMIT 1"
    ))
    if not npcs:
        return {"player": player, "candidates": [], "activity": activity}
    npc = npcs[0]
    inventory = {int(item["item_entry"]): int(item["count"]) for item in activity["inventory"]}
    for episode in activity["episodes"]:
        if episode.get("map_id") != player["map_id"] or inventory.get(episode["item_entry"], 0) < 3:
            continue
        items = _query(db, settings, "world", (
            "SELECT entry, name, bonding, maxcount, class FROM item_template "
            f"WHERE entry={int(episode['item_entry'])} LIMIT 1"
        ))
        if not items or int(items[0]["bonding"]) == 4 or int(items[0]["class"]) not in {0, 7}:
            continue
        item = items[0]
        count = min(10, inventory[episode["item_entry"]])
        if int(item["maxcount"]) > 0:
            count = min(count, int(item["maxcount"]))
        candidates.append({
            "item_entry": int(item["entry"]), "item_name": str(item["name"]), "item_count": count,
            "questgiver_entry": int(npc["entry"]), "questgiver_name": str(npc["name"]),
            "questgiver_x": round(float(npc["x"]), 1), "questgiver_y": round(float(npc["y"]), 1),
            "map_id": player["map_id"], "zone_name": player["zone_name"],
            "episode_key": episode["episode_key"], "gathering_kind": episode["kind"],
        })
    return {"player": player, "candidates": candidates[:8], "activity": activity,
            "observed_at": datetime.now(timezone.utc).isoformat()}


def assess_delivery_plan(*, plan: Any, settings: Settings, client: MysqlCliClient | None = None) -> dict[str, Any]:
    published = plan.actions[0].payload
    objective = published.get("objective") or {}
    count = int(objective.get("item_count") or 0)
    candidates = discover_delivery_candidates(player_guid=int(plan.player_guid), settings=settings, client=client)
    selected = next((row for row in candidates["candidates"]
                     if row["item_entry"] == objective.get("item_entry")
                     and row["questgiver_entry"] == published.get("end_npc_entry")), None)
    if selected is None or not 1 <= count <= selected["item_count"]:
        raise ValueError("delivery material, carried quantity or nearby friendly turn-in is no longer available")
    if published.get("start_npc_entry") != selected["questgiver_entry"]:
        raise ValueError("delivery starter must be the verified friendly turn-in NPC")
    reward = published.get("reward") or {}
    if reward.get("reward_item_entry") or reward.get("reward_spell_id") or int(reward.get("money_copper") or 0) <= 0:
        raise ValueError("automatic material deliveries require a money-only reward")
    directions = (f"Bring {count} {selected['item_name']} to {selected['questgiver_name']} "
                  f"in {selected['zone_name'] or 'the current area'} (map {selected['map_id']}) near "
                  f"{selected['questgiver_x']:.0f}, {selected['questgiver_y']:.0f}. "
                  "Items already owned count; the requested materials are consumed at turn-in.")
    published["objective_text"] = f"Deliver {count} {selected['item_name']}."
    published["request_items_text"] = directions
    published["objective"]["item_name"] = selected["item_name"]
    # Keep an offer notice identical to the final quest directions after rechecks.
    for action in plan.actions[1:]:
        if action.kind == "native_bridge_action" and action.payload.get("native_action_kind") == "world_announce_to_player":
            action.payload["payload"]["message"] = "Optional delivery available: " + directions
    return {"kind": "deliver", "item_entry": selected["item_entry"], "item_count": count,
            "turn_in_entry": selected["questgiver_entry"], "map_id": selected["map_id"],
            "inventory_age_seconds": candidates["activity"]["inventory_age_seconds"],
            "reward_money_copper": int(reward["money_copper"])}
