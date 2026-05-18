"""Living World zone mood: evaluates and persists mood state per zone/player."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

MoodKey = Literal["neutral", "tense", "hostile", "calm", "festive", "grieving"]

_DEED_MOOD_TIERS: tuple[tuple[int, MoodKey, int], ...] = (
    (0,  "neutral",  1),
    (5,  "tense",    2),
    (15, "hostile",  3),
    (40, "hostile",  5),
)


@dataclass(slots=True)
class ZoneMood:
    zone_id: int
    player_guid: int
    mood_key: MoodKey
    intensity: int      # 1–5

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "player_guid": self.player_guid,
            "mood_key": self.mood_key,
            "intensity": self.intensity,
        }


def _compute_mood(deed_total: int) -> tuple[MoodKey, int]:
    mood_key: MoodKey = "neutral"
    intensity = 1
    for threshold, mk, lvl in _DEED_MOOD_TIERS:
        if deed_total >= threshold:
            mood_key = mk
            intensity = lvl
    return mood_key, intensity


def evaluate_zone_mood(
    player_guid: int,
    zone_id: int,
    db_client: Any,
) -> ZoneMood:
    """Read V2 journal counters for the zone and return a ZoneMood.

    Persists the result to wm_zone_mood; degrades gracefully if db_client is None.
    """
    deed_total = 0
    if db_client is not None:
        rows = db_client.query(
            "SELECT SUM(count) AS total FROM wm_journal_counter "
            "WHERE player_guid = %s",
            (player_guid,),
        )
        if rows and rows[0].get("total") is not None:
            deed_total = int(rows[0]["total"])

    mood_key, intensity = _compute_mood(deed_total)
    zm = ZoneMood(zone_id=zone_id, player_guid=player_guid, mood_key=mood_key, intensity=intensity)

    if db_client is not None:
        try:
            db_client.execute(
                """
                INSERT INTO wm_zone_mood (zone_id, player_guid, mood_key, intensity)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE mood_key = VALUES(mood_key), intensity = VALUES(intensity),
                    evaluated_at = NOW()
                """,
                (zone_id, player_guid, mood_key, intensity),
            )
        except Exception:
            pass

    return zm
