from __future__ import annotations

from wm.targets.name_resolver import CreatureNameResolver, _is_junk
from wm.targets.resolver import CreatureTemplateRow, LookupStore


def _row(entry, name, rank=0, minlevel=1, maxlevel=1):
    return CreatureTemplateRow(
        entry=entry, name=name, subname=None, minlevel=minlevel, maxlevel=maxlevel,
        faction=0, npcflag=0, type=0, family=0, rank=rank, unit_class=1, gossip_menu_id=0,
    )


def _store(*rows):
    return LookupStore(creatures_by_entry={r.entry: r for r in rows})


def test_exact_name_beats_substring():
    store = _store(
        _row(883, "Deer"),
        _row(9999, "Young Deer"),
        _row(8888, "Deer Spirit"),
    )
    resolver = CreatureNameResolver(store)
    assert resolver.best_entry("deer") == 883
    matches = resolver.resolve("deer", limit=5)
    assert matches[0].entry == 883
    assert matches[0].match_tier == "exact"


def test_case_and_whitespace_insensitive():
    resolver = CreatureNameResolver(_store(_row(721, "Deer")))
    assert resolver.best_entry("  DEER ") == 721


def test_prefers_normal_rank_within_tier():
    store = _store(
        _row(100, "Wolf", rank=3),   # boss
        _row(101, "Wolf", rank=0),   # normal -> preferred
    )
    assert CreatureNameResolver(store).best_entry("wolf") == 101


def test_junk_rows_are_excluded():
    store = _store(
        _row(1, "Deer (Only GM can see it)"),
        _row(2, "Deer Trigger"),
        _row(3, "Deer"),
    )
    resolver = CreatureNameResolver(store)
    assert resolver.best_entry("deer") == 3
    entries = {m.entry for m in resolver.resolve("deer", limit=10)}
    assert entries == {3}


def test_word_match_when_no_exact():
    store = _store(_row(50, "Timber Wolf"), _row(51, "Wolf Handler"))
    resolver = CreatureNameResolver(store)
    matches = resolver.resolve("wolf", limit=5)
    assert {m.entry for m in matches} == {50, 51}
    assert all(m.match_tier == "word" for m in matches)


def test_no_match_returns_empty():
    resolver = CreatureNameResolver(_store(_row(1, "Deer")))
    assert resolver.resolve("dragon") == []
    assert resolver.best_entry("dragon") is None
    assert resolver.resolve("") == []


def test_is_junk_helper():
    assert _is_junk("Waypoint (Only GM can see it)")
    assert _is_junk("")
    assert not _is_junk("Deer")
