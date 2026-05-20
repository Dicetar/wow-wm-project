"""wm.story_module.v1 — per-character authored story spine.

See docs/superpowers/specs/2026-05-20-wm-vertical-slice-design.md.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "wm.story_module.v1"


class ValidationError(ValueError):
    pass


class BeatKind(str, Enum):
    PINNED = "PINNED"
    OPEN = "OPEN"


@dataclass(slots=True)
class GrantPoint:
    grant_kind: str          # "ability" only for the slice
    ability_ref: str
    when: dict[str, Any]     # {"event": str, "ref": str}
    appropriateness: dict[str, Any]  # {"all_of": [...]} | {"any_of": [...]}


@dataclass(slots=True)
class BeatOutcome:
    next_beat_ref: str | None
    grant_points: list[GrantPoint] = field(default_factory=list)


@dataclass(slots=True)
class Beat:
    id: str
    kind: BeatKind
    entry_condition: dict[str, Any]
    outcome: BeatOutcome
    intent: str | None = None          # OPEN
    constraints: dict[str, Any] = field(default_factory=dict)  # OPEN
    payload: dict[str, Any] | None = None    # PINNED


@dataclass(slots=True)
class StoryModule:
    module_id: str
    character_guid: int
    character_name: str
    premise: str
    tone: str
    constraints: dict[str, Any]
    beats: list[Beat]
    journal_template: str | None = None


def parse_story_module(raw: dict[str, Any]) -> StoryModule:
    if raw.get("schema") != SCHEMA_ID:
        raise ValidationError(f"schema must be {SCHEMA_ID}, got {raw.get('schema')!r}")
    try:
        beats_raw = raw["beats"]
        beat_ids = {b["id"] for b in beats_raw}
    except (KeyError, TypeError) as e:
        raise ValidationError(f"beats missing or malformed: {e}") from e

    beats: list[Beat] = []
    for b in beats_raw:
        kind = BeatKind(b["kind"])
        if kind is BeatKind.OPEN and "intent" not in b:
            raise ValidationError(f"OPEN beat {b['id']!r} missing intent")
        if kind is BeatKind.PINNED and "payload" not in b:
            raise ValidationError(f"PINNED beat {b['id']!r} missing payload")
        outcome_raw = b["outcome"]
        next_ref = outcome_raw.get("next_beat_ref")
        if next_ref is not None and next_ref not in beat_ids:
            raise ValidationError(f"next_beat_ref {next_ref!r} in beat {b['id']!r} is not a known beat id")
        outcome = BeatOutcome(
            next_beat_ref=next_ref,
            grant_points=[
                GrantPoint(
                    grant_kind=g["grant_kind"],
                    ability_ref=g["ability_ref"],
                    when=g["when"],
                    appropriateness=g["appropriateness"],
                )
                for g in outcome_raw.get("grant_points", [])
            ],
        )
        beats.append(Beat(
            id=b["id"], kind=kind,
            entry_condition=b["entry_condition"], outcome=outcome,
            intent=b.get("intent"), constraints=b.get("constraints", {}),
            payload=b.get("payload"),
        ))

    return StoryModule(
        module_id=raw["module_id"],
        character_guid=int(raw["character_guid"]),
        character_name=str(raw["character_name"]),
        premise=str(raw["premise"]),
        tone=str(raw["tone"]),
        constraints=raw.get("constraints", {}),
        beats=beats,
        journal_template=raw.get("journal_template"),
    )
