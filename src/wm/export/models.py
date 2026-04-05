from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ExportBundle:
    database: str
    table: str
    row_count: int
    sample_count: int
    order_columns: list[str]
    primary_key: list[str]
    schema: list[dict[str, Any]]
    samples: list[dict[str, Any]]


@dataclass(slots=True)
class RowListExport:
    rows: list[dict[str, Any]]
