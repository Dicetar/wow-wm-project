from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import struct
from pathlib import Path
from typing import Any

from wm.spells.server_dbc import ACTIVE_ICON_ID_FIELD
from wm.spells.server_dbc import AURA_INTERRUPT_FLAGS_FIELD
from wm.spells.server_dbc import CATEGORY_RECOVERY_TIME_FIELD
from wm.spells.server_dbc import DAMAGE_CLASS_FIELD
from wm.spells.server_dbc import DISPEL_TYPE_FIELD
from wm.spells.server_dbc import DURATION_INDEX_FIELD
from wm.spells.server_dbc import EFFECT_1_FIELD
from wm.spells.server_dbc import EFFECT_APPLY_AURA_NAME_1_FIELD
from wm.spells.server_dbc import EFFECT_IMPLICIT_TARGET_A_1_FIELD
from wm.spells.server_dbc import EQUIPPED_ITEM_CLASS_FIELD
from wm.spells.server_dbc import INTERRUPT_FLAGS_FIELD
from wm.spells.server_dbc import MANA_COST_FIELD
from wm.spells.server_dbc import MANA_COST_PERCENTAGE_FIELD
from wm.spells.server_dbc import POWER_TYPE_FIELD
from wm.spells.server_dbc import PREVENTION_TYPE_FIELD
from wm.spells.server_dbc import RANGE_INDEX_FIELD
from wm.spells.server_dbc import RECOVERY_TIME_FIELD
from wm.spells.server_dbc import SPELL_FAMILY_FLAGS_1_FIELD
from wm.spells.server_dbc import SPELL_FAMILY_FLAGS_2_FIELD
from wm.spells.server_dbc import SPELL_FAMILY_FLAGS_3_FIELD
from wm.spells.server_dbc import SPELL_FAMILY_NAME_FIELD
from wm.spells.server_dbc import SPELL_ICON_ID_FIELD
from wm.spells.server_dbc import STACK_AMOUNT_FIELD
from wm.spells.server_dbc import START_RECOVERY_TIME_FIELD
from wm.spells.server_dbc import load_spell_dbc
from wm.spells.server_dbc import record_spell_id
from wm.spells.shell_bank import SpellShellPatchRow
from wm.spells.shell_bank import default_shell_bank_path
from wm.spells.shell_bank import generate_patch_rows


PRESENTATION_FIELDS: dict[str, int] = {
    "active_icon_id": ACTIVE_ICON_ID_FIELD,
    "aura_interrupt_flags": AURA_INTERRUPT_FLAGS_FIELD,
    "category_recovery_time": CATEGORY_RECOVERY_TIME_FIELD,
    "damage_class": DAMAGE_CLASS_FIELD,
    "dispel_type": DISPEL_TYPE_FIELD,
    "duration_index": DURATION_INDEX_FIELD,
    "effect_1": EFFECT_1_FIELD,
    "effect_apply_aura_name_1": EFFECT_APPLY_AURA_NAME_1_FIELD,
    "effect_implicit_target_a_1": EFFECT_IMPLICIT_TARGET_A_1_FIELD,
    "equipped_item_class": EQUIPPED_ITEM_CLASS_FIELD,
    "interrupt_flags": INTERRUPT_FLAGS_FIELD,
    "mana_cost": MANA_COST_FIELD,
    "mana_cost_percentage": MANA_COST_PERCENTAGE_FIELD,
    "power_type": POWER_TYPE_FIELD,
    "prevention_type": PREVENTION_TYPE_FIELD,
    "range_index": RANGE_INDEX_FIELD,
    "recovery_time": RECOVERY_TIME_FIELD,
    "spell_family_flags_1": SPELL_FAMILY_FLAGS_1_FIELD,
    "spell_family_flags_2": SPELL_FAMILY_FLAGS_2_FIELD,
    "spell_family_flags_3": SPELL_FAMILY_FLAGS_3_FIELD,
    "spell_family_name": SPELL_FAMILY_NAME_FIELD,
    "spell_icon_id": SPELL_ICON_ID_FIELD,
    "stack_amount": STACK_AMOUNT_FIELD,
    "start_recovery_time": START_RECOVERY_TIME_FIELD,
}

MARKER_AURA_FIELD_NAMES = (
    "spell_family_name",
    "spell_family_flags_1",
    "spell_family_flags_2",
    "spell_family_flags_3",
    "damage_class",
    "prevention_type",
)


