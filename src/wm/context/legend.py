from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LegendEntry:
    narrative_key: str
    summary: str
    at: datetime


@dataclass
class LocalLegendSection:
    zone_id: int
    legends: list[LegendEntry] = field(default_factory=list)
