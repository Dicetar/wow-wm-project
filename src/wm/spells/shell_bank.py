from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SpellShellFamily:
    family_id: str
    label: str
    slot_range_start: int
    slot_count: int
    targeting: str
    cooldown_family: str
    supports_true_pet: bool
    supports_multi_pet: bool
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


def default_shell_bank_path() -> Path:
    return Path(__file__).resolve().parents[3].joinpath("control", "runtime", "spell_shell_bank.json")


def load_spell_shell_bank(path: str | Path | None = None) -> SpellShellBank:
    source = Path(path) if path is not None else default_shell_bank_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    families = [
        SpellShellFamily(
            family_id=str(entry["family_id"]),
            label=str(entry["label"]),
            slot_range_start=int(entry["slot_range_start"]),
            slot_count=int(entry["slot_count"]),
            targeting=str(entry["targeting"]),
            cooldown_family=str(entry["cooldown_family"]),
            supports_true_pet=bool(entry["supports_true_pet"]),
            supports_multi_pet=bool(entry["supports_multi_pet"]),
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
