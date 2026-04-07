from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ManagedSpellLink:
    trigger_spell_id: int
    effect_spell_id: int
    link_type: int = 0
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ManagedSpellProcRule:
    spell_id: int
    school_mask: int = 0
    spell_family_name: int = 0
    spell_family_mask_0: int = 0
    spell_family_mask_1: int = 0
    spell_family_mask_2: int = 0
    proc_flags: int = 0
    spell_type_mask: int = 0
    spell_phase_mask: int = 0
    hit_mask: int = 0
    attributes_mask: int = 0
    disable_effect_mask: int = 0
    procs_per_minute: float = 0.0
    chance: float = 0.0
    cooldown: int = 0
    charges: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ManagedSpellDraft:
    spell_entry: int
    slot_kind: str
    name: str
    base_visible_spell_id: int | None = None
    helper_spell_id: int | None = None
    trigger_item_entry: int | None = None
    aura_description: str | None = None
    proc_rules: list[ManagedSpellProcRule] = field(default_factory=list)
    linked_spells: list[ManagedSpellLink] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }
