from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CandidateOption:
    kind: str
    source_table: str
    entry_id: int | None
    label: str
    summary: str | None = None
    raw_row: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CandidateSet:
    kind: str
    source_path: str
    options: list[CandidateOption]
