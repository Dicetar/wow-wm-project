from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SubjectCard:
    subject_name: str
    short_description: str | None = None
    archetype: str | None = None
    species: str | None = None
    occupation: str | None = None
    home_area: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class JournalCounters:
    kill_count: int = 0
    skin_count: int = 0
    feed_count: int = 0
    talk_count: int = 0
    quest_complete_count: int = 0
    last_quest_title: str | None = None


@dataclass(slots=True)
class JournalEvent:
    event_type: str
    event_value: str | None = None


@dataclass(slots=True)
class JournalSummary:
    title: str
    description: str | None
    history_lines: list[str]
    raw: dict[str, Any]
