"""In-process issues queue for blocked + rejected proposals.

Persistence is out-of-scope for the vertical slice; the queue lives as
long as the panel process. Each entry carries enough to triage.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from itertools import count
from typing import Any


@dataclass(slots=True)
class Issue:
    id: int
    reason: str
    kind: str
    character_guid: int
    payload: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)


class IssuesQueue:
    def __init__(self) -> None:
        self._items: list[Issue] = []
        self._ids = count(1)

    def add(self, *, reason: str, kind: str, character_guid: int,
            payload: dict[str, Any], provenance: dict[str, Any] | None = None) -> Issue:
        item = Issue(id=next(self._ids), reason=reason, kind=kind,
                     character_guid=character_guid, payload=payload,
                     provenance=provenance or {})
        self._items.append(item)
        return item

    def list_open(self) -> list[Issue]:
        return list(self._items)