@dataclass(slots=True)
class ShellAuditIssue:
    severity: str
    spell_id: int
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ShellAuditSpellResult:
    spell_id: int
    shell_key: str | None
    label: str | None
    family_id: str | None
    behavior_kind: str | None
    issues: list[ShellAuditIssue]

    @property
    def status(self) -> str:
        if any(issue.severity == "error" for issue in self.issues):
            return "BROKEN"
        if any(issue.severity == "warning" for issue in self.issues):
            return "PARTIAL"
        return "WORKING"

    def to_dict(self) -> dict[str, Any]:
        return {
            "spell_id": self.spell_id,
            "shell_key": self.shell_key,
            "label": self.label,
            "family_id": self.family_id,
            "behavior_kind": self.behavior_kind,
            "status": self.status,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(slots=True)
class ShellAuditReport:
    status: str
    spell_results: list[ShellAuditSpellResult]
    checked_spell_ids: list[int]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checked_spell_ids": self.checked_spell_ids,
            "notes": self.notes,
            "spell_results": [result.to_dict() for result in self.spell_results],
        }


def audit_spell_shells(
    *,
    spell_ids: list[int] | None = None,
    shell_bank_path: str | Path | None = None,
    client_dbc: str | Path | None = None,
    server_dbc: str | Path | None = None,
) -> ShellAuditReport:
    rows = generate_patch_rows(shell_bank_path or default_shell_bank_path())
    named_rows = {row.spell_id: row for row in rows if row.is_named_override}
    selected_ids = sorted(set(int(spell_id) for spell_id in (spell_ids or named_rows.keys())))
    client_records = _load_dbc_fields(client_dbc) if client_dbc else {}
    server_records = _load_dbc_fields(server_dbc) if server_dbc else {}

    results: list[ShellAuditSpellResult] = []
    for spell_id in selected_ids:
        row = named_rows.get(spell_id)
        issues: list[ShellAuditIssue] = []
        if row is None:
            issues.append(_issue("error", spell_id, "missing_shell_bank_row", "Spell is not a named shell-bank row."))
            results.append(
                ShellAuditSpellResult(
                    spell_id=spell_id,
                    shell_key=None,
                    label=None,
                    family_id=None,
                    behavior_kind=None,
                    issues=issues,
                )
            )
            continue

        issues.extend(_audit_shell_row(row))
        if client_dbc:
            issues.extend(_audit_dbc_record(row, client_records.get(spell_id), "client"))
        if server_dbc:
            issues.extend(_audit_dbc_record(row, server_records.get(spell_id), "server"))
        if client_dbc and server_dbc:
            issues.extend(_audit_client_server_match(row, client_records.get(spell_id), server_records.get(spell_id)))

        results.append(
            ShellAuditSpellResult(
                spell_id=spell_id,
                shell_key=row.shell_key,
                label=row.label,
                family_id=row.family_id,
                behavior_kind=row.behavior_kind,
                issues=issues,
            )
        )

    status = _combine_status(result.status for result in results)
    notes = [
        "client_truth_checked=true" if client_dbc else "client_truth_checked=false",
        "server_truth_checked=true" if server_dbc else "server_truth_checked=false",
        "shell_bank_checked=true",
    ]
    return ShellAuditReport(status=status, spell_results=results, checked_spell_ids=selected_ids, notes=notes)


def _audit_shell_row(row: SpellShellPatchRow) -> list[ShellAuditIssue]:
    issues: list[ShellAuditIssue] = []
    presentation = row.client_presentation or {}

    if not row.label or row.label.startswith(row.family_id):
        issues.append(_issue("error", row.spell_id, "missing_label", "Named shell must have a player-facing label."))
    if not row.tooltip:
        issues.append(_issue("error", row.spell_id, "missing_tooltip", "Named shell must have a tooltip."))
    if "spell_icon_id" not in presentation:
        issues.append(_issue("error", row.spell_id, "missing_icon", "Named shell must set spell_icon_id."))

    if row.targeting == "self_cast" and presentation.get("range_index") not in (None, 1):
        issues.append(
            _issue(
                "error",
                row.spell_id,
                "self_cast_range_not_self",
                "Self-cast shell must set range_index=1 to avoid inherited target range.",
            )
        )

    if row.family_id == "passive_aura":
        if presentation.get("spellbook_ability_id") is not None and presentation.get("spellbook_seed_spell_id") is None:
            issues.append(
                _issue(
                    "error",
                    row.spell_id,
                    "missing_spellbook_seed",
                    "Learned passive shell with a spellbook ability row must set spellbook_seed_spell_id.",
                )
            )

    if _is_marker_aura(presentation):
        for field_name in MARKER_AURA_FIELD_NAMES:
            if int(presentation.get(field_name, 0) or 0) != 0:
                issues.append(
                    _issue(
                        "error",
                        row.spell_id,
                        "marker_aura_inherits_stock_identity",
                        f"Marker aura must clear {field_name}; found {presentation.get(field_name)!r}.",
                    )
                )

    if row.family_id in {"unit_target_effect", "self_aura"} and _is_marker_aura(presentation):
        if presentation.get("duration_index") in (None, 0):
            issues.append(
                _issue("warning", row.spell_id, "marker_aura_no_duration", "Visible marker aura has no duration_index.")
            )

    return issues


