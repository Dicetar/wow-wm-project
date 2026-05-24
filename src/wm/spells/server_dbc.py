from __future__ import annotations

import argparse
import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path

from wm.spells.shell_bank import SpellShellPatchRow
from wm.spells.shell_bank import default_shell_bank_path
from wm.spells.shell_bank import generate_patch_rows


SERVER_SEED_TEMPLATE_SOURCE_SPELL_IDS: dict[str, int] = {
    "wm_summon_pet": 133,
    "wm_passive_aura": 107,
    "wm_pet_active": 16827,
    "wm_watcher_marker": 24755,
    "wm_unit_target_projectile": 133,
    "wm_weapon_ranged_attack": 2764,
    "wm_friendly_target_effect": 2061,
    "wm_mind_blast": 8092,
    "wm_unit_target_effect": 770,
    "wm_target_centered_aoe": 27243,
    "wm_ground_target_aoe": 5740,
    "wm_caster_centered_aoe": 1449,
    "wm_self_aura": 1459,
    "wm_random_targets": 48505,
    "wm_frontal_cone": 120,
}

CASTABLE_SERVER_SEED_TEMPLATE_SOURCE_SPELL_IDS: dict[str, int] = {
    "wm_summon_pet": 49126,
    "wm_passive_aura": 107,
    "wm_pet_active": 16827,
    "wm_watcher_marker": 24755,
    "wm_unit_target_projectile": 133,
    "wm_weapon_ranged_attack": 2764,
    "wm_friendly_target_effect": 2061,
    "wm_mind_blast": 8092,
    "wm_unit_target_effect": 770,
    "wm_target_centered_aoe": 27243,
    "wm_ground_target_aoe": 5740,
    "wm_caster_centered_aoe": 1449,
    "wm_self_aura": 1459,
    "wm_random_targets": 48505,
    "wm_frontal_cone": 120,
}

ATTRIBUTES_FIELD = 4
ATTRIBUTES_EX_FIELD = 5
ATTRIBUTES_EX_2_FIELD = 6
ATTRIBUTES_EX_3_FIELD = 7
ATTRIBUTES_EX_4_FIELD = 8
ATTRIBUTES_EX_5_FIELD = 9
ATTRIBUTES_EX_6_FIELD = 10
ATTRIBUTES_EX_7_FIELD = 11
CATEGORY_FIELD = 1
INTERRUPT_FLAGS_FIELD = 31
AURA_INTERRUPT_FLAGS_FIELD = 32
CHANNEL_INTERRUPT_FLAGS_FIELD = 33
CASTING_TIME_INDEX_FIELD = 28
RECOVERY_TIME_FIELD = 29
CATEGORY_RECOVERY_TIME_FIELD = 30
DISPEL_TYPE_FIELD = 2
POWER_TYPE_FIELD = 41
MANA_COST_FIELD = 42
MAX_LEVEL_FIELD = 37
BASE_LEVEL_FIELD = 38
SPELL_LEVEL_FIELD = 39
DURATION_INDEX_FIELD = 40
STACK_AMOUNT_FIELD = 49
REAGENT_START_FIELD = 52
REAGENT_COUNT_START_FIELD = 60
REAGENT_SLOT_COUNT = 8
EQUIPPED_ITEM_CLASS_FIELD = 68
EQUIPPED_ITEM_SUBCLASS_MASK_FIELD = 69
EQUIPPED_ITEM_INVENTORY_TYPE_MASK_FIELD = 70
SPELL_ICON_ID_FIELD = 133
ACTIVE_ICON_ID_FIELD = 134
SPELL_PRIORITY_FIELD = 135
SPELL_VISUAL_ID_1_FIELD = 130
SPELL_VISUAL_ID_2_FIELD = 131
MANA_COST_PERCENTAGE_FIELD = 204
START_RECOVERY_CATEGORY_FIELD = 205
START_RECOVERY_TIME_FIELD = 206
SPELL_FAMILY_NAME_FIELD = 208
SPELL_FAMILY_FLAGS_1_FIELD = 209
SPELL_FAMILY_FLAGS_2_FIELD = 210
SPELL_FAMILY_FLAGS_3_FIELD = 211
STANCE_BAR_ORDER_FIELD = 215
RANGE_INDEX_FIELD = 46
EFFECT_1_FIELD = 71
EFFECT_2_FIELD = 72
EFFECT_3_FIELD = 73
EFFECT_DIE_SIDES_1_FIELD = 74
EFFECT_DIE_SIDES_2_FIELD = 75
EFFECT_DIE_SIDES_3_FIELD = 76
EFFECT_BASE_POINTS_1_FIELD = 80
EFFECT_BASE_POINTS_2_FIELD = 81
EFFECT_BASE_POINTS_3_FIELD = 82
EFFECT_IMPLICIT_TARGET_A_1_FIELD = 86
EFFECT_IMPLICIT_TARGET_A_2_FIELD = 87
EFFECT_IMPLICIT_TARGET_A_3_FIELD = 88
EFFECT_IMPLICIT_TARGET_B_1_FIELD = 89
EFFECT_IMPLICIT_TARGET_B_2_FIELD = 90
EFFECT_IMPLICIT_TARGET_B_3_FIELD = 91
EFFECT_APPLY_AURA_NAME_1_FIELD = 95
EFFECT_APPLY_AURA_NAME_2_FIELD = 96
EFFECT_APPLY_AURA_NAME_3_FIELD = 97
EFFECT_MISC_VALUE_1_FIELD = 110
EFFECT_MISC_VALUE_2_FIELD = 111
EFFECT_MISC_VALUE_3_FIELD = 112
DAMAGE_CLASS_FIELD = 213
PREVENTION_TYPE_FIELD = 214
SPELL_NAME_START_FIELD = 136
SPELL_NAME_FLAGS_FIELD = 152
SPELL_RANK_START_FIELD = 153
SPELL_RANK_FLAGS_FIELD = 169
SPELL_DESCRIPTION_START_FIELD = 170
SPELL_DESCRIPTION_FLAGS_FIELD = 186
SPELL_TOOLTIP_START_FIELD = 187
SPELL_TOOLTIP_FLAGS_FIELD = 203
LOCALIZED_FIELD_COUNT = 16


