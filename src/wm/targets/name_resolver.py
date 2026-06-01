"""Resolve a creature *name* to a creature_template entry, offline.

The conversational layer lets a player say "spawn 3 deer", but native
``creature_spawn`` needs a numeric entry, and an LLM cannot reliably produce
one. This deterministic resolver maps a spoken creature name to candidate
entries using the same static lookup the subject resolver uses
(``data/lookup/creature_template_full.json``), so it works without a live DB
and without trusting the model for IDs.

Matching is tiered (exact name > whole-word > substring) and, within a tier,
prefers ordinary spawnable creatures (lower rank, shorter/cleaner name, lower
entry). Obvious non-spawnable junk (GM/visual/trigger/test/unused rows) is
filtered out so "deer" resolves to the real Deer, not a debug marker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from wm.targets.resolver import LookupStore

# Substrings that mark a creature_template row as not a real, player-facing,
# spawnable creature. Matched case-insensitively against the name.
_JUNK_MARKERS: tuple[str, ...] = (
    "only gm can see",
    "trigger",
    "(test",
    "[test",
    "test ",
    "unused",
    "[dep]",
    "(dep)",
    "(old",
    "[old",
    "do not use",
    "donotuse",
    "visual only",
    "[ph]",
    "placeholder",
)


@dataclass(slots=True)
class CreatureNameMatch:
    entry: int
    name: str
    rank: int
    level_min: int
    level_max: int
    match_tier: str  # "exact" | "word" | "substring"

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": self.entry,
            "name": self.name,
            "rank": self.rank,
            "level_min": self.level_min,
            "level_max": self.level_max,
            "match_tier": self.match_tier,
        }


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _is_junk(name: str) -> bool:
    if not name.strip():
        return True
    lowered = name.lower()
    return any(marker in lowered for marker in _JUNK_MARKERS)


class CreatureNameResolver:
    def __init__(self, store: LookupStore) -> None:
        # Pre-filter junk once; keep (normalized_name, row) for matching.
        self._rows = [row for row in store.creatures_by_entry.values() if not _is_junk(row.name)]

    @classmethod
    def from_json(cls, path: str | Path) -> "CreatureNameResolver":
        return cls(LookupStore.from_json(path))

    def resolve(self, query: str, *, limit: int = 5) -> list[CreatureNameMatch]:
        normalized = _normalize(query)
        if not normalized:
            return []
        word_re = re.compile(r"\b" + re.escape(normalized) + r"\b")
        exact, word, substring = [], [], []
        for row in self._rows:
            name_norm = _normalize(row.name)
            if name_norm == normalized:
                exact.append(row)
            elif word_re.search(name_norm):
                word.append(row)
            elif normalized in name_norm:
                substring.append(row)

        def sort_key(row: Any) -> tuple[int, int, int]:
            # Prefer ordinary creatures (rank 0), then shorter names, then lower entry.
            return (int(row.rank), len(row.name), int(row.entry))

        ordered: list[tuple[str, Any]] = []
        ordered += [("exact", row) for row in sorted(exact, key=sort_key)]
        ordered += [("word", row) for row in sorted(word, key=sort_key)]
        ordered += [("substring", row) for row in sorted(substring, key=sort_key)]

        return [
            CreatureNameMatch(
                entry=int(row.entry),
                name=row.name,
                rank=int(row.rank),
                level_min=int(row.minlevel),
                level_max=int(row.maxlevel),
                match_tier=tier,
            )
            for tier, row in ordered[: max(1, int(limit))]
        ]

    def best_entry(self, query: str) -> int | None:
        matches = self.resolve(query, limit=1)
        return matches[0].entry if matches else None


def _default_lookup_path() -> Path:
    # src/wm/targets/name_resolver.py -> repo root is parents[3]
    return Path(__file__).resolve().parents[3] / "data" / "lookup" / "creature_template_full.json"


@lru_cache(maxsize=1)
def get_default_creature_name_resolver() -> "CreatureNameResolver | None":
    """Load the repo's static creature lookup once. Returns None if absent."""
    path = _default_lookup_path()
    if not path.exists():
        return None
    return CreatureNameResolver.from_json(path)
