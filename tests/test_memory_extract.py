from __future__ import annotations

from typing import Any

from wm.autoplay.memory_extract import extract_memory_note


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


def test_extract_durable_preference_returns_typed_note():
    client = FakeJsonClient({
        "remember": True,
        "steering_key": "Prefers Undead Foes",
        "steering_kind": "preferred_theme",
        "body": "Astel prefers fighting undead enemies.",
        "reason": "stated preference",
    })
    note = extract_memory_note(client=client, player_guid=5408, message="I love hunting undead.")
    assert note is not None
    assert note["steering_key"] == "prefers_undead_foes"  # slugified
    assert note["steering_kind"] == "preferred_theme"
    assert note["body"] == "Astel prefers fighting undead enemies."
    assert note["source"] == "conversation"


def test_ordinary_chat_remembers_nothing():
    client = FakeJsonClient({"remember": False, "steering_key": "", "steering_kind": "", "body": "", "reason": "small talk"})
    assert extract_memory_note(client=client, player_guid=5408, message="hello there") is None


def test_unknown_kind_falls_back_to_preference():
    client = FakeJsonClient({
        "remember": True,
        "steering_key": "calls_self_ser",
        "steering_kind": "totally_made_up",
        "body": "Address the player as Ser Astel.",
        "reason": "x",
    })
    note = extract_memory_note(client=client, player_guid=5408, message="Call me Ser Astel.")
    assert note is not None
    assert note["steering_kind"] == "player_preference"


def test_missing_key_or_body_returns_none():
    client = FakeJsonClient({"remember": True, "steering_key": "", "steering_kind": "player_fact", "body": "x", "reason": ""})
    assert extract_memory_note(client=client, player_guid=5408, message="...") is None
    client2 = FakeJsonClient({"remember": True, "steering_key": "k", "steering_kind": "player_fact", "body": "  ", "reason": ""})
    assert extract_memory_note(client=client2, player_guid=5408, message="...") is None


def test_client_failure_returns_none():
    client = FakeJsonClient(None, raise_exc=True)
    assert extract_memory_note(client=client, player_guid=5408, message="remember this") is None


def test_body_is_clamped():
    client = FakeJsonClient({
        "remember": True,
        "steering_key": "k",
        "steering_kind": "player_fact",
        "body": "x" * 400,
        "reason": "",
    })
    note = extract_memory_note(client=client, player_guid=5408, message="...")
    assert note is not None
    assert len(note["body"]) == 240
