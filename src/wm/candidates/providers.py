from __future__ import annotations

from pathlib import Path
from typing import Any

from wm.candidates.models import CandidateOption, CandidateSet
from wm.export.loader import load_export
from wm.export.models import ExportBundle, RowListExport


def build_quest_candidates(path: str | Path, limit: int = 5) -> CandidateSet:
    rows = _load_rows(path)
    options = _build_candidates(
        rows,
        kind="quest",
        source_table="quest_template",
        label_keys=["LogTitle", "Title", "QuestTitle", "name", "Name"],
        id_keys=["ID", "Id", "QuestID", "QuestId", "entry", "Entry"],
        summary_keys=["QuestLevel", "MinLevel", "QuestSortID", "Type", "ZoneOrSort", "ObjectiveText1"],
        limit=limit,
    )
    return CandidateSet(kind="quest", source_path=str(path), options=options)


def build_item_candidates(path: str | Path, limit: int = 5) -> CandidateSet:
    rows = _load_rows(path)
    options = _build_candidates(
        rows,
        kind="item",
        source_table="item_template",
        label_keys=["name", "Name", "ItemName", "display_name"],
        id_keys=["entry", "Entry", "ID", "Id", "item_id"],
        summary_keys=["Quality", "ItemLevel", "RequiredLevel", "class", "subclass", "InventoryType"],
        limit=limit,
    )
    return CandidateSet(kind="item", source_path=str(path), options=options)


def build_spell_candidates(path: str | Path, limit: int = 5) -> CandidateSet:
    rows = _load_rows(path)
    options = _build_candidates(
        rows,
        kind="spell",
        source_table="spell_dbc",
        label_keys=["SpellName1", "SpellName", "Name", "name"],
        id_keys=["ID", "Id", "SpellID", "SpellId", "entry", "Entry"],
        summary_keys=["School", "Category", "RecoveryTime", "RangeIndex", "Effect1", "Attributes"],
        limit=limit,
    )
    return CandidateSet(kind="spell", source_path=str(path), options=options)


def _load_rows(path: str | Path) -> list[dict[str, Any]]:
    loaded = load_export(path)
    if isinstance(loaded, RowListExport):
        return [_normalize_nested_nulls(row) for row in loaded.rows]
    if isinstance(loaded, ExportBundle):
        rows: list[dict[str, Any]] = []
        for sample in loaded.samples:
            if isinstance(sample, dict) and isinstance(sample.get("row"), dict):
                rows.append(_normalize_nested_nulls(sample["row"]))
            elif isinstance(sample, dict):
                rows.append(_normalize_nested_nulls(sample))
        return rows
    return []


def _build_candidates(
    rows: list[dict[str, Any]],
    *,
    kind: str,
    source_table: str,
    label_keys: list[str],
    id_keys: list[str],
    summary_keys: list[str],
    limit: int,
) -> list[CandidateOption]:
    options: list[CandidateOption] = []
    seen: set[tuple[int | None, str]] = set()
    for row in rows:
        label = _first_present_string(row, label_keys)
        if not label:
            continue
        entry_id = _first_present_int(row, id_keys)
        key = (entry_id, label)
        if key in seen:
            continue
        seen.add(key)
        summary = _build_summary(row, summary_keys)
        options.append(
            CandidateOption(
                kind=kind,
                source_table=source_table,
                entry_id=entry_id,
                label=label,
                summary=summary,
                raw_row=row,
            )
        )
        if len(options) >= limit:
            break
    return options


def _build_summary(row: dict[str, Any], keys: list[str]) -> str | None:
    parts: list[str] = []
    for key in keys:
        if key not in row or row[key] in (None, "", [], {}):
            continue
        parts.append(f"{key}={row[key]}")
    return "; ".join(parts) if parts else None


def _first_present_string(row: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _first_present_int(row: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _normalize_nested_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize_nested_nulls(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_nested_nulls(v) for v in value]
    if value == "NULL":
        return None
    return value
