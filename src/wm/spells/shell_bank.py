from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SpellShellFamily:
    family_id: str
    family_kind: str
    label: str
    slot_range_start: int
    slot_count: int
    targeting: str
    cooldown_family: str
    supports_true_pet: bool
    supports_multi_pet: bool
    patch_seed_template: str | None
    behavior_kinds: list[str]

    @property
    def slot_range_end(self) -> int:
        return self.slot_range_start + self.slot_count - 1

    def contains(self, spell_id: int) -> bool:
        return self.slot_range_start <= int(spell_id) <= self.slot_range_end


@dataclass(slots=True)
class SpellShellDefinition:
    shell_key: str
    spell_id: int
    family_id: str
    label: str
    behavior_kind: str
    targeting: str
    required_level: int
    icon_hint: str | None
    tooltip: str | None
    client_presentation: dict[str, Any] | None
    patch_state: str | None
    notes: list[str]


@dataclass(slots=True)
class SpellShellBank:
    schema_version: str
    description: str
    client_patch_required: bool
    notes: list[str]
    families: list[SpellShellFamily]
    patch: dict[str, str]
    shells: list[SpellShellDefinition]

    @property
    def total_family_slots(self) -> int:
        return sum(family.slot_count for family in self.families)

    @property
    def generic_families(self) -> list[SpellShellFamily]:
        return [family for family in self.families if family.family_kind == "generic"]

    def family_for_spell(self, spell_id: int) -> SpellShellFamily | None:
        for family in self.families:
            if family.contains(spell_id):
                return family
        return None

    def family_by_id(self, family_id: str) -> SpellShellFamily | None:
        for family in self.families:
            if family.family_id == family_id:
                return family
        return None

    def shell_by_key(self, shell_key: str) -> SpellShellDefinition | None:
        for shell in self.shells:
            if shell.shell_key == shell_key:
                return shell
        return None

    def shell_by_spell_id(self, spell_id: int) -> SpellShellDefinition | None:
        for shell in self.shells:
            if shell.spell_id == int(spell_id):
                return shell
        return None


@dataclass(slots=True)
class SpellShellPatchRow:
    spell_id: int
    family_id: str
    shell_key: str
    label: str
    targeting: str
    cooldown_family: str
    seed_template: str | None
    slot_index: int
    is_named_override: bool
    behavior_kind: str | None = None
    required_level: int | None = None
    icon_hint: str | None = None
    tooltip: str | None = None
    client_presentation: dict[str, Any] | None = None
    patch_state: str | None = None
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "spell_id": self.spell_id,
            "family_id": self.family_id,
            "shell_key": self.shell_key,
            "label": self.label,
            "targeting": self.targeting,
            "cooldown_family": self.cooldown_family,
            "seed_template": self.seed_template,
            "slot_index": self.slot_index,
            "is_named_override": self.is_named_override,
            "behavior_kind": self.behavior_kind,
            "required_level": self.required_level,
            "icon_hint": self.icon_hint,
            "tooltip": self.tooltip,
            "client_presentation": dict(self.client_presentation or {}),
            "patch_state": self.patch_state,
            "notes": list(self.notes or []),
        }


def default_shell_bank_path() -> Path:
    return Path(__file__).resolve().parents[3].joinpath("control", "runtime", "spell_shell_bank.json")


def load_spell_shell_bank(path: str | Path | None = None) -> SpellShellBank:
    source = Path(path) if path is not None else default_shell_bank_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    families = [
        SpellShellFamily(
            family_id=str(entry["family_id"]),
            family_kind=str(entry.get("family_kind") or "generic"),
            label=str(entry["label"]),
            slot_range_start=int(entry["slot_range_start"]),
            slot_count=int(entry["slot_count"]),
            targeting=str(entry["targeting"]),
            cooldown_family=str(entry["cooldown_family"]),
            supports_true_pet=bool(entry["supports_true_pet"]),
            supports_multi_pet=bool(entry["supports_multi_pet"]),
            patch_seed_template=(str(entry["patch_seed_template"]) if entry.get("patch_seed_template") not in (None, "") else None),
            behavior_kinds=[str(kind) for kind in entry.get("behavior_kinds", [])],
        )
        for entry in raw.get("families", [])
    ]
    shells = [
        SpellShellDefinition(
            shell_key=str(entry["shell_key"]),
            spell_id=int(entry["spell_id"]),
            family_id=str(entry["family_id"]),
            label=str(entry["label"]),
            behavior_kind=str(entry["behavior_kind"]),
            targeting=str(entry.get("targeting") or "unknown"),
            required_level=int(entry.get("required_level") or 1),
            icon_hint=(str(entry["icon_hint"]) if entry.get("icon_hint") not in (None, "") else None),
            tooltip=(str(entry["tooltip"]) if entry.get("tooltip") not in (None, "") else None),
            client_presentation=(
                dict(entry["client_presentation"])
                if isinstance(entry.get("client_presentation"), dict)
                else None
            ),
            patch_state=(str(entry["patch_state"]) if entry.get("patch_state") not in (None, "") else None),
            notes=[str(note) for note in entry.get("notes", [])],
        )
        for entry in raw.get("shells", [])
    ]
    return SpellShellBank(
        schema_version=str(raw["schema_version"]),
        description=str(raw["description"]),
        client_patch_required=bool(raw.get("client_patch_required", True)),
        notes=[str(note) for note in raw.get("notes", [])],
        families=families,
        patch={str(key): str(value) for key, value in dict(raw.get("patch", {})).items()},
        shells=shells,
    )