@dataclass(slots=True)
class SpellDbcFile:
    path: str
    signature: str
    record_count: int
    field_count: int
    record_size: int
    string_block_size: int
    records: list[bytes]
    string_block: bytes

    def id_to_index(self) -> dict[int, int]:
        return {record_spell_id(record): index for index, record in enumerate(self.records)}


@dataclass(slots=True)
class SpellDbcInspection:
    path: str
    record_count: int
    min_id: int | None
    max_id: int | None
    checked_ids: dict[int, bool]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class SpellDbcMaterializationResult:
    source_dbc: str
    out: str
    include: str
    seed_profile: str
    selected_spell_ids: list[int]
    appended_count: int
    replaced_count: int
    source_seed_spell_ids: dict[str, int]
    inspection: SpellDbcInspection

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["inspection"] = self.inspection.to_dict()
        return payload


def default_output_path() -> Path:
    return (
        Path(__file__)
        .resolve()
        .parents[3]
        .joinpath(".wm-bootstrap", "state", "client-patches", "wm_spell_shell_bank", "server-spell-dbc", "Spell.dbc")
    )


def record_spell_id(record: bytes) -> int:
    if len(record) < 4:
        raise ValueError("Spell.dbc record is too short to contain an id.")
    return int(struct.unpack_from("<I", record, 0)[0])


def load_spell_dbc(path: str | Path) -> SpellDbcFile:
    source_path = Path(path)
    with source_path.open("rb") as handle:
        header = handle.read(20)
        if len(header) != 20:
            raise ValueError(f"Spell.dbc header is incomplete: {source_path}")
        signature, record_count, field_count, record_size, string_block_size = struct.unpack("<4s4I", header)
        if signature != b"WDBC":
            raise ValueError(f"Unsupported Spell.dbc signature {signature!r} in {source_path}")
        records = []
        for _ in range(record_count):
            record = handle.read(record_size)
            if len(record) != record_size:
                raise ValueError(f"Spell.dbc record payload is truncated: {source_path}")
            records.append(record)
        string_block = handle.read(string_block_size)
        if len(string_block) != string_block_size:
            raise ValueError(f"Spell.dbc string block is truncated: {source_path}")
    return SpellDbcFile(
        path=str(source_path),
        signature=signature.decode("ascii", "replace"),
        record_count=record_count,
        field_count=field_count,
        record_size=record_size,
        string_block_size=string_block_size,
        records=records,
        string_block=string_block,
    )