def _audit_dbc_record(row: SpellShellPatchRow, fields: tuple[int, ...] | None, label: str) -> list[ShellAuditIssue]:
    issues: list[ShellAuditIssue] = []
    if fields is None:
        return [_issue("error", row.spell_id, f"missing_{label}_dbc_row", f"{label} Spell.dbc has no row for this shell.")]

    presentation = row.client_presentation or {}
    for field_name, expected in presentation.items():
        field_index = PRESENTATION_FIELDS.get(field_name)
        if field_index is None or field_index >= len(fields):
            continue
        actual = _normalize_dbc_value(fields[field_index])
        if actual != _normalize_dbc_value(expected):
            issues.append(
                _issue(
                    "error",
                    row.spell_id,
                    f"{label}_dbc_mismatch",
                    f"{label} DBC {field_name} expected {expected!r}, found {actual!r}.",
                )
            )

    return issues


def _audit_client_server_match(
    row: SpellShellPatchRow,
    client_fields: tuple[int, ...] | None,
    server_fields: tuple[int, ...] | None,
) -> list[ShellAuditIssue]:
    if client_fields is None or server_fields is None:
        return []

    issues: list[ShellAuditIssue] = []
    for field_name in (
        "spell_icon_id",
        "range_index",
        "duration_index",
        "stack_amount",
        "effect_1",
        "effect_apply_aura_name_1",
        "spell_family_name",
        "spell_family_flags_1",
        "spell_family_flags_2",
        "spell_family_flags_3",
        "damage_class",
        "prevention_type",
    ):
        field_index = PRESENTATION_FIELDS[field_name]
        if field_index >= len(client_fields) or field_index >= len(server_fields):
            continue
        if client_fields[field_index] != server_fields[field_index]:
            issues.append(
                _issue(
                    "error",
                    row.spell_id,
                    "client_server_dbc_diverged",
                    f"Client/server DBC mismatch for {field_name}: client={client_fields[field_index]!r}, server={server_fields[field_index]!r}.",
                )
            )
    return issues


def _load_dbc_fields(path: str | Path | None) -> dict[int, tuple[int, ...]]:
    if path is None:
        return {}
    dbc = load_spell_dbc(path)
    records: dict[int, tuple[int, ...]] = {}
    for record in dbc.records:
        spell_id = record_spell_id(record)
        if len(record) != dbc.record_size:
            continue
        records[spell_id] = struct.unpack("<" + "I" * dbc.field_count, record)
    return records


def _is_marker_aura(presentation: dict[str, Any]) -> bool:
    return int(presentation.get("effect_1", 0) or 0) == 6 and int(presentation.get("effect_apply_aura_name_1", 0) or 0) == 4


def _normalize_dbc_value(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    return int(value)


def _issue(severity: str, spell_id: int, code: str, message: str) -> ShellAuditIssue:
    return ShellAuditIssue(severity=severity, spell_id=int(spell_id), code=code, message=message)


def _combine_status(statuses: object) -> str:
    status_list = list(statuses)
    if any(status == "BROKEN" for status in status_list):
        return "BROKEN"
    if any(status == "PARTIAL" for status in status_list):
        return "PARTIAL"
    return "WORKING"


def render_summary(report: ShellAuditReport) -> str:
    lines = [f"status={report.status}", f"checked={','.join(str(spell_id) for spell_id in report.checked_spell_ids)}"]
    for result in report.spell_results:
        lines.append(f"spell={result.spell_id} key={result.shell_key} status={result.status}")
        for issue in result.issues:
            lines.append(f"  {issue.severity} {issue.code}: {issue.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit WM shell spell truth across shell bank and optional DBC payloads.")
    parser.add_argument("--spell-id", dest="spell_ids", action="append", type=int, default=[])
    parser.add_argument("--shell-bank", default=str(default_shell_bank_path()))
    parser.add_argument("--client-dbc", default=None)
    parser.add_argument("--server-dbc", default=None)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    report = audit_spell_shells(
        spell_ids=args.spell_ids or None,
        shell_bank_path=args.shell_bank,
        client_dbc=args.client_dbc,
        server_dbc=args.server_dbc,
    )
    if args.summary:
        print(render_summary(report))
    else:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.status != "BROKEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
