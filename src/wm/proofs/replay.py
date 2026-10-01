from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from wm.autoplay.intent import IntentRejection, compile_intent
from wm.autoplay.intent_extract import extract_chat_intent
from wm.autoplay.tools import autoplay_tool_manifest
from wm.control.registry import ControlRegistry
from wm.control.validator import validate_control_proposal


SCHEMA_VERSION = "wm.proofs.replay.v1"


@dataclass(slots=True)
class FakeLmStudioResponder:
    """Deterministic LM Studio stand-in backed by one recorded response."""

    response: dict[str, Any]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def generate_json(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"parsed": dict(self.response), "request": {"response_format": {"type": "json_schema"}}}


@dataclass(slots=True)
class FakeNativeCoordinator:
    """Validate control proposals without executing or writing anything."""

    registry: ControlRegistry
    proposals: list[dict[str, Any]] = field(default_factory=list)

    def execute(self, proposal: Any) -> dict[str, Any]:
        validation = validate_control_proposal(proposal=proposal, registry=self.registry)
        native_kind = str(proposal.action.payload.get("native_action_kind") or "")
        result = {
            "status": "would_apply" if validation.ok else "rejected",
            "native_action_kind": native_kind,
            "validation_ok": validation.ok,
            "issues": [issue.model_dump(mode="json") for issue in validation.issues],
        }
        self.proposals.append(result)
        return result


def load_recording(path: str | Path) -> dict[str, Any]:
    recording_path = Path(path)
    with recording_path.open("r", encoding="utf-8") as handle:
        recording = json.load(handle)
    if not isinstance(recording, dict):
        raise ValueError("replay recording must be a JSON object")
    if recording.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"replay recording schema_version must be {SCHEMA_VERSION!r}")
    events = recording.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("replay recording must contain a non-empty events list")
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f"events[{index}] must be an object")
        if not isinstance(event.get("player_guid"), int):
            raise ValueError(f"events[{index}].player_guid must be an integer")
        if not str(event.get("message") or "").strip():
            raise ValueError(f"events[{index}].message is required")
        if not isinstance(event.get("llm_response"), dict):
            raise ValueError(f"events[{index}].llm_response must be an object")
    return recording


def replay_recording(*, recording: dict[str, Any], project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    modes = recording.get("verb_modes") if isinstance(recording.get("verb_modes"), dict) else None
    manifest = autoplay_tool_manifest(modes=modes)
    coordinator = FakeNativeCoordinator(ControlRegistry.load(root / "control"))
    known_memory: set[str] = set()
    event_results: list[dict[str, Any]] = []
    previous_reply: str | None = None

    for index, event in enumerate(recording["events"]):
        response = dict(event["llm_response"])
        responder = FakeLmStudioResponder(response)
        intent = extract_chat_intent(
            client=responder,
            player_guid=int(event["player_guid"]),
            message=str(event["message"]),
            manifest=manifest,
            identity=event.get("identity") if isinstance(event.get("identity"), dict) else None,
        )
        action_result: dict[str, Any] | None = None
        rejection: str | None = None
        if intent is not None:
            compiled = compile_intent(
                player_guid=int(event["player_guid"]),
                verb=str(intent["verb"]),
                args=intent.get("args"),
                modes=modes,
                reason=str(intent.get("reason") or "offline replay"),
            )
            if isinstance(compiled, IntentRejection):
                rejection = compiled.reason
            else:
                action_result = coordinator.execute(compiled.proposal)

        expected = event.get("expected") if isinstance(event.get("expected"), dict) else {}
        reply = str(response.get("reply") or "").strip()
        responsive = bool(reply or intent is not None)
        repeated_reply = bool(reply and previous_reply and reply.casefold() == previous_reply.casefold())
        if reply:
            previous_reply = reply

        memory_refs = {str(value) for value in response.get("memory_refs", []) if str(value)}
        expected_memory = {str(value) for value in expected.get("memory_refs", []) if str(value)}
        memory_reused = expected_memory.issubset(memory_refs & known_memory) if expected_memory else None
        remembered = event.get("remember") if isinstance(event.get("remember"), list) else []
        known_memory.update(str(value) for value in remembered if str(value))

        expected_action = str(expected.get("action_kind") or "") or None
        actual_action = action_result.get("native_action_kind") if action_result else None
        action_correct = (
            actual_action == expected_action and bool(action_result and action_result.get("validation_ok"))
            if expected_action
            else None
        )
        event_results.append({
            "index": index,
            "event_id": event.get("id", index + 1),
            "responsive": responsive,
            "reply": reply or None,
            "repeated_reply": repeated_reply,
            "intent": intent,
            "action": action_result,
            "rejection": rejection,
            "expected_action_kind": expected_action,
            "action_correct": action_correct,
            "expected_memory_refs": sorted(expected_memory),
            "memory_reused": memory_reused,
        })

    return _score(recording=recording, events=event_results, proposals=coordinator.proposals)


def replay_file(*, path: str | Path, project_root: str | Path) -> dict[str, Any]:
    return replay_recording(recording=load_recording(path), project_root=project_root)


def _score(
    *, recording: dict[str, Any], events: list[dict[str, Any]], proposals: list[dict[str, Any]]
) -> dict[str, Any]:
    responsiveness = _ratio(sum(bool(event["responsive"]) for event in events), len(events))
    expected_actions = [event for event in events if event["action_correct"] is not None]
    action_correctness = _ratio(
        sum(bool(event["action_correct"]) for event in expected_actions), len(expected_actions)
    )
    expected_memory = [event for event in events if event["memory_reused"] is not None]
    memory_reuse = _ratio(sum(bool(event["memory_reused"]) for event in expected_memory), len(expected_memory))
    spam_count = sum(bool(event["repeated_reply"]) for event in events)
    non_spam = _ratio(len(events) - spam_count, len(events))
    unsafe = [proposal for proposal in proposals if not proposal["validation_ok"]]
    safety = _ratio(len(proposals) - len(unsafe), len(proposals)) if proposals else 1.0
    scores = {
        "responsiveness": responsiveness,
        "safety": safety,
        "memory_reuse": memory_reuse,
        "action_correctness": action_correctness,
        "non_spam": non_spam,
    }
    applicable = [responsiveness, safety, non_spam]
    if expected_actions:
        applicable.append(action_correctness)
    if expected_memory:
        applicable.append(memory_reuse)
    passed = not unsafe and all(score == 1.0 for score in applicable)
    return {
        "schema_version": "wm.proofs.replay.result.v1",
        "recording_name": str(recording.get("name") or "unnamed"),
        "passed": passed,
        "scores": scores,
        "counts": {
            "events": len(events),
            "proposals": len(proposals),
            "unsafe_proposals": len(unsafe),
            "repeated_replies": spam_count,
            "expected_actions": len(expected_actions),
            "expected_memory_reuses": len(expected_memory),
        },
        "events": events,
    }


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 1.0