def write_spell_dbc(path: str | Path, dbc: SpellDbcFile) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack(
        "<4s4I",
        dbc.signature.encode("ascii"),
        len(dbc.records),
        dbc.field_count,
        dbc.record_size,
        dbc.string_block_size,
    )
    with output_path.open("wb") as handle:
        handle.write(header)
        for record in dbc.records:
            if len(record) != dbc.record_size:
                raise ValueError(
                    f"Spell.dbc record length {len(record)} does not match declared record size {dbc.record_size}."
                )
            handle.write(record)
        handle.write(dbc.string_block)
    return output_path


def inspect_spell_dbc(path: str | Path, *, spell_ids: list[int] | None = None) -> SpellDbcInspection:
    dbc = load_spell_dbc(path)
    all_ids = [record_spell_id(record) for record in dbc.records]
    id_set = set(all_ids)
    checked = {int(spell_id): int(spell_id) in id_set for spell_id in list(spell_ids or [])}
    return SpellDbcInspection(
        path=str(Path(path)),
        record_count=len(all_ids),
        min_id=min(all_ids) if all_ids else None,
        max_id=max(all_ids) if all_ids else None,
        checked_ids=checked,
    )


def materialize_server_spell_dbc(
    *,
    source_dbc: str | Path,
    out: str | Path,
    include: str = "named",
    seed_profile: str = "learnable",
    shell_bank_path: str | Path | None = None,
    spell_ids: list[int] | None = None,
) -> SpellDbcMaterializationResult:
    seed_spell_ids = _seed_template_source_spell_ids(seed_profile)
    selected_rows = select_shell_patch_rows(
        shell_bank_path=shell_bank_path,
        include=include,
        spell_ids=spell_ids,
    )
    dbc = load_spell_dbc(source_dbc)
    source_index_by_id = dbc.id_to_index()
    source_records_by_seed_id: dict[int, bytes] = {}
    for row in selected_rows:
        if row.seed_template is None:
            raise ValueError(f"Shell spell {row.spell_id} does not declare a seed template.")
        if row.seed_template not in seed_spell_ids:
            raise ValueError(
                f"Unsupported server Spell.dbc seed template `{row.seed_template}` for shell spell {row.spell_id}."
            )
        seed_spell_id = seed_spell_ids[row.seed_template]
        seed_index = source_index_by_id.get(seed_spell_id)
        if seed_index is None:
            raise ValueError(
                f"Seed spell id {seed_spell_id} for template `{row.seed_template}` was not found in {source_dbc}."
            )
        source_records_by_seed_id.setdefault(seed_spell_id, dbc.records[seed_index])

    working_records = [bytearray(record) for record in dbc.records]
    working_index_by_id = dbc.id_to_index()
    working_string_block = bytearray(dbc.string_block)
    appended_count = 0
    replaced_count = 0
    for row in selected_rows:
        seed_spell_id = seed_spell_ids[str(row.seed_template)]
        materialized = bytearray(source_records_by_seed_id[seed_spell_id])
        struct.pack_into("<I", materialized, 0, int(row.spell_id))
        _apply_server_presentation(materialized, row)
        _apply_server_text(materialized, working_string_block, row)
        existing_index = working_index_by_id.get(int(row.spell_id))
        if existing_index is None:
            working_records.append(materialized)
            working_index_by_id[int(row.spell_id)] = len(working_records) - 1
            appended_count += 1
        else:
            working_records[existing_index] = materialized
            replaced_count += 1

    written_path = write_spell_dbc(
        out,
        SpellDbcFile(
            path=str(Path(out)),
            signature=dbc.signature,
            record_count=len(working_records),
            field_count=dbc.field_count,
            record_size=dbc.record_size,
            string_block_size=len(working_string_block),
            records=[bytes(record) for record in working_records],
            string_block=bytes(working_string_block),
        ),
    )
    selected_spell_ids = [int(row.spell_id) for row in selected_rows]
    inspection = inspect_spell_dbc(written_path, spell_ids=selected_spell_ids)
    return SpellDbcMaterializationResult(
        source_dbc=str(Path(source_dbc)),
        out=str(written_path),
        include=str(include),
        seed_profile=str(seed_profile),
        selected_spell_ids=selected_spell_ids,
        appended_count=appended_count,
        replaced_count=replaced_count,
        source_seed_spell_ids=dict(seed_spell_ids),
        inspection=inspection,
    )


