"""Tests for expanded SubjectCard schema — AreaContext, SubjectCluster, new fields."""
from __future__ import annotations

from wm.subjects.models import AreaContext, SubjectCard, SubjectCluster


def test_area_context():
    ac = AreaContext(zone_id=12, zone_name="Elwynn Forest", area_id=None, area_name=None)
    assert ac.zone_id == 12
    assert ac.zone_name == "Elwynn Forest"
    assert ac.area_id is None


def test_subject_cluster():
    sc = SubjectCluster(exact_entry=3100, archetype_key="wolf",
                        family_cluster="wolves_elwynn", local_pop_key=None)
    assert sc.exact_entry == 3100
    assert sc.archetype_key == "wolf"
    assert sc.family_cluster == "wolves_elwynn"


def test_subject_card_new_fields_have_defaults():
    card = SubjectCard(canonical_id="creature:3100", kind="creature", display_name="Young Wolf")
    assert card.creature_family is None
    assert card.npc_role_tags == []
    assert card.faction_name is None
    assert card.faction_alignment == "unknown"
    assert card.area_context is None
    assert card.settlement_role is None
    assert card.wm_notes == []
    assert card.cluster is None


def test_subject_card_new_fields_set():
    card = SubjectCard(
        canonical_id="creature:3100",
        kind="creature",
        display_name="Young Wolf",
        creature_family="Wolf",
        npc_role_tags=["questgiver"],
        faction_alignment="neutral",
        area_context=AreaContext(zone_id=12, zone_name="Elwynn Forest", area_id=None, area_name=None),
        settlement_role="wild",
        wm_notes=["spotted near goldshire"],
        cluster=SubjectCluster(exact_entry=3100, archetype_key="wolf",
                               family_cluster="wolves_elwynn", local_pop_key=None),
    )
    assert card.creature_family == "Wolf"
    assert card.npc_role_tags == ["questgiver"]
    assert card.faction_alignment == "neutral"
    assert card.area_context.zone_name == "Elwynn Forest"
    assert card.settlement_role == "wild"
    assert card.cluster.archetype_key == "wolf"


def test_subject_card_existing_fields_unchanged():
    card = SubjectCard(
        canonical_id="creature:69",
        kind="creature",
        display_name="Timber Wolf",
        archetype="Wolf",
        group_keys=["family:wolf", "type:beast"],
        role_tags=["world_subject"],
    )
    assert card.canonical_id == "creature:69"
    assert card.archetype == "Wolf"
    assert "family:wolf" in card.group_keys
    assert "world_subject" in card.role_tags


def test_to_dict_includes_new_fields():
    card = SubjectCard(
        canonical_id="creature:3100",
        kind="creature",
        display_name="Young Wolf",
        creature_family="Wolf",
        faction_alignment="neutral",
    )
    d = card.to_dict()
    assert d["creature_family"] == "Wolf"
    assert d["faction_alignment"] == "neutral"
