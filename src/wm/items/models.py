from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ItemStatLine:
    stat_type: int
    stat_value: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ItemSpellLine:
    spell_id: int
    trigger: int = 0
    charges: int = 0
    ppm_rate: float = 0.0
    cooldown_ms: int = -1
    category: int = 0
    category_cooldown_ms: int = -1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ManagedItemDraft:
    item_entry: int
    base_item_entry: int
    name: str
    display_id: int | None = None
    description: str | None = None
    item_class: int | None = None
    item_subclass: int | None = None
    inventory_type: int | None = None
    quality: int | None = None
    item_level: int | None = None
    required_level: int | None = None
    bonding: int | None = None
    buy_price: int | None = None
    sell_price: int | None = None
    max_count: int | None = None
    stackable: int | None = None
    allowable_class: int | None = None
    allowable_race: int | None = None
    clear_stats: bool = False
    clear_spells: bool = False
    stats: list[ItemStatLine] = field(default_factory=list)
    spells: list[ItemSpellLine] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    template_defaults: dict[str, Any] = field(default_factory=dict)

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
