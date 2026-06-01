"""Ambient narration cues for the Live Reaction Layer (Phase 2).

WM occasionally narrates notable in-game moments so the world feels alive even
when the player is silent. This module is the pure, deterministic part: it
decides which events are narration-worthy and shapes the LLM prompt. The
service layer owns throttling (cooldown), the LLM text call, sanitization, and
speaking the line through the existing low-risk ``world_announce_to_player``
verb.

Only events the native bridge actually senses today are considered notable:
entering a new area and completing/being rewarded for a quest. Rare/elite kill,
death, and level-up narration are intentionally deferred until a bridge sensor
emits those facts (Phase 3) -- we do not fabricate notability the engine cannot
confirm. Ordinary trash kills are deliberately excluded so WM does not babble.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# Canonical WM event types (see wm.sources.native_bridge.adapter) that are worth
# an unprompted line. Kept deliberately small; expand only as the bridge gains
# new sensed facts (e.g. player_death, level_up, rare_kill).
NOTABLE_AMBIENT_EVENT_TYPES: frozenset[str] = frozenset(
    {"enter_area", "quest_completed", "quest_complete", "quest_rewarded", "level_up", "death"}
)

# Rare, high-stakes moments that should narrate immediately rather than lose the
# single ambient slot to routine zone-hopping. These bypass the ambient cooldown
# and win selection when several notable events are pending in the same cycle.
HIGH_PRIORITY_AMBIENT_KINDS: frozenset[str] = frozenset({"level_up", "death"})


@dataclass(slots=True)
class AmbientCue:
    kind: str
    descriptor: str
    source_event_key: str
    zone_id: int | None = None
    area_id: int | None = None
    subject_type: str | None = None
    subject_entry: int | None = None
    event_value: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "descriptor": self.descriptor,
            "source_event_key": self.source_event_key,
            "zone_id": self.zone_id,
            "area_id": self.area_id,
            "subject_type": self.subject_type,
            "subject_entry": self.subject_entry,
            "event_value": self.event_value,
        }


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _descriptor(kind: str, event_value: str | None, area_id: int | None) -> str:
    label = (event_value or "").strip()
    if kind == "enter_area":
        where = label or (f"area {area_id}" if area_id is not None else "a new area")
        return f"entered {where}"
    if kind in ("quest_completed", "quest_complete"):
        what = label or "a quest"
        return f"completed {what}"
    if kind == "quest_rewarded":
        what = label or "a quest"
        return f"was rewarded for {what}"
    if kind == "level_up":
        return f"reached level {label}" if label else "gained a level"
    if kind == "death":
        where = label or "the field"
        return f"has fallen in {where}"
    return label or kind


def classify_ambient_event(event_payload: Any) -> AmbientCue | None:
    """Return an AmbientCue for a narration-worthy event, else None."""
    if not isinstance(event_payload, dict):
        return None
    kind = str(event_payload.get("event_type") or "").strip()
    if kind not in NOTABLE_AMBIENT_EVENT_TYPES:
        return None
    source_key = str(
        event_payload.get("source_event_key")
        or event_payload.get("event_id")
        or ""
    ).strip()
    if not source_key:
        return None
    event_value = event_payload.get("event_value")
    event_value = str(event_value).strip() if event_value not in (None, "") else None
    area_id = _int_or_none(event_payload.get("area_id"))
    return AmbientCue(
        kind=kind,
        descriptor=_descriptor(kind, event_value, area_id),
        source_event_key=source_key,
        zone_id=_int_or_none(event_payload.get("zone_id")),
        area_id=area_id,
        subject_type=(str(event_payload.get("subject_type")) if event_payload.get("subject_type") else None),
        subject_entry=_int_or_none(event_payload.get("subject_entry")),
        event_value=event_value,
    )


_SYSTEM_PROMPT = (
    "You are World Master, the unseen director of this game world. Narrate ONE short "
    "in-world line (a single sentence, at most two) reacting to what just happened to the "
    "player, as ambient atmosphere. No markdown, bullets, headings, or quotes. Do not "
    "address the player by stat or coordinates. Never promise or imply rewards, items, "
    "teleports, quests, or any mechanical effect. Never invent place or creature names; "
    "use only the names given in the context. Keep it evocative but grounded. "
    "Do not think. Do not explain. Output only the line."
)


def build_ambient_messages(cue: AmbientCue, identity: dict[str, Any] | None) -> list[dict[str, str]]:
    """Build the chat-style messages for a single ambient narration line."""
    context = {
        "moment": cue.to_dict(),
        "player": identity or {},
        "instruction": "Write one ambient World Master line about this moment.",
    }
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False, sort_keys=True)},
    ]
