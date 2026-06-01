"""Deterministic preparation of creature_spawn arguments from a spoken request.

An LLM cannot produce a creature entry id. So when the conversational layer
wants to spawn a creature, the model only needs to *name* it; this module
resolves the spoken name to a ``creature_entry`` via the offline
``CreatureNameResolver``.

The native ``creature_spawn`` verb spawns the creature *near the scoped player
automatically* (see control/actions/native/native_bridge_action.json: required
``creature_entry``; optional ``distance``/``angle_offset``/``follow_*``/
``duration_ms``). So no position is needed here -- we only resolve the entry and
pass through any movement/follow hints the model supplied.

Returns a ready ``creature_spawn`` payload or a human-readable SpawnArgsError so
the caller can reject cleanly instead of enqueuing a malformed native action.
Pure and unit-testable; the live wiring just supplies the resolver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_NAME_KEYS = ("creature_name", "name", "creature", "creature_kind")
_ENTRY_KEYS = ("creature_entry", "entry")
# Optional hints the native verb accepts; passed through untouched when present.
_PASSTHROUGH_KEYS = (
    "distance",
    "angle_offset",
    "follow_player",
    "follow_distance",
    "follow_angle",
    "duration_ms",
    "arc_key",
)


@dataclass(slots=True)
class SpawnArgsError:
    reason: str


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _spoken_name(args: dict[str, Any]) -> str | None:
    for key in _NAME_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def prepare_creature_spawn_args(
    raw_args: dict[str, Any] | None,
    *,
    resolver: Any,
) -> dict[str, Any] | SpawnArgsError:
    """Return a ready ``creature_spawn`` payload, or a SpawnArgsError.

    ``resolver`` is a CreatureNameResolver-like object exposing ``best_entry``.
    """
    args = dict(raw_args or {})

    # Trust an explicit valid entry, else resolve the spoken creature name.
    entry: int | None = None
    for key in _ENTRY_KEYS:
        entry = _positive_int(args.get(key))
        if entry is not None:
            break

    resolved_name: str | None = None
    if entry is None:
        name = _spoken_name(args)
        if not name:
            return SpawnArgsError("no creature entry or name was provided")
        entry = _positive_int(resolver.best_entry(name)) if resolver is not None else None
        if entry is None:
            return SpawnArgsError(f"could not resolve creature name {name!r} to a known creature")
        resolved_name = name

    payload: dict[str, Any] = {"creature_entry": entry}
    for key in _PASSTHROUGH_KEYS:
        if args.get(key) is not None:
            payload[key] = args[key]
    if resolved_name is not None:
        payload["resolved_from_name"] = resolved_name
    return payload
