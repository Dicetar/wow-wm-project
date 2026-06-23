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


def test_memory_context_includes_only_active_body_and_content_free_exclusions():
    from wm.context.pack import build_memory_context_section

    section = build_memory_context_section([
        {
            "SteeringKey": "preference.name",
            "SteeringKind": "preference",
            "Body": "Call me Marker.",
            "Priority": "100",
            "Source": "player",
            "IsActive": "1",
            "MetadataJSON": '{"source_event_id": 5}',
            "UpdatedAt": "2026-06-23 12:00:00",
        },
        {
            "SteeringKey": "old.secret",
            "SteeringKind": "preference",
            "Body": "Do not leak this suppressed text.",
            "Priority": "10",
            "Source": "player",
            "IsActive": "0",
            "MetadataJSON": "{}",
            "UpdatedAt": "2026-06-23 12:01:00",
        },
        {
            "SteeringKey": "forgotten.fact",
            "SteeringKind": "preference",
            "Body": "",
            "Priority": "10",
            "Source": "player",
            "IsActive": "0",
            "MetadataJSON": '{"forgotten": true}',
            "UpdatedAt": "2026-06-23 12:02:00",
        },
    ])

    assert section["active"] == [
        {
            "steering_key": "preference.name",
            "steering_kind": "preference",
            "source": "player",
            "priority": 100,
            "updated_at": "2026-06-23 12:00:00",
            "body": "Call me Marker.",
            "metadata": {"source_event_id": 5},
        }
    ]
    assert section["source_evidence"][0]["state"] == "active"
    assert {entry["state"] for entry in section["excluded"]} == {"suppressed", "forgotten"}
    assert all("body" not in entry for entry in section["excluded"])
    assert "Do not leak" not in str(section)
