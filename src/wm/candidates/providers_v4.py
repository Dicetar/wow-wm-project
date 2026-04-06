from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from wm.candidates.filters import is_candidate_label_allowed
from wm.candidates.models import CandidateOption, CandidateSet
from wm.candidates.ranking import CandidateContext, annotate_summary_with_score, score_item_candidate, score_quest_candidate, score_spell_candidate
from wm.export.loader import load_export
from wm.export.models import ExportBundle, RowListExport

_SCHEMA_NAME_KEYS = ("name", "Field", "field", "column", "Column")


def build_quest_candidates_v4(path: str | Path, *, context: CandidateContext | None = None, limit: int = 5) -> CandidateSet:
    rows, schema_names = _load_rows_and_schema(path)
    options = _build_candidates_v4(
        rows,
        schema_names=schema_names,
        kind="quest",
        source_table="quest_template",
        preferred_label_keys=["LogTitle", "Title", "QuestTitle", "name", "Name"],
        preferred_id_keys=["ID", "Id", "QuestID", "QuestId", "entry", "Entry"],
        preferred_summary_keys=["QuestLevel", "MinLevel", "QuestSortID", "QuestInfoID", "ObjectiveText1"],
        context=context,
        scorer=score_quest_candidate,
        limit=limit,
    )
    return CandidateSet(kind="quest", source_path=str(path), options=options)


def build_item_candidates_v4(path: str | Path, *, context: CandidateContext | None = None, limit: int = 5) -> CandidateSet:
    rows, schema_names = _load_rows_and_schema(path)
    options = _build_candidates_v4(
        rows,
        schema_names=schema_names,
        kind="item",
        source_table="item_template",
        preferred_label_keys=["name", "Name", "ItemName", "display_name", "Description"],
        preferred_id_keys=["entry", "Entry", "ID", "Id", "item_id"],
        preferred_summary_keys=["Quality", "ItemLevel", "RequiredLevel", "class", "subclass", "InventoryType", "spellid_1"],
        context=context,
        scorer=score_item_candidate,
        limit=limit,
    )
    return CandidateSet(kind="item", source_path=str(path), options=options)


def build_spell_candidates_v4(path: str | Path, *, context: CandidateContext | None = None, limit: int = 5) -> CandidateSet:
    rows, schema_names = _load_rows_and_schema(path)
    options = _build_candidates_v4(
        rows,
        schema_names=schema_names,
        kind="spell",
        source_table="spell_dbc",
        preferred_label_keys=[
            "Name_Lang_enUS",
            "SpellName1",
            "SpellName",
            "Name",
            "Name_lang",
            "Description_Lang_enUS",
            "Description",
        ],
        preferred_id_keys=["ID", "Id", "SpellID", "SpellId", "entry", "Entry"],
        preferred_summary_keys=["SchoolMask", "Category", "ManaCost", "RangeIndex", "DurationIndex", "Effect_1", "Effect_2", "Effect_3"],
        context=context,
        scorer=score_spell_candidate,
        limit=limit,
    )
    return CandidateSet(kind="spell", source_path=str(path), options=options)


def _load_rows_and_schema(path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    loaded = load_export(path)
    if isinstance(loaded, RowListExport):
        rows = [_normalize_nested_nulls(row) for row in loaded.rows]
        return rows, _derive_schema_names([], rows)
    if isinstance(loaded, ExportBundle):
        rows: list[dict[str, Any]] = []
        for sample in loaded.samples:
            if isinstance(sample, dict) and isinstance(sample.get("row"), dict):
                rows.append(_normalize_nested_nulls(sample["row"]))
            elif isinstance(sample, dict):
                rows.append(_normalize_nested_nulls(sample))
        return rows, _derive_schema_names(loaded.schema, rows)
    return [], []


def _derive_schema_names(schema: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for entry in schema:
        if not isinstance(entry, dict):
            continue
        for key in _SCHEMA_NAME_KEYS:
            value = entry.get(key)
            if value is None:
                continue
            text = str(value)
            if text and text not in seen:
                ordered.append(text)
                seen.add(text)
                break
    for row in rows:
        for key in row.keys():
            text = str(key)
            if text not in seen:
                ordered.append(text)
                seen.add(text)
    return ordered


def _build_candidates_v4(
    rows: list[dict[str, Any]],
    *,
    schema_names: list[str],
    kind: str,
    source_table: str,
    preferred_label_keys: list[str],
    preferred_id_keys: list[str],
    preferred_summary_keys: list[str],
    context: CandidateContext | None,
    scorer,
    limit: int,
) -> list[CandidateOption]:
    label_keys = _discover_label_keys(schema_names, preferred_label_keys)
    summary_keys = _discover_summary_keys(schema_names, preferred_summary_keys)

    scored_rows: list[tuple[int, int | None, str, dict[str, Any], str | None]] = []
    seen: set[tuple[int | None, str]] = set()
    for row in rows:
        label = _pick_label(row, label_keys)
        if not label or not is_candidate_label_allowed(kind, label):
            continue
        entry_id = _first_present_int(row, preferred_id_keys)
        key = (entry_id, label)
        if key in seen:
            continue
        seen.add(key)
        summary = _build_summary(row, summary_keys)
        score = int(scorer(row, label, context))
        scored_rows.append((score, entry_id, label, row, summary))

    scored_rows.sort(key=lambda item: (-item[0], item[1] if item[1] is not None else 10**12, item[2]))

    options: list[CandidateOption] = []
    for score, entry_id, label, row, summary in scored_rows[:limit]:
        options.append(
            CandidateOption(
                kind=kind,
                source_table=source_table,
                entry_id=entry_id,
                label=label,
                summary=annotate_summary_with_score(summary, score),
                raw_row=row,
            )
        )
    return options


def _discover_label_keys(schema_names: list[str], preferred: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for key in preferred:
        if key in schema_names and key not in seen:
            ordered.append(key)
            seen.add(key)
    dynamic_patterns = [
        re.compile(r"(^|_)name($|_)", re.IGNORECASE),
        re.compile(r"spellname", re.IGNORECASE),
        re.compile(r"title", re.IGNORECASE),
        re.compile(r"description", re.IGNORECASE),
    ]
    for key in schema_names:
        if key in seen:
            continue
        if any(pattern.search(key) for pattern in dynamic_patterns):
            ordered.append(key)
            seen.add(key)
    return ordered


def _discover_summary_keys(schema_names: list[str], preferred: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for key in preferred:
        if key in schema_names and key not in seen:
            ordered.append(key)
            seen.add(key)
    return ordered


def _pick_label(row: dict[str, Any], label_keys: list[str]) -> str | None:
    for key in label_keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if not text:
            continue
        if _looks_like_non_label(text):
            continue
        return text
    return None


def _looks_like_non_label(text: str) -> bool:
    if text.isdigit():
        return True
    if len(text) <= 1:
        return True
    return False


def _build_summary(row: dict[str, Any], keys: list[str]) -> str | None:
    parts: list[str] = []
    for key in keys:
        if key not in row or row[key] in (None, "", [], {}):
            continue
        parts.append(f"{key}={row[key]}")
    return "; ".join(parts) if parts else None


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