def generate_patch_rows(path: str | Path | None = None) -> list[SpellShellPatchRow]:
    bank = load_spell_shell_bank(path)
    _validate_bank(bank)
    rows_by_spell_id: dict[int, SpellShellPatchRow] = {}

    for family in bank.families:
        for index in range(family.slot_count):
            spell_id = family.slot_range_start + index
            rows_by_spell_id[spell_id] = SpellShellPatchRow(
                spell_id=spell_id,
                family_id=family.family_id,
                shell_key=f"{family.family_id}_{index + 1:04d}",
                label=f"{family.label} {index + 1:04d}",
                targeting=family.targeting,
                cooldown_family=family.cooldown_family,
                seed_template=family.patch_seed_template,
                slot_index=index,
                is_named_override=False,
            )

    for shell in bank.shells:
        family = bank.family_by_id(shell.family_id)
        if family is None:
            raise ValueError(f"Shell `{shell.shell_key}` references unknown family `{shell.family_id}`.")
        slot_index = shell.spell_id - family.slot_range_start
        if slot_index < 0 or slot_index >= family.slot_count:
            raise ValueError(
                f"Shell `{shell.shell_key}` with spell {shell.spell_id} is outside family `{shell.family_id}` range."
            )
        rows_by_spell_id[shell.spell_id] = SpellShellPatchRow(
            spell_id=shell.spell_id,
            family_id=shell.family_id,
            shell_key=shell.shell_key,
            label=shell.label,
            targeting=shell.targeting,
            cooldown_family=family.cooldown_family,
            seed_template=family.patch_seed_template,
            slot_index=slot_index,
            is_named_override=True,
            behavior_kind=shell.behavior_kind,
            required_level=shell.required_level,
            icon_hint=shell.icon_hint,
            tooltip=shell.tooltip,
            client_presentation=dict(shell.client_presentation or {}),
            patch_state=shell.patch_state,
            notes=list(shell.notes),
        )

    return [rows_by_spell_id[spell_id] for spell_id in sorted(rows_by_spell_id)]


def _validate_bank(bank: SpellShellBank) -> None:
    seen_family_ids: set[str] = set()
    for family in bank.families:
        if family.family_id in seen_family_ids:
            raise ValueError(f"Duplicate shell family id `{family.family_id}`.")
        seen_family_ids.add(family.family_id)
    ordered_families = sorted(bank.families, key=lambda family: family.slot_range_start)
    previous_end: int | None = None
    previous_id: str | None = None
    for family in ordered_families:
        if previous_end is not None and family.slot_range_start <= previous_end:
            raise ValueError(f"Shell family `{family.family_id}` overlaps `{previous_id}`.")
        previous_end = family.slot_range_end
        previous_id = family.family_id
    seen_shell_keys: set[str] = set()
    seen_shell_ids: set[int] = set()
    for shell in bank.shells:
        if shell.shell_key in seen_shell_keys:
            raise ValueError(f"Duplicate shell key `{shell.shell_key}`.")
        if shell.spell_id in seen_shell_ids:
            raise ValueError(f"Duplicate shell spell id `{shell.spell_id}`.")
        seen_shell_keys.add(shell.shell_key)
        seen_shell_ids.add(shell.spell_id)


def build_patch_plan(path: str | Path | None = None) -> dict[str, Any]:
    bank = load_spell_shell_bank(path)
    rows = generate_patch_rows(path)
    return {
        "schema_version": "wm.spell_shell_patch_plan.v1",
        "source_contract": str(Path(path) if path is not None else default_shell_bank_path()),
        "artifact_version": bank.patch.get("artifact_version", "wm_spell_shell_bank.v1"),
        "generation_mode": bank.patch.get("generation_mode", "explicit"),
        "family_count": len(bank.families),
        "generic_family_count": len(bank.generic_families),
        "slots_per_family": int(bank.patch.get("slots_per_family", "0") or 0),
        "reserve_gap_slots": int(bank.patch.get("reserve_gap_slots", "0") or 0),
        "total_rows": len(rows),
        "named_override_count": sum(1 for row in rows if row.is_named_override),
        "families": [
            {
                "family_id": family.family_id,
                "family_kind": family.family_kind,
                "slot_range_start": family.slot_range_start,
                "slot_range_end": family.slot_range_end,
                "slot_count": family.slot_count,
                "seed_template": family.patch_seed_template,
            }
            for family in bank.families
        ],
        "rows": [row.to_dict() for row in rows],
    }
