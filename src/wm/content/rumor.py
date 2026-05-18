"""Content-layer rumor template models.

Distinct from wm.living.rumor (which evaluates live triggers);
this module defines the template structures stored/loaded by content authors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RumorLine:
    line_key: str
    template: str           # Supports {player}, {subject}, {count}, {zone}
    min_deed_count: int = 1
    tags: list[str] = field(default_factory=list)

    def render(self, **kwargs: Any) -> str:
        try:
            return self.template.format(**kwargs)
        except KeyError:
            return self.template


@dataclass(slots=True)
class RumorBundle:
    bundle_key: str
    lines: list[RumorLine]
    subject_filter: str | None = None   # archetype or species tag

    def lines_for_count(self, deed_count: int) -> list[RumorLine]:
        return [ln for ln in self.lines if deed_count >= ln.min_deed_count]

    def best_line(self, deed_count: int) -> RumorLine | None:
        eligible = self.lines_for_count(deed_count)
        if not eligible:
            return None
        return max(eligible, key=lambda ln: ln.min_deed_count)
