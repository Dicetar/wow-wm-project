from __future__ import annotations

from wm.autoplay.spawn_args import SpawnArgsError, prepare_creature_spawn_args


class FakeResolver:
    def __init__(self, mapping):
        self._mapping = mapping

    def best_entry(self, name):
        return self._mapping.get(name.strip().lower())


def test_resolves_name_to_creature_entry():
    resolver = FakeResolver({"deer": 883})
    out = prepare_creature_spawn_args({"creature_name": "Deer"}, resolver=resolver)
    assert not isinstance(out, SpawnArgsError)
    assert out["creature_entry"] == 883
    assert out["resolved_from_name"] == "Deer"
    assert "position" not in out  # native verb spawns near the player


def test_explicit_creature_entry_is_trusted():
    out = prepare_creature_spawn_args({"creature_entry": 721}, resolver=FakeResolver({}))
    assert out["creature_entry"] == 721
    assert "resolved_from_name" not in out


def test_legacy_entry_key_also_accepted():
    out = prepare_creature_spawn_args({"entry": 721}, resolver=FakeResolver({}))
    assert out["creature_entry"] == 721


def test_unresolved_name_is_error():
    out = prepare_creature_spawn_args({"creature_name": "dragon"}, resolver=FakeResolver({"deer": 883}))
    assert isinstance(out, SpawnArgsError)
    assert "dragon" in out.reason


def test_missing_name_and_entry_is_error():
    out = prepare_creature_spawn_args({}, resolver=FakeResolver({}))
    assert isinstance(out, SpawnArgsError)


def test_passes_through_follow_hints():
    resolver = FakeResolver({"wolf": 100})
    out = prepare_creature_spawn_args(
        {"creature_name": "wolf", "follow_player": True, "distance": 5, "bogus": "x"},
        resolver=resolver,
    )
    assert out["creature_entry"] == 100
    assert out["follow_player"] is True
    assert out["distance"] == 5
    assert "bogus" not in out  # only known hints pass through
