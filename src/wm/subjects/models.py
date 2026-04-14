from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from wm.refs import CreatureRef


@dataclass(slots=True)
class SubjectCard:
    canonical_id: str
    kind: str
    display_name: str
    entry: int | None = None
    title: str | None = None
    archetype: str | None = None
    faction_id: int | None = None
    faction_label: str | None = None
    creature_type: str | None = None
    family: str | None = None
    rank: str | None = None
    unit_class: str | None = None
    role_tags: list[str] = field(default_factory=list)
    group_keys: list[str] = field(default_factory=list)
    area_tags: list[str] = field(default_factory=list)
    source_ref: CreatureRef | None = None
    source: str = "unknown"
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_ref"] = self.source_ref.to_dict() if self.source_ref is not None else None
        return payload