def _seed_template_source_spell_ids(seed_profile: str) -> dict[str, int]:
    if seed_profile == "learnable":
        return SERVER_SEED_TEMPLATE_SOURCE_SPELL_IDS
    if seed_profile == "castable":
        return CASTABLE_SERVER_SEED_TEMPLATE_SOURCE_SPELL_IDS
    raise ValueError(f"Unsupported server Spell.dbc seed profile: {seed_profile}")


def _apply_server_presentation(record: bytearray, row: SpellShellPatchRow) -> None:
    if len(record) < (STANCE_BAR_ORDER_FIELD + 1) * 4:
        return
    presentation = dict(row.client_presentation or {})
    for key, field_index in {
        "category": CATEGORY_FIELD,
        "cast_time_index": CASTING_TIME_INDEX_FIELD,
        "dispel_type": DISPEL_TYPE_FIELD,
        "max_level": MAX_LEVEL_FIELD,
        "base_level": BASE_LEVEL_FIELD,
        "spell_level": SPELL_LEVEL_FIELD,
        "duration_index": DURATION_INDEX_FIELD,
        "stack_amount": STACK_AMOUNT_FIELD,
        "recovery_time": RECOVERY_TIME_FIELD,
        "category_recovery_time": CATEGORY_RECOVERY_TIME_FIELD,
        "effect_1": EFFECT_1_FIELD,
        "effect_2": EFFECT_2_FIELD,
        "effect_3": EFFECT_3_FIELD,
        "effect_die_sides_1": EFFECT_DIE_SIDES_1_FIELD,
        "effect_die_sides_2": EFFECT_DIE_SIDES_2_FIELD,
        "effect_die_sides_3": EFFECT_DIE_SIDES_3_FIELD,
        "effect_base_points_1": EFFECT_BASE_POINTS_1_FIELD,
        "effect_base_points_2": EFFECT_BASE_POINTS_2_FIELD,
        "effect_base_points_3": EFFECT_BASE_POINTS_3_FIELD,
        "effect_implicit_target_a_1": EFFECT_IMPLICIT_TARGET_A_1_FIELD,
        "effect_implicit_target_a_2": EFFECT_IMPLICIT_TARGET_A_2_FIELD,
        "effect_implicit_target_a_3": EFFECT_IMPLICIT_TARGET_A_3_FIELD,
        "effect_implicit_target_b_1": EFFECT_IMPLICIT_TARGET_B_1_FIELD,
        "effect_implicit_target_b_2": EFFECT_IMPLICIT_TARGET_B_2_FIELD,
        "effect_implicit_target_b_3": EFFECT_IMPLICIT_TARGET_B_3_FIELD,
        "effect_apply_aura_name_1": EFFECT_APPLY_AURA_NAME_1_FIELD,
        "effect_apply_aura_name_2": EFFECT_APPLY_AURA_NAME_2_FIELD,
        "effect_apply_aura_name_3": EFFECT_APPLY_AURA_NAME_3_FIELD,
        "power_type": POWER_TYPE_FIELD,
        "mana_cost": MANA_COST_FIELD,
        "spell_visual_id_1": SPELL_VISUAL_ID_1_FIELD,
        "spell_visual_id_2": SPELL_VISUAL_ID_2_FIELD,
        "spell_icon_id": SPELL_ICON_ID_FIELD,
        "active_icon_id": ACTIVE_ICON_ID_FIELD,
        "spell_priority": SPELL_PRIORITY_FIELD,
        "mana_cost_percentage": MANA_COST_PERCENTAGE_FIELD,
        "start_recovery_category": START_RECOVERY_CATEGORY_FIELD,
        "start_recovery_time": START_RECOVERY_TIME_FIELD,
        "spell_family_name": SPELL_FAMILY_NAME_FIELD,
        "spell_family_flags_1": SPELL_FAMILY_FLAGS_1_FIELD,
        "spell_family_flags_2": SPELL_FAMILY_FLAGS_2_FIELD,
        "spell_family_flags_3": SPELL_FAMILY_FLAGS_3_FIELD,
        "stance_bar_order": STANCE_BAR_ORDER_FIELD,
        "range_index": RANGE_INDEX_FIELD,
        "attributes": ATTRIBUTES_FIELD,
        "attributes_ex": ATTRIBUTES_EX_FIELD,
        "attributes_ex_2": ATTRIBUTES_EX_2_FIELD,
        "attributes_ex_3": ATTRIBUTES_EX_3_FIELD,
        "attributes_ex_4": ATTRIBUTES_EX_4_FIELD,
        "attributes_ex_5": ATTRIBUTES_EX_5_FIELD,
        "attributes_ex_6": ATTRIBUTES_EX_6_FIELD,
        "attributes_ex_7": ATTRIBUTES_EX_7_FIELD,
        "interrupt_flags": INTERRUPT_FLAGS_FIELD,
        "aura_interrupt_flags": AURA_INTERRUPT_FLAGS_FIELD,
        "channel_interrupt_flags": CHANNEL_INTERRUPT_FLAGS_FIELD,
        "damage_class": DAMAGE_CLASS_FIELD,
        "prevention_type": PREVENTION_TYPE_FIELD,
    }.items():
        if key in presentation:
            struct.pack_into("<I", record, field_index * 4, int(presentation[key]))
    for key, field_index in {
        "equipped_item_class": EQUIPPED_ITEM_CLASS_FIELD,
        "equipped_item_subclass_mask": EQUIPPED_ITEM_SUBCLASS_MASK_FIELD,
        "equipped_item_inventory_type_mask": EQUIPPED_ITEM_INVENTORY_TYPE_MASK_FIELD,
        "effect_misc_value_1": EFFECT_MISC_VALUE_1_FIELD,
        "effect_misc_value_2": EFFECT_MISC_VALUE_2_FIELD,
        "effect_misc_value_3": EFFECT_MISC_VALUE_3_FIELD,
    }.items():
        if key in presentation:
            struct.pack_into("<i", record, field_index * 4, int(presentation[key]))
    if "spell_icon_id" in presentation and "active_icon_id" not in presentation:
        struct.pack_into("<I", record, ACTIVE_ICON_ID_FIELD * 4, 0)
    for reagent_index in range(1, REAGENT_SLOT_COUNT + 1):
        item_key = f"reagent_{reagent_index}_item_id"
        count_key = f"reagent_{reagent_index}_count"
        if item_key in presentation:
            struct.pack_into(
                "<I",
                record,
                (REAGENT_START_FIELD + reagent_index - 1) * 4,
                int(presentation[item_key]),
            )
        if count_key in presentation:
            struct.pack_into(
                "<I",
                record,
                (REAGENT_COUNT_START_FIELD + reagent_index - 1) * 4,
                int(presentation[count_key]),
            )


