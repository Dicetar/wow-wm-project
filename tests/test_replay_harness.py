from __future__ import annotations

import json
from pathlib import Path

import pytest

from wm.proofs.__main__ import main
from wm.proofs.replay import load_recording, replay_recording


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _recording() -> dict:
    return {
        "schema_version": "wm.proofs.replay.v1",
        "name": "chat-action-memory",
        "verb_modes": {"player_restore_health_power": "auto"},
        "events": [
            {
                "id": "remember-1",
                "player_guid": 5408,
                "message": "Call me captain.",
                "remember": ["preferred_title"],
                "llm_response": {"act": False, "verb": "", "args": {}, "reason": "chat", "reply": "Understood."},
            },
            {
                "id": "heal-1",
                "player_guid": 5408,
                "message": "Restore my health.",
                "llm_response": {
                    "act": True,
                    "verb": "player_restore_health_power",
                    "args": {"health_percent": 100},
                    "reason": "clear request",
                    "reply": "At once, captain.",
                    "memory_refs": ["preferred_title"],
                },
                "expected": {
                    "action_kind": "player_restore_health_power",
                    "memory_refs": ["preferred_title"],
                },
            },
        ],
    }


def test_replay_scores_real_intent_compile_and_control_validation():
    result = replay_recording(recording=_recording(), project_root=PROJECT_ROOT)

    assert result["passed"] is True
    assert result["scores"] == {
        "responsiveness": 1.0,
        "safety": 1.0,
        "memory_reuse": 1.0,
        "action_correctness": 1.0,
        "non_spam": 1.0,
    }
    assert result["events"][1]["action"]["status"] == "would_apply"


def test_replay_rejects_uncontracted_or_disabled_action():
    recording = _recording()
    recording["events"] = [{
        "player_guid": 5408,
        "message": "Teleport me.",
        "llm_response": {
            "act": True,
            "verb": "player_teleport",
            "args": {"map_id": 0, "x": 1, "y": 2, "z": 3},
            "reason": "request",
            "reply": "Trying.",
        },
        "expected": {"action_kind": "player_teleport"},
    }]

    result = replay_recording(recording=recording, project_root=PROJECT_ROOT)

    assert result["passed"] is False
    assert result["events"][0]["intent"] is None
    assert result["scores"]["action_correctness"] == 0.0
    assert result["counts"]["proposals"] == 0


def test_replay_flags_repeated_replies_as_spam():
    recording = _recording()
    recording["events"][1]["llm_response"]["reply"] = "Understood."

    result = replay_recording(recording=recording, project_root=PROJECT_ROOT)

    assert result["passed"] is False
    assert result["counts"]["repeated_replies"] == 1
    assert result["scores"]["non_spam"] == 0.5


def test_load_recording_rejects_wrong_schema(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "wrong", "events": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        load_recording(path)


def test_replay_cli_returns_success_and_prints_json(tmp_path: Path, capsys):
    path = tmp_path / "recording.json"
    path.write_text(json.dumps(_recording()), encoding="utf-8")

    code = main(["replay", str(path), "--project-root", str(PROJECT_ROOT), "--json"])

    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["passed"] is True
