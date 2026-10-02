"""Activity evidence reconstructed from the existing event log and live perception."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import EventStore


def _time(value: Any) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def summarize_activity(
    events: list[dict[str, Any]], *, player_guid: int, now: datetime | None = None,
    window_seconds: int = 900,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    selected = []
    seen = set()
    for event in events:
        stamp = _time(event.get("occurred_at"))
        key = str(event.get("source_event_key") or event.get("event_id") or "")
        if (event.get("player_guid") != player_guid or stamp is None or not key
                or not 0 <= (now - stamp).total_seconds() <= window_seconds or key in seen):
            continue
        seen.add(key)
        selected.append((stamp, event))
    selected.sort(key=lambda pair: pair[0])
    if not selected:
        return {"episodes": [], "observed_at": now.isoformat(), "player_guid": player_guid}
    # Do not blend activities from different places after the player moves.
    location = (selected[-1][1].get("map_id"), selected[-1][1].get("zone_id"))
    kills: dict[int, int] = {}
    materials: dict[tuple[str, int], dict[str, Any]] = {}
    for stamp, event in selected:
        if (event.get("map_id"), event.get("zone_id")) != location:
            continue
        if event.get("event_type") == "kill":
            target = int(event.get("subject_entry") or 0)
            kills[target] = kills.get(target, 0) + 1
        payload = (event.get("metadata") or {}).get("payload") or {}
        kind = payload.get("gathering_kind")
        if event.get("event_type") != "loot_item" or kind not in {"skinning", "mining", "herbalism", "fishing"}:
            continue
        item = int(payload.get("item_entry") or 0)
        count = int(payload.get("count") or 0)
        if item <= 0 or count <= 0:
            continue
        material = materials.setdefault((kind, item), {
            "kind": kind, "item_entry": item, "item_name": str(payload.get("item_name") or ""),
            "gathered_count": 0, "sources": set(), "event_keys": [],
            "started_at": stamp.isoformat(), "last_observed_at": stamp.isoformat(),
        })
        material["gathered_count"] += count
        key = str(event.get("source_event_key") or event.get("event_id"))
        source = str((event.get("metadata") or {}).get("subject_guid") or payload.get("loot_source_guid") or key)
        material["sources"].add(source)
        material["event_keys"].append(key)
        material["last_observed_at"] = stamp.isoformat()
    episodes = []
    for material in materials.values():
        sources = material.pop("sources")
        material["source_count"] = len(sources)
        material["map_id"], material["zone_id"] = location
        material["kill_count"] = sum(kills.values())
        material["kill_targets"] = kills
        material["episode_key"] = hashlib.sha256(
            f"{player_guid}:{material['kind']}:{material['item_entry']}:{material['event_keys'][0]}".encode()
        ).hexdigest()
        material["intent_inference"] = "Possibly gathering supplies; purpose is not confirmed."
        episodes.append(material)
    episodes.sort(key=lambda row: (row["source_count"], row["gathered_count"]), reverse=True)
    return {"episodes": episodes[:8], "observed_at": now.isoformat(), "player_guid": player_guid,
            "window_seconds": window_seconds, "event_sample_size": len(events),
            "history_note": "Bounded recent evidence, not a complete lifetime history."}


def read_activity_context(*, player_guid: int, settings: Settings, client: MysqlCliClient | None = None) -> dict[str, Any]:
    client = client or MysqlCliClient()
    events = EventStore(client=client, settings=settings).list_recent_events(
        event_class="observed", player_guid=player_guid, limit=300, newest_first=True,
    )
    context = summarize_activity([event.to_dict() for event in events], player_guid=player_guid)
    rows = client.query(
        host=settings.world_db_host, port=settings.world_db_port, user=settings.world_db_user,
        password=settings.world_db_password, database=settings.world_db_name,
        sql="SELECT PayloadJSON, TIMESTAMPDIFF(SECOND, UpdatedAt, NOW()) AS AgeSeconds "
            f"FROM wm_bridge_player_perception WHERE PlayerGUID={int(player_guid)} LIMIT 1",
    )
    age = int(rows[0]["AgeSeconds"]) if rows and rows[0].get("AgeSeconds") is not None else None
    payload = json.loads(rows[0]["PayloadJSON"]) if rows and age is not None and 0 <= age <= 30 else {}
    if not isinstance(payload, dict):
        payload = {}
    context["inventory"] = payload.get("inventory", [])
    context["professions"] = payload.get("professions", [])
    context["inventory_scope"] = payload.get("inventory_scope", "unavailable")
    context["inventory_fresh"] = isinstance(payload.get("inventory"), list)
    context["inventory_age_seconds"] = age
    context["phase_mask"] = int(payload.get("phase_mask") or 0)
    return context


def compact_activity_context(context: dict[str, Any]) -> dict[str, Any]:
    episodes = [{key: value for key, value in row.items() if key not in {"event_keys", "kill_targets"}}
                for row in context.get("episodes", [])[:8]]
    materials = {row["item_entry"] for row in episodes}
    return {
        "episodes": episodes,
        "inventory": [row for row in context.get("inventory", []) if row.get("item_entry") in materials][:8],
        "professions": context.get("professions", [])[:13],
        "inventory_fresh": context.get("inventory_fresh", False),
        "inventory_age_seconds": context.get("inventory_age_seconds"),
        "inventory_scope": context.get("inventory_scope"),
        "observed_at": context.get("observed_at"),
        "history_note": context.get("history_note"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m wm.autoplay.activities")
    parser.add_argument("--player-guid", required=True, type=int)
    args = parser.parse_args(argv)
    print(json.dumps(read_activity_context(player_guid=args.player_guid, settings=Settings.from_env()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
