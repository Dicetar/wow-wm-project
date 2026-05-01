from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


@dataclass(slots=True)
class JourneyEligibilitySnapshot:
    character_guid: int | None
    status: str
    profile_name: str | None = None
    active_arc_keys: list[str] = field(default_factory=list)
    completed_arc_keys: list[str] = field(default_factory=list)
    unlock_refs: list[str] = field(default_factory=list)
    reward_refs: list[str] = field(default_factory=list)
    steering_keys: list[str] = field(default_factory=list)
    prompt_kinds: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)

    @property
    def ready_for_arc_factory(self) -> bool:
        return self.status == "WORKING" and self.character_guid is not None and not self.blocked_reasons

    def has_active_arc(self, arc_key: str) -> bool:
        return str(arc_key) in set(self.active_arc_keys)

    def has_unlock(self, unlock_kind: str, unlock_id: int | str) -> bool:
        return _ref(unlock_kind, unlock_id) in set(self.unlock_refs)

    def has_reward(self, reward_kind: str, template_id: int | str) -> bool:
        return _ref(reward_kind, template_id) in set(self.reward_refs)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ready_for_arc_factory"] = self.ready_for_arc_factory
        return payload


def build_journey_eligibility(character_state: Any) -> JourneyEligibilitySnapshot:
    state = _as_mapping(character_state)
    if not state:
        return JourneyEligibilitySnapshot(
            character_guid=None,
            status="PARTIAL",
            blocked_reasons=["character_state_missing"],
        )

    profile = _as_mapping(state.get("profile"))
    character_guid = _int_or_none(profile.get("character_guid") or state.get("character_guid"))
    status = str(state.get("status") or ("WORKING" if profile else "PARTIAL"))
    blocked_reasons = [str(note) for note in state.get("notes") or [] if str(note).strip()]
    if not profile:
        blocked_reasons.append("profile_missing")

    arc_states = [_as_mapping(item) for item in state.get("arc_states") or []]
    unlocks = [_as_mapping(item) for item in state.get("unlocks") or []]
    rewards = [_as_mapping(item) for item in state.get("rewards") or state.get("reward_instances") or []]
    steering = [_as_mapping(item) for item in state.get("conversation_steering") or []]
    prompts = [_as_mapping(item) for item in state.get("prompt_queue") or []]

    return JourneyEligibilitySnapshot(
        character_guid=character_guid,
        status=status,
        profile_name=_str_or_none(profile.get("character_name")),
        active_arc_keys=sorted(
            {
                str(arc.get("arc_key"))
                for arc in arc_states
                if arc.get("arc_key") and str(arc.get("status") or "active") == "active"
            }
        ),
        completed_arc_keys=sorted(
            {
                str(arc.get("arc_key"))
                for arc in arc_states
                if arc.get("arc_key") and str(arc.get("status") or "") == "completed"
            }
        ),
        unlock_refs=sorted(
            {
                _ref(unlock.get("unlock_kind"), unlock.get("unlock_id"))
                for unlock in unlocks
                if unlock.get("unlock_kind") not in (None, "") and unlock.get("unlock_id") not in (None, "")
            }
        ),
        reward_refs=sorted(
            {
                _ref(reward.get("reward_kind"), reward.get("template_id"))
                for reward in rewards
                if reward.get("reward_kind") not in (None, "") and reward.get("template_id") not in (None, "")
            }
        ),
        steering_keys=sorted(
            {
                str(note.get("steering_key"))
                for note in steering
                if note.get("steering_key") and _truthy(note.get("is_active", True))
            }
        ),
        prompt_kinds=sorted(
            {
                str(prompt.get("prompt_kind"))
                for prompt in prompts
                if prompt.get("prompt_kind") and not _truthy(prompt.get("is_consumed", False))
            }
        ),
        blocked_reasons=sorted(set(blocked_reasons)),
    )


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    return {}


def _ref(kind: Any, ident: Any) -> str:
    return f"{str(kind)}:{str(ident)}"


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if value in (None, ""):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