def _append_string(string_block: bytearray, text: str) -> int:
    offset = len(string_block)
    string_block.extend(text.encode("utf-8"))
    string_block.append(0)
    return offset


def _apply_localized_string(record: bytearray, start_field: int, flags_field: int, offset: int) -> None:
    for field_index in range(start_field, start_field + LOCALIZED_FIELD_COUNT):
        struct.pack_into("<I", record, field_index * 4, offset)
    struct.pack_into("<I", record, flags_field * 4, 0x00FF_FFFE)


def _apply_server_text(record: bytearray, string_block: bytearray, row: SpellShellPatchRow) -> None:
    if len(record) < (SPELL_TOOLTIP_FLAGS_FIELD + 1) * 4:
        return
    label_offset = _append_string(string_block, row.label)
    tooltip = row.tooltip or f"WM shell {row.shell_key}."
    tooltip_offset = _append_string(string_block, tooltip)
    _apply_localized_string(record, SPELL_NAME_START_FIELD, SPELL_NAME_FLAGS_FIELD, label_offset)
    _apply_localized_string(record, SPELL_DESCRIPTION_START_FIELD, SPELL_DESCRIPTION_FLAGS_FIELD, tooltip_offset)
    _apply_localized_string(record, SPELL_TOOLTIP_START_FIELD, SPELL_TOOLTIP_FLAGS_FIELD, tooltip_offset)
    for field_index in range(SPELL_RANK_START_FIELD, SPELL_RANK_START_FIELD + LOCALIZED_FIELD_COUNT):
        struct.pack_into("<I", record, field_index * 4, 0)
    struct.pack_into("<I", record, SPELL_RANK_FLAGS_FIELD * 4, 0x00FF_FFEC)


