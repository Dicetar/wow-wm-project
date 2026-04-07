from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ItemSqlPlan:
    item_entry: int
    statements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_managed_item_sql_plan(
    *,
    item_entry: int,
    final_row: dict[str, Any],
    column_order: list[str],
    note: str | None = None,
) -> ItemSqlPlan:
    statements = [f"-- WM managed item slot {item_entry}"]
    if note:
        statements.append(f"-- {note}")
    statements.append(f"DELETE FROM item_template WHERE entry = {int(item_entry)};")
    columns_sql = ", ".join(f"`{column}`" for column in column_order)
    values_sql = ", ".join(_sql_value(final_row.get(column)) for column in column_order)
    statements.append(f"REPLACE INTO item_template ({columns_sql}) VALUES ({values_sql});")
    return ItemSqlPlan(item_entry=item_entry, statements=statements)


def _sql_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"
