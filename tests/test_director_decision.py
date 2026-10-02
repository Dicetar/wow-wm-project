from types import SimpleNamespace
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
         patch.object(service, "_chat_reply", return_value={"message": "I will consider it."}) as legacy_reply, \
         patch.object(service, "_send_chat_reply", return_value={"ok": True}) as legacy_send, \
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
    legacy_reply.assert_not_called()
    legacy_send.assert_not_called()


def test_director_chat_quest_failure_preserves_retryability(tmp_path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    service = AutoplayService(store=store, panel_state=panel)
    event = {"event_type": "wm_chat", "event_value": "Make a quest",
             "player_guid": 5408, "source_event_key": "test:request:retry", "occurred_at": utc_now_iso()}
    decision = DirectorDecision("propose_content", "quest", {}, "player asked", "")
    with patch.object(service, "_chat_world_context", return_value={}), \
         patch.object(service, "_decide_director_chat", return_value=decision), \
         patch.object(service, "_generate_for_opportunity",
                      return_value={"ok": False, "retryable": True, "reason": "candidate_discovery_failed"}), \
         patch.object(service, "_capture_conversation_memory"):
        result = service._reply_to_chat_event(
            control_config={"durable_director_enabled": True, "durable_director_player_guid": 5408},
            settings=Settings(), session={"character_guid": 5408}, event_payload=event,
        )
    assert result["ok"] is False
    assert result["retryable"] is True


def test_director_auto_action_requires_active_saved_policy(tmp_path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    service = AutoplayService(store=store, panel_state=panel)
    compiled = SimpleNamespace(verb="world_announce_to_player", risk="low")
    with patch("wm.autoplay.director_work.DirectorWorkLedger") as ledger:
        result = service._apply_durable_director_intent(
            settings=Settings(), player_guid=5408, compiled=compiled,
            source_event_key="event:1", source_event_at=utc_now_iso(),
            source_message="hello", dry_run=SimpleNamespace(status="dry-run"),
        )
    assert result["reason"] == "director_scope_or_policy_inactive"
    ledger.assert_not_called()


def test_director_rejects_uncutover_verb_before_legacy_executor(tmp_path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    service = AutoplayService(store=store, panel_state=panel)
    with patch.object(service, "_control_coordinator") as coordinator:
        result = service._handle_intent(
            settings=Settings(),
            control_config={"durable_director_enabled": True},
            player_guid=5408,
            intent={"verb": "creature_spawn", "args": {"name": "Unknown"}},
            source_message="Spawn something", source_event_key="event:other",
            source_event_at=utc_now_iso(),
        )
    assert result["reason"] == "director_capability_unsupported"
    coordinator.assert_not_called()


def test_director_clarification_routes_through_scoped_intent_without_legacy_reply(tmp_path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    service = AutoplayService(store=store, panel_state=panel)
    event = {"event_type": "wm_chat", "event_value": "Make something",
             "player_guid": 5408, "source_event_key": "test:request:clarify", "occurred_at": utc_now_iso()}
    decision = DirectorDecision("ask_clarification", "", {}, "unclear", "Which target?")
    with patch.object(service, "_chat_world_context", return_value={"speaker": {"guid": 5408}}), \
         patch.object(service, "_decide_director_chat", return_value=decision), \
         patch.object(service, "_chat_reply") as legacy_reply, \
         patch.object(service, "_send_chat_reply") as legacy_send, \
         patch.object(service, "_speak") as legacy_speak, \
         patch.object(service, "_capture_conversation_memory"), \
         patch.object(service, "_handle_intent", return_value={"intent": "applied"}) as action:
        result = service._reply_to_chat_event(
            control_config={"durable_director_enabled": True, "durable_director_player_guid": 5408},
            settings=Settings(), session={"character_guid": 5408}, event_payload=event,
        )
    assert result["decision"] == "ask_clarification"
    assert action.call_args.kwargs["intent"]["args"]["message"] == "Which target?"
    legacy_reply.assert_not_called()
    legacy_send.assert_not_called()
    legacy_speak.assert_not_called()


def test_director_action_unavailable_remains_retryable(tmp_path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    service = AutoplayService(store=store, panel_state=panel)
    event = {"event_type": "wm_chat", "event_value": "Tell me hello",
             "player_guid": 5408, "source_event_key": "test:action:retry", "occurred_at": utc_now_iso()}
    decision = DirectorDecision("propose_action", "world_announce_to_player",
                                {"message": "Hello"}, "player asked", "")
    with patch.object(service, "_chat_world_context", return_value={}), \
         patch.object(service, "_decide_director_chat", return_value=decision), \
         patch.object(service, "_handle_intent",
                      return_value={"intent": "unavailable", "reason": "director_scope_or_policy_inactive"}), \
         patch.object(service, "_capture_conversation_memory"):
        result = service._reply_to_chat_event(
            control_config={"durable_director_enabled": True, "durable_director_player_guid": 5408},
            settings=Settings(), session={"character_guid": 5408}, event_payload=event,
        )
    assert result["ok"] is False
    assert result["retryable"] is True
