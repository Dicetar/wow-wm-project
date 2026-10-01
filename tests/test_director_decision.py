from unittest.mock import patch

import pytest

from wm.autoplay.decision import DirectorDecision, decide_request
from wm.autoplay.service import AutoplayService
from wm.autoplay.state import AutoplayStateStore, utc_now_iso
from wm.config import Settings
from wm.panel.state import PanelState


class FakeClient:
    def __init__(self, payload, response_type="json_schema"):
        self.payload = payload
        self.response_type = response_type

    def generate_json(self, **kwargs):
        return {"parsed": self.payload, "request": {"response_format": {"type": self.response_type}}}


def _payload(outcome="propose_content", capability="quest", args=None):
    return {"outcome": outcome, "capability": capability, "args": args or {},
            "reason": "player asked", "question": ""}


def test_director_decision_accepts_only_schema_bound_output():
    evidence = {"selected_character": {"guid": 5408}, "capabilities": ["quest"]}
    assert decide_request(client=FakeClient(_payload()), evidence=evidence).outcome == "propose_content"
    with pytest.raises(ValueError, match="schema-constrained"):
        decide_request(client=FakeClient(_payload(), "text"), evidence=evidence)
    with pytest.raises(ValueError, match="missing required"):
        decide_request(client=FakeClient({"outcome": "no_action"}), evidence=evidence)


def test_director_chat_quest_request_creates_draft_without_direct_apply(tmp_path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    service = AutoplayService(store=store, panel_state=panel)
    event = {"event_type": "wm_chat", "event_value": "Make me a quest to hunt bandits",
             "player_guid": 5408, "source_event_key": "test:request:1", "occurred_at": utc_now_iso()}
    decision = DirectorDecision("propose_content", "quest", {}, "player asked", "")
    with patch.object(service, "_chat_world_context", return_value={"speaker": {"guid": 5408}}), \
         patch.object(service, "_decide_director_chat", return_value=decision), \
         patch.object(service, "_chat_reply", return_value={"message": "I will consider it."}), \
         patch.object(service, "_send_chat_reply", return_value={"ok": True}), \
         patch.object(service, "_capture_conversation_memory"), \
         patch.object(service, "_generate_for_opportunity", return_value={"ok": True, "draft_id": "draft-1"}) as generate, \
         patch.object(service, "_handle_scene_request") as scene, \
         patch.object(service, "_handle_intent") as action:
        result = service._reply_to_chat_event(
            control_config={"durable_director_enabled": True, "durable_director_player_guid": 5408},
            settings=Settings(), session={"character_guid": 5408}, event_payload=event,
        )
    assert result["content_result"]["draft_id"] == "draft-1"
    assert generate.call_args.kwargs["opportunity"]["player_request"] == event["event_value"]
    scene.assert_not_called()
    action.assert_not_called()
