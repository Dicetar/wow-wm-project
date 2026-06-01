from __future__ import annotations

from typing import Any

from wm.autoplay.scene_compose import (
    ComposedScene,
    SceneComposeError,
    extract_scene_request,
    validate_scene_steps,
)


class FakeResolver:
    def best_entry(self, name):
        return 68 if str(name).strip().lower() == "guard" else None


class FakeJsonClient:
    def __init__(self, parsed: Any, *, raise_exc: bool = False):
        self._parsed = parsed
        self._raise = raise_exc
        self.calls: list[dict[str, Any]] = []

    def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise:
            raise RuntimeError("boom")
        return {"parsed": self._parsed}


def _greet_steps():
    # Steps are linked to the spawned creature via a shared arc_key.
    return [
        {"native_action_kind": "creature_spawn", "payload": {"creature_name": "guard", "arc_key": "greet", "follow_player": True}, "expected_effect": "guard appears"},
        {"native_action_kind": "creature_say", "payload": {"arc_key": "greet", "text": "Well met, traveler."}, "expected_effect": "guard greets"},
        {"native_action_kind": "creature_emote", "payload": {"arc_key": "greet", "emote_id": 66}, "expected_effect": "salute"},
        {"native_action_kind": "creature_despawn", "payload": {"arc_key": "greet"}, "expected_effect": "guard leaves"},
    ]


def test_validate_resolves_spawn_and_accepts_clean_scene():
    steps = validate_scene_steps(_greet_steps(), resolver=FakeResolver())
    assert not isinstance(steps, SceneComposeError)
    assert steps[0]["native_action_kind"] == "creature_spawn"
    assert steps[0]["payload"]["creature_entry"] == 68  # name resolved
    assert len(steps) == 4


def test_rejects_unsupported_verb():
    steps = [{"native_action_kind": "zone_set_weather", "payload": {}}]
    out = validate_scene_steps(steps, resolver=FakeResolver())
    assert isinstance(out, SceneComposeError)
    assert "weather" in out.reason.lower()


def test_rejects_non_scene_verb():
    steps = [{"native_action_kind": "player_add_money", "payload": {"copper": 100}}]
    out = validate_scene_steps(steps, resolver=FakeResolver())
    assert isinstance(out, SceneComposeError)
    assert "scene-safe" in out.reason


def test_rejects_spawn_without_cleanup():
    steps = [
        {"native_action_kind": "creature_spawn", "payload": {"creature_name": "guard", "arc_key": "x"}},
        {"native_action_kind": "creature_say", "payload": {"arc_key": "x", "text": "hi"}},
    ]
    out = validate_scene_steps(steps, resolver=FakeResolver())
    assert isinstance(out, SceneComposeError)
    assert "cleanup" in out.reason


def test_temporary_spawn_satisfies_cleanup():
    steps = [
        {"native_action_kind": "creature_spawn", "payload": {"creature_name": "guard", "arc_key": "x", "duration_ms": 60000}},
        {"native_action_kind": "creature_say", "payload": {"arc_key": "x", "text": "hi"}},
    ]
    out = validate_scene_steps(steps, resolver=FakeResolver())
    assert not isinstance(out, SceneComposeError)


def test_rejects_unresolved_creature_name():
    steps = [
        {"native_action_kind": "creature_spawn", "payload": {"creature_name": "frobnicator", "duration_ms": 1000}},
        {"native_action_kind": "creature_despawn", "payload": {"arc_key": "x"}},
    ]
    out = validate_scene_steps(steps, resolver=FakeResolver())
    assert isinstance(out, SceneComposeError)
    assert "frobnicator" in out.reason


def test_rejects_empty_and_oversized():
    assert isinstance(validate_scene_steps([], resolver=FakeResolver()), SceneComposeError)
    big = [{"native_action_kind": "creature_emote", "payload": {"emote": 1}} for _ in range(9)]
    assert isinstance(validate_scene_steps(big, resolver=FakeResolver()), SceneComposeError)


def test_extract_returns_composed_scene():
    client = FakeJsonClient({"compose": True, "scene_name": "Greeting", "steps": _greet_steps(), "reason": "x"})
    scene = extract_scene_request(client=client, player_guid=5408, message="summon a guard to greet me", resolver=FakeResolver())
    assert isinstance(scene, ComposedScene)
    assert scene.scene_name == "Greeting"
    assert scene.steps[0]["payload"]["creature_entry"] == 68


def test_extract_returns_none_when_not_composing():
    client = FakeJsonClient({"compose": False, "scene_name": "", "steps": [], "reason": "chat"})
    assert extract_scene_request(client=client, player_guid=5408, message="hello", resolver=FakeResolver()) is None


def test_extract_returns_none_on_invalid_scene():
    bad = {"compose": True, "scene_name": "x", "steps": [{"native_action_kind": "zone_set_weather", "payload": {}}], "reason": "y"}
    client = FakeJsonClient(bad)
    assert extract_scene_request(client=client, player_guid=5408, message="make it rain", resolver=FakeResolver()) is None


def test_extract_returns_none_on_client_failure():
    client = FakeJsonClient(None, raise_exc=True)
    assert extract_scene_request(client=client, player_guid=5408, message="stage a scene", resolver=FakeResolver()) is None
