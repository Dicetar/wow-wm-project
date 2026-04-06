from __future__ import annotations

from dataclasses import asdict
from typing import Any

from wm.reserved.models import ReservedSlot


class ReservedCliError(ValueError):
    """Raised when reserved slot CLI input is invalid."""


def parse_notes_arg(raw_notes: list[str] | None) -> list[str]:
    if not raw_notes:
        return []
    parsed: list[str] = []
    for value in raw_notes:
        text = str(value).strip()
        if text:
            parsed.append(text)
    return parsed


def render_slot(slot: ReservedSlot | None) -> dict[str, Any]:
    if slot is None:
        return {"slot": None}
    return asdict(slot)


def render_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        entity_type = str(row["EntityType"])
        slot_status = str(row["SlotStatus"])
        count_rows = int(row["CountRows"])
        if entity_type not in summary:
            summary[entity_type] = {}
        summary[entity_type][slot_status] = count_rows
    return summary


def ensure_status(raw_status: str) -> str:
    normalized = raw_status.strip().lower()
    if normalized not in {"free", "staged", "active", "retired", "archived"}:
        raise ReservedCliError(f"Unsupported slot status: {raw_status}")
    return normalized
