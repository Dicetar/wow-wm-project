"""Tests for ZoneMoodSection, LocalLegendSection, and pack versioning."""
from __future__ import annotations

from datetime import datetime


def test_zone_mood_section_dataclass():
    from wm.context.zone_mood import ZoneMoodSection
    s = ZoneMoodSection(zone_id=12, zone_name="Elwynn Forest",
                        dominant_activity="heavy_combat",
                        known_events=["player_killed_30_wolves"],
                        local_mood_label="wary")
    assert s.zone_id == 12
    assert "player_killed_30_wolves" in s.known_events


def test_local_legend_section_dataclass():
    from wm.context.legend import LocalLegendSection, LegendEntry
    entry = LegendEntry(narrative_key="wolf_purge_elwynn",
                        summary="Player slew 30 wolves", at=datetime.utcnow())
    section = LocalLegendSection(zone_id=12, legends=[entry])
    assert len(section.legends) == 1
    assert section.legends[0].narrative_key == "wolf_purge_elwynn"


def test_pack_version_field():
    from wm.context.versions import CURRENT_PACK_VERSION
    assert isinstance(CURRENT_PACK_VERSION, str)
    assert CURRENT_PACK_VERSION.startswith("wm.context_pack.v")
