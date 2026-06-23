from __future__ import annotations

import argparse
import json
import re
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient


MEMORY_ACTIONS = {"pin", "suppress", "forget"}
_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def load_memory_entries(*, client: Any, settings: Settings, player_guid: int) -> list[dict[str, Any]]:
    return client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=(
            "SELECT CharacterGUID, SteeringKey, SteeringKind, Body, Priority, Source, IsActive, "
            "MetadataJSON, CreatedAt, UpdatedAt FROM wm_character_conversation_steering "
            f"WHERE CharacterGUID = {int(player_guid)} ORDER BY IsActive DESC, Priority DESC, UpdatedAt DESC"
        ),
    )


def memory_action_sql(*, player_guid: int, steering_key: str, action: str) -> str:
    key = _validated_key(steering_key)
    action_name = str(action).lower()
    if action_name not in MEMORY_ACTIONS:
        raise ValueError(f"Unsupported memory action: {action}")
    update = {
        "pin": "Priority = GREATEST(Priority, 100), IsActive = 1",
        "suppress": "IsActive = 0",
        "forget": "Body = '', IsActive = 0, MetadataJSON = JSON_OBJECT('forgotten', true)",
    }[action_name]
    return (
        "START TRANSACTION; "
        "INSERT INTO wm_character_memory_action "
        "(CharacterGUID, SteeringKey, ActionKind, PreviousActive, PreviousPriority) "
        f"SELECT CharacterGUID, SteeringKey, '{action_name}', IsActive, Priority "
        "FROM wm_character_conversation_steering "
        f"WHERE CharacterGUID = {int(player_guid)} AND SteeringKey = '{key}'; "
        "UPDATE wm_character_conversation_steering "
        f"SET {update} WHERE CharacterGUID = {int(player_guid)} AND SteeringKey = '{key}'; "
        "SELECT ROW_COUNT() AS affected_rows; "
        "COMMIT"
    )


def apply_memory_action(
    *,
    client: Any,
    settings: Settings,
    player_guid: int,
    steering_key: str,
    action: str,
    mode: str,
) -> dict[str, Any]:
    key = _validated_key(steering_key)
    rows = load_memory_entries(client=client, settings=settings, player_guid=int(player_guid))
    current = next((row for row in rows if str(row.get("SteeringKey") or "") == key), None)
    if current is None:
        return {"ok": False, "status": "not_found", "player_guid": int(player_guid), "steering_key": key}
    sql = memory_action_sql(player_guid=int(player_guid), steering_key=key, action=action)
    if mode == "dry-run":
        return {
            "ok": True,
            "status": "dry-run",
            "player_guid": int(player_guid),
            "steering_key": key,
            "action": str(action).lower(),
            "current": current,
        }
    if mode != "apply":
        raise ValueError("mode must be dry-run or apply")
    result_rows = client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=sql,
    )
    affected = _first_int(result_rows, "affected_rows")
    if affected != 1:
        return {
            "ok": False,
            "status": "not_applied",
            "player_guid": int(player_guid),
            "steering_key": key,
            "action": str(action).lower(),
            "affected_rows": affected,
        }
    return {
        "ok": True,
        "status": "applied",
        "player_guid": int(player_guid),
        "steering_key": key,
        "action": str(action).lower(),
        "affected_rows": affected,
    }


def _validated_key(value: str) -> str:
    key = str(value or "")
    if not _KEY_RE.fullmatch(key):
        raise ValueError("steering_key must contain only letters, digits, underscore, dot, colon, or hyphen")
    return key


def _first_int(rows: list[dict[str, Any]], key: str) -> int:
    if not rows:
        return 0
    raw = rows[0].get(key)
    if raw is None:
        return 0
    return int(raw)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or control scoped WM conversation memory.")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--player-guid", type=int, required=True)
    inspect.add_argument("--summary", action="store_true")
    for action in sorted(MEMORY_ACTIONS):
        command = sub.add_parser(action)
        command.add_argument("--player-guid", type=int, required=True)
        command.add_argument("--steering-key", required=True)
        command.add_argument("--mode", choices=("dry-run", "apply"), default="dry-run")
        command.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    if args.command == "inspect":
        payload = {
            "ok": True,
            "player_guid": int(args.player_guid),
            "memories": load_memory_entries(client=client, settings=settings, player_guid=int(args.player_guid)),
        }
    else:
        payload = apply_memory_action(
            client=client,
            settings=settings,
            player_guid=int(args.player_guid),
            steering_key=str(args.steering_key),
            action=str(args.command),
            mode=str(args.mode),
        )
    if args.summary:
        print(
            f"memory status={payload.get('status', 'inspected')} player={payload.get('player_guid')} "
            f"action={payload.get('action', '')} key={payload.get('steering_key', '')} "
            f"count={len(payload.get('memories') or [])} ok={str(bool(payload.get('ok'))).lower()}"
        )
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
