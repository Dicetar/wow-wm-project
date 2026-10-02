from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.control._cli import build_live_coordinator, write_json
from wm.control.scene_play import ControlScene, SceneStep, build_scene_proposal
from wm.control.summary import native_request_refs_from_execution
from wm.db.mysql_cli import MysqlCliClient
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.payload_contract import validate_native_action_payload


def execute_action(*, action_kind: str, payload: dict[str, Any], player_guid: int,
                   run_key: str, mode: str, settings: Settings,
                   confirm_live_apply: bool = False) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    payload = dict(payload)
    kind = NATIVE_ACTION_KIND_BY_ID.get(action_kind)
    if kind is None or not kind.implemented:
        raise ValueError(f"Unsupported native action: {action_kind}")
    issues = validate_native_action_payload(action_kind=action_kind, payload=payload)
    if issues:
        raise ValueError("; ".join(issues))
    coordinates = [key in payload for key in ("x", "y", "z")]
    if any(coordinates) and not all(coordinates):
        raise ValueError("Exact placement requires x, y and z together")
    for key in ("x", "y", "z", "orientation"):
        if key in payload and (isinstance(payload[key], bool) or not math.isfinite(float(payload[key]))):
            raise ValueError(f"{key} must be a finite number")
        if key in payload:
            payload[key] = float(payload[key])
    if action_kind.startswith("world_spawn_"):
        if payload.get("object_type") not in {"creature", "gameobject"}:
            raise ValueError("object_type must be creature or gameobject")
        for key in ("entry", "spawn_id", "phase_mask", "respawn_seconds", "map_id"):
            if key in payload and (type(payload[key]) is not int or payload[key] < (0 if key in {"map_id", "respawn_seconds"} else 1)):
                raise ValueError(f"Invalid integer {key}")
    scene = ControlScene(scene_id="world_tools", description=str(payload.get("reason") or action_kind), steps=[])
    step = SceneStep(native_action_kind=action_kind, payload=payload, risk_level=kind.default_risk)
    proposal = build_scene_proposal(scene=scene, step=step, index=0, player_guid=player_guid,
                                    player_name=None, run_key=run_key,
                                    manual_reason=str(payload.get("reason") or "WM world tool"))
    execution = build_live_coordinator(settings).execute(
        proposal=proposal, mode=mode, confirm_live_apply=confirm_live_apply,
    )
    result = execution.to_dict()
    result["native_receipts"] = native_request_refs_from_execution(execution.applied)
    result["world_result"] = next((ref["result"] for ref in result["native_receipts"] if isinstance(ref.get("result"), dict)), {})
    return result


def inspect_spawns(*, player_guid: int, radius: float, limit: int,
                   settings: Settings, client: MysqlCliClient, position_source: str = "live") -> dict[str, Any]:
    if position_source not in {"live", "saved"}:
        raise ValueError("position_source must be live or saved")
    def query(database: str, port: int, sql: str) -> list[dict[str, Any]]:
        return client.query(host=settings.world_db_host if database == settings.world_db_name else settings.char_db_host,
                            port=port, user=settings.world_db_user if database == settings.world_db_name else settings.char_db_user,
                            password=settings.world_db_password if database == settings.world_db_name else settings.char_db_password,
                            database=database, sql=sql)
    players = query(settings.char_db_name, settings.char_db_port,
                    f"SELECT guid, name, map, position_x, position_y, position_z, orientation, online FROM characters WHERE guid={int(player_guid)}")
    if not players:
        raise ValueError("Character not found")
    player = players[0]
    if position_source == "live":
        presence = query(settings.world_db_name, settings.world_db_port,
            "SELECT Online, MapID, PosX, PosY, PosZ, Orientation, "
            "TIMESTAMPDIFF(SECOND, UpdatedAt, NOW()) AS age_seconds "
            f"FROM wm_bridge_player_presence WHERE PlayerGUID={int(player_guid)} LIMIT 1")
        if (not presence or not int(presence[0]["Online"]) or presence[0]["age_seconds"] is None
                or not 0 <= int(presence[0]["age_seconds"]) <= 15):
            raise ValueError("Fresh online native position is unavailable; use saved explicitly for offline inspection")
        live = presence[0]
        if any(live.get(key) is None for key in ("MapID", "PosX", "PosY", "PosZ")):
            raise ValueError("Native position is incomplete")
        player = dict(player, map=live["MapID"], position_x=live["PosX"], position_y=live["PosY"],
                      position_z=live["PosZ"], orientation=live["Orientation"], online=live["Online"])
    map_id = int(player["map"])
    x, y, z = (float(player[f"position_{axis}"]) for axis in "xyz")
    if not all(math.isfinite(value) for value in (x, y, z, radius)) or not 0 < radius <= 3000:
        raise ValueError("coordinates must be finite and radius must be between zero and 3000 yards")
    rows = []
    for table, template in (("creature", "creature_template"), ("gameobject", "gameobject_template")):
        entry = "id1" if table == "creature" else "id"
        distance = f"POW(s.position_x-({x}),2)+POW(s.position_y-({y}),2)+POW(s.position_z-({z}),2)"
        found = query(settings.world_db_name, settings.world_db_port,
                      f"SELECT s.guid AS spawn_id, s.{entry} AS entry, t.name, s.map, s.position_x AS x, "
                      f"s.position_y AS y, s.position_z AS z, s.orientation, s.spawntimesecs AS respawn_seconds, "
                      f"s.phaseMask AS phase_mask, SQRT({distance}) AS distance FROM {table} s "
                      f"LEFT JOIN {template} t ON t.entry=s.{entry} WHERE s.map={map_id} AND ({distance})<={radius * radius} "
                      f"ORDER BY distance LIMIT {max(1, min(int(limit), 200))}")
        rows.extend(dict(row, object_type=table) for row in found)
    rows.sort(key=lambda row: float(row["distance"]))
    return {"player": player, "position_source": "fresh_native_presence" if position_source == "live" else "character_database_last_saved",
            "spawns": rows[:max(1, min(limit, 200))],
            "note": "Persistent DB positions; spawn presence, phase visibility and terrain reachability are not proven."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and edit persistent world spawns or run typed native actions.")
    parser.add_argument("command", choices=["inspect", "execute"])
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--spec-json", type=Path)
    parser.add_argument("--run-key")
    parser.add_argument("--radius", type=float, default=100)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--position-source", choices=["live", "saved"], default="live")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--confirm-live-apply", action="store_true")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    try:
        if args.command == "inspect":
            result = inspect_spawns(player_guid=args.player_guid, radius=args.radius, limit=args.limit,
                                    settings=settings, client=MysqlCliClient(), position_source=args.position_source)
        else:
            if args.spec_json is None or not args.run_key:
                raise ValueError("execute requires --spec-json and --run-key")
            spec = json.loads(args.spec_json.read_text(encoding="utf-8-sig"))
            result = execute_action(action_kind=spec["action_kind"], payload=spec["payload"],
                                    player_guid=args.player_guid, run_key=args.run_key, mode=args.mode,
                                    settings=settings, confirm_live_apply=args.confirm_live_apply)
        write_json(result, args.output_json)
        return 0 if result.get("status", "dry-run") in {"dry-run", "applied"} else 1
    except (ValueError, KeyError) as exc:
        write_json({"ok": False, "error": str(exc)}, args.output_json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
