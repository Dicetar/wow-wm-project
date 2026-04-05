from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wm.export.models import ExportBundle, RowListExport


class UnsupportedExportFormatError(ValueError):
    """Raised when a JSON export file is not in a recognized format."""


def load_export(path: str | Path) -> ExportBundle | RowListExport:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    if isinstance(raw, list):
        return RowListExport(rows=_normalize_rows(raw))

    if isinstance(raw, dict) and _looks_like_bundle(raw):
        return ExportBundle(
            database=str(raw.get("database", "")),
            table=str(raw.get("table", "")),
            row_count=int(raw.get("row_count", 0)),
            sample_count=int(raw.get("sample_count", 0)),
            order_columns=[str(x) for x in raw.get("order_columns", [])],
            primary_key=[str(x) for x in raw.get("primary_key", [])],
            schema=[dict(x) for x in raw.get("schema", [])],
            samples=_normalize_rows(raw.get("samples", [])),
        )

    raise UnsupportedExportFormatError(
        f"Unrecognized export format for file: {Path(path)}"
    )


def _looks_like_bundle(raw: dict[str, Any]) -> bool:
    required = {
        "database",
        "table",
        "row_count",
        "sample_count",
        "order_columns",
        "primary_key",
        "schema",
        "samples",
    }
    return required.issubset(raw.keys())


def _normalize_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise UnsupportedExportFormatError("Row export contains non-object rows")
        normalized.append(_normalize_null_strings(row))
    return normalized


def _normalize_null_strings(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if value == "NULL":
            normalized[key] = None
        else:
            normalized[key] = value
    return normalized