def select_shell_patch_rows(
    *,
    shell_bank_path: str | Path | None = None,
    include: str = "named",
    spell_ids: list[int] | None = None,
) -> list[SpellShellPatchRow]:
    rows = generate_patch_rows(shell_bank_path or default_shell_bank_path())
    if include not in {"named", "all"}:
        raise ValueError(f"Unsupported include mode: {include}")
    if include == "named":
        rows = [row for row in rows if row.is_named_override]
    if spell_ids:
        requested_ids = {int(spell_id) for spell_id in spell_ids}
        selected = [row for row in rows if int(row.spell_id) in requested_ids]
        selected_ids = {int(row.spell_id) for row in selected}
        missing = sorted(requested_ids - selected_ids)
        if missing:
            raise ValueError(f"Requested spell ids are not part of the selected shell-bank rows: {missing}")
        rows = selected
    if not rows:
        raise ValueError("No shell-bank rows were selected for server Spell.dbc materialization.")
    return sorted(rows, key=lambda row: int(row.spell_id))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect or materialize server-known WM shell spell ids into a Spell.dbc copy."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a Spell.dbc for specific shell spell ids.")
    inspect_parser.add_argument("--spell-dbc", required=True, help="Path to the Spell.dbc file to inspect.")
    inspect_parser.add_argument(
        "--spell-id",
        dest="spell_ids",
        action="append",
        type=int,
        help="Specific spell id to check for presence. Repeatable.",
    )
    inspect_parser.add_argument("--summary", action="store_true")

    materialize_parser = subparsers.add_parser(
        "materialize",
        help="Clone shell seed rows into a server Spell.dbc copy so WM shell ids become server-known.",
    )
    materialize_parser.add_argument("--source-dbc", required=True, help="Input Spell.dbc path.")
    materialize_parser.add_argument("--out", default=str(default_output_path()), help="Output Spell.dbc path.")
    materialize_parser.add_argument(
        "--shell-bank",
        default=None,
        help="Optional path to spell_shell_bank.json. Defaults to the repo contract.",
    )
    materialize_parser.add_argument(
        "--include",
        choices=["named", "all"],
        default="named",
        help="Whether to materialize only named shells or the full shell-bank row set.",
    )
    materialize_parser.add_argument(
        "--seed-profile",
        choices=["learnable", "castable"],
        default="learnable",
        help=(
            "`learnable` keeps the neutral server-proof seed for grant/revoke validation; "
            "`castable` uses cast-shape seeds for visible client shell tests."
        ),
    )
    materialize_parser.add_argument(
        "--spell-id",
        dest="spell_ids",
        action="append",
        type=int,
        help="Restrict materialization to these shell spell ids. Repeatable.",
    )
    materialize_parser.add_argument("--summary", action="store_true")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "inspect":
        result = inspect_spell_dbc(args.spell_dbc, spell_ids=list(args.spell_ids or []))
        if args.summary:
            print(json.dumps(result.to_dict(), ensure_ascii=False))
        else:
            print(str(result.path))
        return 0

    result = materialize_server_spell_dbc(
        source_dbc=args.source_dbc,
        out=args.out,
        include=args.include,
        seed_profile=args.seed_profile,
        shell_bank_path=args.shell_bank,
        spell_ids=list(args.spell_ids or []),
    )
    if args.summary:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(result.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
