from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ZoneMoodSection:
    zone_id: int
    zone_name: str
    dominant_activity: str | None       # "heavy_combat", "peaceful", "contested"
    known_events: list[str]             # ["player_killed_30_wolves", "nemesis_spawned"]
    local_mood_label: str | None        # "hostile towards player", "wary", "grateful"


def stub_zone_mood(zone_id: int, zone_name: str) -> ZoneMoodSection:
    """Returns an empty stub when wm_zone_mood table is not yet populated."""
    return ZoneMoodSection(zone_id=zone_id, zone_name=zone_name,
                           dominant_activity=None, known_events=[], local_mood_label=None)
