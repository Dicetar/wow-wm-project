"""Tests for wm.subjects.decoders — AzerothCore integer field tables."""
from __future__ import annotations

from wm.subjects.decoders import (
    decode_creature_family,
    decode_creature_type,
    decode_faction_alignment,
    decode_npc_flags,
    decode_rank,
)


def test_creature_type_known_values():
    assert decode_creature_type(1) == "Beast"
    assert decode_creature_type(7) == "Humanoid"
    assert decode_creature_type(6) == "Undead"
    assert decode_creature_type(9) == "Mechanical"


def test_creature_type_unknown_falls_back():
    assert decode_creature_type(999) == "Unknown(999)"


def test_npc_flags_single():
    assert "questgiver" in decode_npc_flags(0x2)
    assert "vendor" in decode_npc_flags(0x80)
    assert "innkeeper" in decode_npc_flags(0x10000)


def test_npc_flags_combined():
    tags = decode_npc_flags(0x82)  # questgiver | vendor
    assert "questgiver" in tags
    assert "vendor" in tags


def test_npc_flags_zero():
    assert decode_npc_flags(0) == []


def test_rank_decode():
    assert decode_rank(0) == "normal"
    assert decode_rank(1) == "elite"
    assert decode_rank(3) == "worldboss"
    assert decode_rank(4) == "rare"


def test_rank_unknown_falls_back():
    assert decode_rank(99) == "unknown(99)"


def test_creature_family_known():
    assert decode_creature_family(1) == "Wolf"
    assert decode_creature_family(2) == "Cat"


def test_creature_family_unknown_returns_none():
    assert decode_creature_family(9999) is None


def test_faction_alignment_known():
    assert decode_faction_alignment(1) == "alliance_friendly"
    assert decode_faction_alignment(3) == "horde_friendly"
    assert decode_faction_alignment(35) == "neutral"
    assert decode_faction_alignment(14) == "hostile_all"


def test_faction_alignment_unknown():
    result = decode_faction_alignment(99999)
    assert result == "unknown"
