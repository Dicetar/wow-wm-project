"""Utilities for assembling V2 context pack sections into a pack dict."""
from __future__ import annotations

from typing import Any

from wm.context.versions import CURRENT_PACK_VERSION
from wm.context.zone_mood import stub_zone_mood
from wm.context.legend import LocalLegendSection


def enrich_pack_with_v2_sections(
    pack: dict,
    *,
    player_guid: int,
    zone_id: int | None = None,
    zone_name: str = "",
    db_client: Any = None,
) -> dict:
    """Add version, zone_mood, and local_legends fields to a pack dict in-place."""
    pack["version"] = CURRENT_PACK_VERSION

    zone_mood_data: dict = {"mood_key": "neutral", "intensity": 1}
    if db_client is not None and zone_id is not None:
        try:
            from wm.living.zone_mood import evaluate_zone_mood
            zm = evaluate_zone_mood(player_guid, zone_id, db_client)
            zone_mood_data = {"mood_key": zm.mood_key, "intensity": zm.intensity}
        except Exception:
            pass

    pack["zone_mood"] = zone_mood_data

    legend_data: list = []
    if db_client is not None:
        try:
            rows = db_client.query(
                "SELECT event_type, data_json, at FROM wm_journal_special_event "
                "WHERE player_guid = %s ORDER BY at DESC LIMIT 5",
                (player_guid,),
            )
            legend_data = [
                {"event_type": r["event_type"], "at": str(r.get("at"))}
                for r in rows
            ]
        except Exception:
            pass

    pack["local_legends"] = legend_data
    return pack
