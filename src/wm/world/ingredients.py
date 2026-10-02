"""Read existing world ingredients near a fresh selected-character position."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any

from wm.autoplay.activities import read_activity_context
from wm.autoplay.quest_feasibility import _player_facts, _query
from wm.config import Settings
from wm.control._cli import write_json
from wm.db.mysql_cli import MysqlCliClient


class LootReader:
    def __init__(self, client: MysqlCliClient, settings: Settings) -> None:
        self.client, self.settings = client, settings
        self.cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self.truncated = False

    def preload(self, table: str, entries: list[int]) -> None:
        if table not in {"creature_loot_template", "skinning_loot_template", "gameobject_loot_template", "reference_loot_template"}:
            raise ValueError("Unsupported loot ingredient table")
        missing = sorted({int(entry) for entry in entries if entry > 0 and (table, entry) not in self.cache})[:200]
        if not missing:
            return
        rows = _query(self.client, self.settings, "world",
            "SELECT Entry, Item, `Reference`, Chance, QuestRequired, GroupId, MinCount, MaxCount "
            f"FROM {table} WHERE Entry IN ({','.join(map(str, missing))}) AND (LootMode & 1)<>0 "
            "ORDER BY Entry, GroupId, Item LIMIT 4000")
        self.truncated = self.truncated or len(rows) == 4000
        for entry in missing:
            self.cache[table, entry] = []
        for row in rows:
            self.cache[table, int(row["Entry"])].append(row)

    def preload_references(self) -> None:
        for _ in range(4):
            refs = {int(row["Reference"]) for rows in self.cache.values() for row in rows
                    if int(row["Reference"]) > 0 and ("reference_loot_template", int(row["Reference"])) not in self.cache}
            if not refs:
                break
            self.preload("reference_loot_template", list(refs))

    def rows(self, table: str, entry: int) -> list[dict[str, Any]]:
        if table not in {"creature_loot_template", "skinning_loot_template", "gameobject_loot_template", "reference_loot_template"}:
            raise ValueError("Unsupported loot ingredient table")
        key = (table, entry)
        if entry <= 0:
            return []
        if key not in self.cache:
            self.preload(table, [entry])
        return self.cache[key]

    def resolve(self, table: str, entry: int, trail: tuple[int, ...] = ()) -> list[dict[str, Any]]:
        rows = self.rows(table, entry)
        resolved = []
        for row in rows:
            if int(row["QuestRequired"]):
                continue
            chance = float(row["Chance"])
            group = int(row["GroupId"])
            if chance == 0 and group:
                members = [item for item in rows if int(item["GroupId"]) == group]
                zeros = sum(float(item["Chance"]) == 0 for item in members)
                chance = max(0, 100 - sum(max(0, float(item["Chance"])) for item in members)) / max(1, zeros)
            reference = int(row["Reference"])
            if reference:
                if len(trail) >= 4 or reference in trail:
                    continue
                for item in self.resolve("reference_loot_template", reference, (*trail, reference)):
                    resolved.append(dict(item, chance_hint=round(chance * item["chance_hint"] / 100, 2),
                                         reference_path=[reference, *item.get("reference_path", [])]))
            elif int(row["Item"]) > 0 and chance > 0:
                resolved.append({"item_entry": int(row["Item"]), "chance_hint": round(chance, 2),
                                 "min_count": int(row["MinCount"]), "max_count": int(row["MaxCount"]),
                                 "reference_path": []})
        return resolved[:100]


def scout_world(*, player_guid: int, settings: Settings, client: MysqlCliClient | None = None,
                radius: float = 1800, limit: int = 20, search: str = "") -> dict[str, Any]:
    if type(player_guid) is not int or player_guid <= 0:
        raise ValueError("Choose a character GUID")
    if not math.isfinite(radius) or not 0 < radius <= 3000:
        raise ValueError("radius must be between zero and 3000 yards")
    limit = max(1, min(int(limit), 40))
    db = client or MysqlCliClient()
    player = _player_facts(player_guid=player_guid, settings=settings, client=db)
    activity = read_activity_context(player_guid=player_guid, settings=settings, client=db)
    if not activity["inventory_fresh"] or not activity["phase_mask"]:
        raise ValueError("World scouting requires fresh native inventory/phase perception")
    x, y, phase, bit = player["x"], player["y"], activity["phase_mask"], player["faction_bit"]
    distance = f"POW(c.position_x-({x}),2)+POW(c.position_y-({y}),2)"
    near = (f"c.map={player['map_id']} AND (c.phaseMask & {phase})<>0 "
            f"AND (c.spawnMask & 1)<>0 AND {distance}<={radius * radius}")
    creatures = _query(db, settings, "world",
        "SELECT ct.entry, ct.name, ct.minlevel, ct.maxlevel, ct.npcflag, ct.lootid, ct.skinloot, "
        "ft.EnemyGroup, ft.FriendGroup, ft.FactionGroup, COUNT(*) AS spawn_count, "
        "AVG(c.position_x) AS x, AVG(c.position_y) AS y, MIN(c.position_z) AS z, "
        f"SQRT(MIN({distance})) AS distance FROM creature c "
        "JOIN creature_template ct ON ct.entry=c.id1 JOIN factiontemplate_dbc ft ON ft.ID=ct.faction "
        f"WHERE {near} GROUP BY ct.entry, ct.name, ct.minlevel, ct.maxlevel, ct.npcflag, ct.lootid, "
        "ct.skinloot, ft.EnemyGroup, ft.FriendGroup, ft.FactionGroup, "
        "FLOOR(c.position_x/300), FLOOR(c.position_y/300) ORDER BY distance LIMIT 80")
    npcs, enemies, sources = [], [], []
    reader = LootReader(db, settings)
    reader.preload("creature_loot_template", [int(row["lootid"]) for row in creatures])
    reader.preload("skinning_loot_template", [int(row["skinloot"]) for row in creatures])
    reader.preload_references()
    skills = {int(row["skill_id"]): int(row["value"]) for row in activity["professions"]}
    for row in creatures:
        hostile = bool(int(row["EnemyGroup"]) & bit)
        friendly = not hostile and bool((int(row["FriendGroup"]) | int(row["FactionGroup"])) & bit)
        identity = {"entry": int(row["entry"]), "name": str(row["name"]),
                    "x": round(float(row["x"]), 1), "y": round(float(row["y"]), 1),
                    "distance": round(float(row["distance"]), 1), "spawn_count": int(row["spawn_count"]),
                    "coordinate_kind": "cluster_centroid", "distance_kind": "nearest_spawn_2d"}
        flags = int(row["npcflag"])
        if friendly and flags:
            roles = [name for flag, name in ((2, "questgiver"), (16, "trainer"), (128, "vendor"), (65536, "banker")) if flags & flag]
            npcs.append(dict(identity, npc_flags=flags, roles=roles))
        if hostile:
            enemies.append(dict(identity, min_level=int(row["minlevel"]), max_level=int(row["maxlevel"])))
        if not hostile or flags or not max(1, player["level"] - 8) <= int(row["minlevel"]) <= player["level"] + 3:
            continue
        for field, table, kind in (("lootid", "creature_loot_template", "corpse_loot"),
                                   ("skinloot", "skinning_loot_template", "skinning")):
            entry = int(row[field])
            if not entry:
                continue
            skill_required = int(row["maxlevel"]) * 5 if kind == "skinning" else 0
            if kind == "skinning" and skills.get(393, 0) < skill_required:
                continue
            for item in reader.resolve(table, entry):
                sources.append(dict(item, source_kind=kind, source_entry=identity["entry"],
                                    source_name=identity["name"], x=identity["x"], y=identity["y"],
                                    spawn_count=identity["spawn_count"], distance=identity["distance"],
                                    loot_entry=entry, skill_required=skill_required))
    objects = _query(db, settings, "world",
        "SELECT gt.entry, gt.name, gt.type, gt.Data1 AS loot_entry, COUNT(*) AS spawn_count, "
        "AVG(c.position_x) AS x, AVG(c.position_y) AS y, "
        f"SQRT(MIN({distance})) AS distance FROM gameobject c "
        "JOIN gameobject_template gt ON gt.entry=c.id "
        f"WHERE {near} AND gt.type=3 GROUP BY gt.entry, gt.name, gt.type, gt.Data1, "
        f"FLOOR(c.position_x/300), FLOOR(c.position_y/300) ORDER BY distance LIMIT {limit}")
    reader.preload("gameobject_loot_template", [int(row["loot_entry"]) for row in objects])
    reader.preload_references()
    for row in objects:
        for item in reader.resolve("gameobject_loot_template", int(row["loot_entry"])):
            sources.append(dict(item, source_kind="gameobject", source_entry=int(row["entry"]),
                                source_name=str(row["name"]), x=round(float(row["x"]), 1),
                                y=round(float(row["y"]), 1), spawn_count=int(row["spawn_count"]),
                                distance=round(float(row["distance"]), 1), loot_entry=int(row["loot_entry"]),
                                interaction_requirements="unchecked; scouting only"))
    sources = sources[:1000]
    item_ids = sorted({row["item_entry"] for row in sources})
    items = _query(db, settings, "world",
        "SELECT entry, name, bonding, maxcount, class AS item_class, Quality AS quality, RequiredLevel AS required_level "
        f"FROM item_template WHERE entry IN ({','.join(map(str, item_ids))})") if item_ids else []
    identities = {int(row["entry"]): row for row in items}
    materials = []
    for source in sources:
        item = identities.get(source["item_entry"])
        if not item or int(item["bonding"]) == 4 or int(item["item_class"]) not in {0, 7}:
            continue
        material = dict(source, item_name=str(item["name"]), max_count=int(item["maxcount"]))
        if search and search.casefold() not in (material["item_name"] + " " + material["source_name"]).casefold():
            continue
        materials.append(material)
    materials.sort(key=lambda row: (row["source_kind"] == "gameobject", row["distance"], -row["chance_hint"]))
    match = lambda row: not search or search.casefold() in row["name"].casefold()
    return {"schema_version": "wm.world.ingredients.v1", "observed_at": datetime.now(timezone.utc).isoformat(),
            "player_guid": player_guid, "player": player, "phase_mask": phase, "radius": radius,
            "position_source": "fresh_native_presence", "inventory": activity["inventory"],
            "professions": activity["professions"], "npcs": [row for row in npcs if match(row)][:limit],
            "enemies": [row for row in enemies if match(row)][:limit], "materials": materials[:limit],
            "resource_objects": [row for row in objects if match(row)][:limit],
            "loot_rows_truncated": reader.truncated,
            "limitations": ["Persistent spawn data, not proof actors are alive or terrain is reachable.",
                            "Race-faction hint, not a reputation-sensitive NPC reaction proof.",
                            "Loot chance hints omit conditions and reference repetition; drops are not guaranteed.",
                            "Object locks/skills are not resolved; objects cannot yet drive automatic commissions.",
                            "Reference loot expands at most four levels; cyclic references are omitted."]}


def compact_ingredients(pack: dict[str, Any]) -> dict[str, Any]:
    return {key: pack.get(key) for key in ("observed_at", "player", "phase_mask", "position_source", "limitations")} | {
        "npcs": pack.get("npcs", [])[:5], "enemies": pack.get("enemies", [])[:5],
        "materials": pack.get("materials", [])[:8], "resource_objects": pack.get("resource_objects", [])[:5]}


def execute_read_tool(*, capability: str, args: dict[str, Any], player_guid: int,
                      settings: Settings, client: MysqlCliClient | None = None) -> dict[str, Any]:
    allowed = {"world_scout": {"radius", "limit", "search"},
               "world_lookup": {"kind", "entry", "search", "limit"},
               "loot_sources": {"entry", "search", "map_id", "limit"}}
    if capability not in allowed or not isinstance(args, dict) or set(args) - allowed[capability]:
        raise ValueError("Unsupported world read-tool arguments")
    limit = args.get("limit", 12)
    if type(limit) is not int or not 1 <= limit <= 40:
        raise ValueError("limit must be an integer between 1 and 40")
    search = args.get("search", "")
    if not isinstance(search, str) or len(search) > 100:
        raise ValueError("search must be literal text up to 100 characters")
    if capability == "world_scout":
        return scout_world(player_guid=player_guid, radius=args.get("radius", 1800), limit=limit,
                           search=search, settings=settings, client=client)
    if capability == "world_lookup":
        return lookup_templates(kind=args.get("kind", "creature"), entry=args.get("entry"), search=search,
                                limit=limit, settings=settings, client=client)
    entry = args.get("entry")
    if search.strip():
        matches = lookup_templates(kind="item", search=search, entry=entry,
                                   limit=max(2, limit), settings=settings, client=client)["rows"]
        if len(matches) != 1:
            return {"status": "ambiguous" if matches else "not_found", "search": search, "matches": matches,
                    "note": "Ask which item is intended; no item identity was guessed."}
        entry = int(matches[0]["entry"])
    return find_loot_sources(item_entry=entry, map_id=args.get("map_id"), limit=limit, settings=settings, client=client)


def compact_read_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("schema_version") == "wm.world.ingredients.v1":
        return compact_ingredients(result)
    return {key: value[:8] if isinstance(value, list) else value for key, value in result.items()}


def lookup_templates(*, kind: str, settings: Settings, entry: int | None = None,
                     search: str = "", limit: int = 20, client: MysqlCliClient | None = None) -> dict[str, Any]:
    limit = max(1, min(int(limit), 100))
    if entry is not None and (type(entry) is not int or entry <= 0):
        raise ValueError("entry must be a positive integer")
    if entry is None and not search.strip():
        raise ValueError("Specify an entry or search text")
    if kind == "shell":
        from dataclasses import asdict
        from wm.spells.shell_bank import load_spell_shell_bank
        bank = load_spell_shell_bank()
        rows = [asdict(shell) for shell in bank.shells
                if (entry is None or shell.spell_id == entry)
                and (not search or search.casefold() in (shell.label + " " + shell.behavior_kind).casefold())][:limit]
        return {"kind": kind, "rows": rows, "source": "repo_shell_bank",
                "runtime_truth": "UNKNOWN; metadata is not deployment, client-payload or behavior proof"}
    definitions = {
        "creature": ("creature_template", "entry", "name", "entry, name, minlevel, maxlevel, faction, npcflag, lootid, skinloot, ScriptName"),
        "gameobject": ("gameobject_template", "entry", "name", "entry, name, type, displayId, faction, flags, Data0, Data1, ScriptName"),
        "item": ("item_template", "entry", "name", "entry, name, class AS item_class, subclass, Quality, displayid, bonding, maxcount, stackable, RequiredLevel, spellid_1, spelltrigger_1"),
        "quest": ("quest_template", "ID", "LogTitle", "ID, LogTitle, LogDescription, QuestLevel, MinLevel, RewardMoney, RequiredNpcOrGo1, RequiredNpcOrGoCount1, RequiredItemId1, RequiredItemCount1"),
    }
    if kind not in definitions:
        raise ValueError("kind must be creature, gameobject, item, quest or shell")
    table, identity, name, fields = definitions[kind]
    conditions = []
    if entry is not None:
        conditions.append(f"{identity}={entry}")
    if search.strip():
        # Hex literal keeps text out of the SQL grammar, including quotes and wildcards.
        text = search.strip()[:100].encode("utf-8").hex()
        conditions.append(f"LOCATE(CONVERT(0x{text} USING utf8mb4), {name})>0")
    db = client or MysqlCliClient()
    rows = _query(db, settings, "world", f"SELECT {fields} FROM {table} WHERE {' AND '.join(conditions)} ORDER BY {identity} LIMIT {limit}")
    details = {}
    if entry is not None and kind in {"creature", "gameobject"}:
        spawn_table, spawn_entry = ("creature", "id1") if kind == "creature" else ("gameobject", "id")
        details["spawn_regions"] = _query(db, settings, "world",
            f"SELECT map, phaseMask AS phase_mask, spawnMask AS spawn_mask, COUNT(*) AS spawn_count "
            f"FROM {spawn_table} WHERE {spawn_entry}={entry} GROUP BY map, phaseMask, spawnMask ORDER BY spawn_count DESC LIMIT 20")
        details["spawn_samples"] = _query(db, settings, "world",
            f"SELECT guid AS spawn_id, map, position_x AS x, position_y AS y, position_z AS z, orientation, "
            f"spawntimesecs AS respawn_seconds, phaseMask AS phase_mask FROM {spawn_table} "
            f"WHERE {spawn_entry}={entry} ORDER BY guid LIMIT 10")
    if entry is not None and kind == "quest":
        details["npc_relations"] = _query(db, settings, "world",
            f"SELECT id AS npc_entry, 'starter' AS role FROM creature_queststarter WHERE quest={entry} "
            f"UNION ALL SELECT id AS npc_entry, 'ender' AS role FROM creature_questender WHERE quest={entry} LIMIT 20")
    return {"kind": kind, "rows": rows, **details, "source": "world_database",
            "runtime_truth": "Database ingredients, not proof of loaded/client-visible content"}


def find_loot_sources(*, item_entry: int, settings: Settings, map_id: int | None = None,
                      limit: int = 20, client: MysqlCliClient | None = None) -> dict[str, Any]:
    if type(item_entry) is not int or item_entry <= 0:
        raise ValueError("item_entry must be positive")
    if map_id is not None and (type(map_id) is not int or map_id < 0):
        raise ValueError("map_id must be nonnegative")
    db = client or MysqlCliClient()
    item = lookup_templates(kind="item", entry=item_entry, settings=settings, client=db)["rows"]
    if not item:
        raise ValueError("Item template was not found")
    references: set[int] = set()
    for _ in range(4):
        clause = f"Item={item_entry}"
        if references:
            clause += f" OR `Reference` IN ({','.join(map(str, sorted(references)))})"
        found = _query(db, settings, "world",
            f"SELECT DISTINCT Entry FROM reference_loot_template WHERE ({clause}) AND (LootMode & 1)<>0 LIMIT 200")
        new = {int(row["Entry"]) for row in found} - references
        if not new:
            break
        references.update(new)
    loot_clause = f"l.Item={item_entry}"
    if references:
        loot_clause += f" OR l.`Reference` IN ({','.join(map(str, sorted(references)))})"
    limit = max(1, min(int(limit), 50))
    sources = []
    for table, field, kind in (("creature_loot_template", "lootid", "corpse_loot"),
                               ("skinning_loot_template", "skinloot", "skinning"),
                               ("gameobject_loot_template", "Data1", "gameobject")):
        objects = kind == "gameobject"
        template, spawn, spawn_entry = ("gameobject_template", "gameobject", "id") if objects else ("creature_template", "creature", "id1")
        map_filter = f" AND s.map={map_id}" if map_id is not None else ""
        sources.extend(dict(row, source_kind=kind) for row in _query(db, settings, "world",
            "SELECT DISTINCT t.entry AS source_entry, t.name AS source_name, l.Entry AS loot_entry, "
            "l.Item, l.`Reference`, l.Chance, l.QuestRequired, l.GroupId, s.map, s.phaseMask AS phase_mask, "
            f"COUNT(*) AS spawn_count, AVG(s.position_x) AS x, AVG(s.position_y) AS y FROM {table} l "
            f"JOIN {template} t ON t.{field}=l.Entry JOIN {spawn} s ON s.{spawn_entry}=t.entry "
            f"WHERE ({loot_clause}) AND (l.LootMode & 1)<>0{map_filter} "
            + ("AND t.type=3 " if objects else "")
            + "GROUP BY t.entry, t.name, l.Entry, l.Item, l.`Reference`, l.Chance, l.QuestRequired, l.GroupId, s.map, s.phaseMask "
            + f"ORDER BY spawn_count DESC LIMIT {limit}"))
    sources.sort(key=lambda row: int(row["spawn_count"]), reverse=True)
    return {"item": item[0], "sources": sources[:limit], "reference_entries": sorted(references),
            "map_filter": map_id, "source": "world_loot_and_persistent_spawn_tables",
            "limitations": ["Four reference levels, bounded source rows; not an exhaustive drop database.",
                            "No live loot, condition, faction, skill or navigation guarantee.",
                            "Spawn counts describe persistent population, not currently living actors.",
                            "Object search covers chest-type templates; fishing, crafting and vendors are separate sources."]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scout current-world content ingredients without mutations.")
    parser.add_argument("command", choices=["scout", "lookup", "loot"], nargs="?", default="scout")
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--kind", choices=["creature", "gameobject", "item", "quest", "shell"])
    parser.add_argument("--entry", type=int)
    parser.add_argument("--map-id", type=int)
    parser.add_argument("--radius", type=float, default=1800)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--search", default="")
    parser.add_argument("--output-json")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    try:
        if args.command == "scout":
            result = scout_world(player_guid=args.player_guid, radius=args.radius, limit=args.limit,
                                 search=args.search, settings=settings)
        elif args.command == "lookup":
            result = lookup_templates(kind=args.kind, entry=args.entry, search=args.search, limit=args.limit, settings=settings)
        else:
            result = find_loot_sources(item_entry=args.entry, map_id=args.map_id, limit=args.limit, settings=settings)
    except (ValueError, RuntimeError) as exc:
        write_json({"ok": False, "status": "unavailable", "error": str(exc)}, Path(args.output_json) if args.output_json else None)
        return 1
    write_json(result, Path(args.output_json) if args.output_json else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
