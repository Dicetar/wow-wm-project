from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


CONTEXT_PACK_SCHEMA_VERSION = "wm.context_pack.v1"


@dataclass(slots=True)
class ContextPack:
    pack_id: str
    player_guid: int
    target_entry: int
    schema_version: str = CONTEXT_PACK_SCHEMA_VERSION
    source_event: dict[str, Any] | None = None
    character_state: dict[str, Any] | None = None
    target_profile: dict[str, Any] | None = None
    subject_card: dict[str, Any] | None = None
    journal_summary: dict[str, Any] | None = None
    journal_status: str = "UNKNOWN"
    journal_source_flags: list[str] = field(default_factory=list)
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    related_subject_events: list[dict[str, Any]] = field(default_factory=list)
    quest_runtime: dict[str, Any] = field(default_factory=dict)
    eligible_recipes: list[dict[str, Any]] = field(default_factory=list)
    policy: dict[str, Any] | None = None
    native_context_snapshot: dict[str, Any] | None = None
    generation_input: dict[str, Any] = field(default_factory=dict)
    status: str = "UNKNOWN"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
