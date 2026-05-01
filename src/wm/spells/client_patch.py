from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from wm.spells.server_dbc import SpellDbcFile
from wm.spells.server_dbc import inspect_spell_dbc
from wm.spells.server_dbc import load_spell_dbc
from wm.spells.server_dbc import select_shell_patch_rows
from wm.spells.server_dbc import write_spell_dbc
from wm.spells.shell_bank import SpellShellPatchRow
from wm.spells.shell_bank import default_shell_bank_path


CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS: dict[str, int] = {
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

SPELL_NAME_START_FIELD = 136
SPELL_NAME_FLAGS_FIELD = 152
SPELL_RANK_START_FIELD = 153
SPELL_RANK_FLAGS_FIELD = 169
SPELL_DESCRIPTION_START_FIELD = 170
SPELL_DESCRIPTION_FLAGS_FIELD = 186
SPELL_TOOLTIP_START_FIELD = 187
SPELL_TOOLTIP_FLAGS_FIELD = 203
LOCALIZED_FIELD_COUNT = 16
CATEGORY_FIELD = 1
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

SKILL_LINE_ABILITY_ID_FIELD = 0
SKILL_LINE_ABILITY_SKILL_LINE_FIELD = 1
SKILL_LINE_ABILITY_SPELL_FIELD = 2
SKILL_LINE_ABILITY_RACE_MASK_FIELD = 3
SKILL_LINE_ABILITY_CLASS_MASK_FIELD = 4
SKILL_LINE_ABILITY_MIN_SKILL_LINE_RANK_FIELD = 7
SKILL_LINE_ABILITY_ACQUIRE_METHOD_FIELD = 9

SKILL_RACE_CLASS_INFO_ID_FIELD = 0
SKILL_RACE_CLASS_INFO_SKILL_ID_FIELD = 1
SKILL_RACE_CLASS_INFO_RACE_MASK_FIELD = 2
SKILL_RACE_CLASS_INFO_CLASS_MASK_FIELD = 3
SKILL_RACE_CLASS_INFO_FLAGS_FIELD = 4
SKILL_RACE_CLASS_INFO_MIN_LEVEL_FIELD = 5
SKILL_RACE_CLASS_INFO_SKILL_TIER_ID_FIELD = 6
SKILL_RACE_CLASS_INFO_SKILL_COST_INDEX_FIELD = 7

CLIENT_ALL_PLAYER_RACE_MASK = 2047
CLIENT_ROGUE_CLASS_MASK = 8
CLIENT_SKILL_FLAG_WEAPON_OR_ARMOR = 128
# AzerothCore enum: 2 means learned/removed together with the whole skill.
# This keeps the DBC row global but makes the actual grant depend on WM adding
# the skill to the explicit character, instead of using class creation tables.
CLIENT_SKILL_ACQUIRE_ON_SKILL_LEARN = 2
ATTRIBUTES_FIELD = 4
ATTRIBUTES_EX_FIELD = 5
ATTRIBUTES_EX_2_FIELD = 6
ATTRIBUTES_EX_3_FIELD = 7
ATTRIBUTES_EX_4_FIELD = 8
ATTRIBUTES_EX_5_FIELD = 9
ATTRIBUTES_EX_6_FIELD = 10
ATTRIBUTES_EX_7_FIELD = 11
INTERRUPT_FLAGS_FIELD = 31
AURA_INTERRUPT_FLAGS_FIELD = 32
CHANNEL_INTERRUPT_FLAGS_FIELD = 33
DAMAGE_CLASS_FIELD = 213
PREVENTION_TYPE_FIELD = 214

COMBAT_PROFICIENCY_SKILL_RACE_CLASS_ROWS: tuple[tuple[int, int, int, int, int, int, int, int], ...] = (
    (100055, 55, CLIENT_ALL_PLAYER_RACE_MASK, CLIENT_ROGUE_CLASS_MASK, CLIENT_SKILL_FLAG_WEAPON_OR_ARMOR, 0, 0, 0),
    (100172, 172, CLIENT_ALL_PLAYER_RACE_MASK, CLIENT_ROGUE_CLASS_MASK, CLIENT_SKILL_FLAG_WEAPON_OR_ARMOR, 0, 0, 0),
    (100229, 229, CLIENT_ALL_PLAYER_RACE_MASK, CLIENT_ROGUE_CLASS_MASK, CLIENT_SKILL_FLAG_WEAPON_OR_ARMOR, 0, 0, 0),
    (100293, 293, CLIENT_ALL_PLAYER_RACE_MASK, CLIENT_ROGUE_CLASS_MASK, CLIENT_SKILL_FLAG_WEAPON_OR_ARMOR, 40, 0, 0),
    (100413, 413, CLIENT_ALL_PLAYER_RACE_MASK, CLIENT_ROGUE_CLASS_MASK, CLIENT_SKILL_FLAG_WEAPON_OR_ARMOR, 0, 0, 0),
)

COMBAT_PROFICIENCY_SKILL_LINE_ABILITY_ROWS: tuple[tuple[int, int, int, int, int, int, int, int, int, int, int, int, int, int], ...] = (
    (100055, 55, 202, 0, CLIENT_ROGUE_CLASS_MASK, 0, 0, 1, 0, CLIENT_SKILL_ACQUIRE_ON_SKILL_LEARN, 0, 0, 0, 0),
    (100172, 172, 197, 0, CLIENT_ROGUE_CLASS_MASK, 0, 0, 1, 0, CLIENT_SKILL_ACQUIRE_ON_SKILL_LEARN, 0, 0, 0, 0),
    (100229, 229, 200, 0, CLIENT_ROGUE_CLASS_MASK, 0, 0, 1, 0, CLIENT_SKILL_ACQUIRE_ON_SKILL_LEARN, 0, 0, 0, 0),
    (100293, 293, 750, 0, CLIENT_ROGUE_CLASS_MASK, 0, 0, 1, 0, CLIENT_SKILL_ACQUIRE_ON_SKILL_LEARN, 0, 0, 0, 0),
    (100413, 413, 8737, 0, CLIENT_ROGUE_CLASS_MASK, 0, 0, 1, 0, CLIENT_SKILL_ACQUIRE_ON_SKILL_LEARN, 0, 0, 0, 0),
)


@dataclass(slots=True)
class ClientSpellDbcMaterializationResult:
    source_dbc: str
    source_spell_icon_dbc: str | None
    out: str
    include: str
    selected_spell_ids: list[int]
    appended_count: int
    replaced_count: int
    presentation_applied_spell_ids: list[int]
    source_seed_spell_ids: dict[str, int]
    inspection: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ClientSkillLineAbilityDbcMaterializationResult:
    source_dbc: str
    out: str
    include: str
    selected_spell_ids: list[int]
    appended_count: int
    combat_proficiency_appended_count: int
    replaced_count: int
    skipped_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ClientSkillRaceClassInfoDbcMaterializationResult:
    source_dbc: str
    out: str
    appended_count: int
    replaced_count: int
    combat_proficiency_skill_ids: list[int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ClientPatchPackageResult:
    source_dbc: str
    payload_spell_dbc: str
    payload_skill_line_ability_dbc: str
    payload_skill_race_class_info_dbc: str
    package_out: str
    mpq_editor: str
    installed_to: str | None
    selected_spell_ids: list[int]
    verify_extracted_spell_dbc: str
    verify_extracted_skill_line_ability_dbc: str
    verify_extracted_skill_race_class_info_dbc: str
    materialization: dict[str, object]
    skill_line_ability_materialization: dict[str, object]
    skill_race_class_info_materialization: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_state_dir() -> Path:
    return repo_root().joinpath(".wm-bootstrap", "state", "client-patches", "wm_spell_shell_bank")


def default_payload_spell_dbc_path() -> Path:
    return default_state_dir().joinpath("payload", "DBFilesClient", "Spell.dbc")


def default_payload_skill_line_ability_dbc_path() -> Path:
    return default_state_dir().joinpath("payload", "DBFilesClient", "SkillLineAbility.dbc")


def default_payload_skill_race_class_info_dbc_path() -> Path:
    return default_state_dir().joinpath("payload", "DBFilesClient", "SkillRaceClassInfo.dbc")


def default_package_path() -> Path:
    return default_state_dir().joinpath("patch-z.mpq")


def default_mpq_editor_path() -> Path:
    return repo_root().joinpath(".wm-bootstrap", "tools", "mpqeditor", "x64", "MPQEditor.exe")


def default_source_dbc_path() -> Path:
    return Path(r"D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc")


def default_source_spell_icon_dbc_path() -> Path:
    return default_source_dbc_path().parent.joinpath("SpellIcon.dbc")


def default_source_skill_line_ability_dbc_path() -> Path:
    return default_source_dbc_path().parent.joinpath("SkillLineAbility.dbc")


def default_source_skill_race_class_info_dbc_path() -> Path:
    return default_source_dbc_path().parent.joinpath("SkillRaceClassInfo.dbc")


def default_install_path() -> Path:
    return Path(r"D:\WOW\world of warcraft 3.3.5a hd\Data\patch-z.mpq")


def materialize_client_spell_dbc(
    *,
    source_dbc: str | Path,
    out: str | Path,
    include: str = "all",
    shell_bank_path: str | Path | None = None,
    spell_ids: list[int] | None = None,
    source_spell_icon_dbc: str | Path | None = None,
) -> ClientSpellDbcMaterializationResult:
    selected_rows = select_shell_patch_rows(
        shell_bank_path=shell_bank_path or default_shell_bank_path(),
        include=include,
        spell_ids=spell_ids,
    )
    dbc = load_spell_dbc(source_dbc)
    icon_ids_by_name = (
        _load_spell_icon_ids_by_name(source_spell_icon_dbc)
        if source_spell_icon_dbc is not None and Path(source_spell_icon_dbc).exists()
        else {}
    )
    source_index_by_id = dbc.id_to_index()
    source_records_by_seed_id: dict[int, bytes] = {}
    for row in selected_rows:
        if row.seed_template is None:
            raise ValueError(f"Shell spell {row.spell_id} does not declare a seed template.")
        if row.seed_template not in CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS:
            raise ValueError(
                f"Unsupported client Spell.dbc seed template `{row.seed_template}` for shell spell {row.spell_id}."
            )
        seed_spell_id = CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS[row.seed_template]
        seed_index = source_index_by_id.get(seed_spell_id)
        if seed_index is None:
            raise ValueError(
                f"Seed spell id {seed_spell_id} for template `{row.seed_template}` was not found in {source_dbc}."
            )
        source_records_by_seed_id.setdefault(seed_spell_id, dbc.records[seed_index])

    string_block = bytearray(dbc.string_block)
    working_records = [bytearray(record) for record in dbc.records]
    working_index_by_id = dbc.id_to_index()
    appended_count = 0
    replaced_count = 0
    presentation_applied_spell_ids: list[int] = []
    for row in selected_rows:
        seed_spell_id = CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS[str(row.seed_template)]
        materialized = bytearray(source_records_by_seed_id[seed_spell_id])
        _set_field(materialized, 0, int(row.spell_id))
        _zero_reagents(materialized)
        if row.required_level is not None:
            _set_field(materialized, BASE_LEVEL_FIELD, max(1, int(row.required_level)))
            _set_field(materialized, SPELL_LEVEL_FIELD, max(1, int(row.required_level)))
        _set_field(materialized, MANA_COST_FIELD, 0)
        if _apply_client_presentation(materialized, row, icon_ids_by_name):
            presentation_applied_spell_ids.append(int(row.spell_id))
        _apply_client_text(materialized, string_block, row)

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
            string_block_size=len(string_block),
            records=[bytes(record) for record in working_records],
            string_block=bytes(string_block),
        ),
    )
    selected_spell_ids = [int(row.spell_id) for row in selected_rows]
    inspection = inspect_spell_dbc(written_path, spell_ids=selected_spell_ids)
    return ClientSpellDbcMaterializationResult(
        source_dbc=str(Path(source_dbc)),
        source_spell_icon_dbc=str(Path(source_spell_icon_dbc)) if source_spell_icon_dbc is not None else None,
        out=str(written_path),
        include=str(include),
        selected_spell_ids=selected_spell_ids,
        appended_count=appended_count,
        replaced_count=replaced_count,
        presentation_applied_spell_ids=presentation_applied_spell_ids,
        source_seed_spell_ids=dict(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS),
        inspection=inspection.to_dict(),
    )


def materialize_client_skill_line_ability_dbc(
    *,
    source_dbc: str | Path,
    out: str | Path,
    include: str = "all",
    shell_bank_path: str | Path | None = None,
    spell_ids: list[int] | None = None,
) -> ClientSkillLineAbilityDbcMaterializationResult:
    selected_rows = select_shell_patch_rows(
        shell_bank_path=shell_bank_path or default_shell_bank_path(),
        include=include,
        spell_ids=spell_ids,
    )
    dbc = load_spell_dbc(source_dbc)
    if dbc.field_count < 10:
        raise ValueError(f"SkillLineAbility.dbc has too few fields: {source_dbc}")

    source_records_by_seed_spell_id = {
        _field(record, SKILL_LINE_ABILITY_SPELL_FIELD): record
        for record in dbc.records
    }
    spellbook_rows = [
        row
        for row in selected_rows
        if _presentation_int(row, "spellbook_seed_spell_id") is not None
    ]

    target_spell_ids = {int(row.spell_id) for row in spellbook_rows}
    target_ability_ids = {
        int(_presentation_int(row, "spellbook_ability_id") or (1_000_000 + int(row.spell_id)))
        for row in spellbook_rows
    }
    combat_proficiency_ability_ids = {row[0] for row in COMBAT_PROFICIENCY_SKILL_LINE_ABILITY_ROWS}
    combat_proficiency_spell_ids = {row[2] for row in COMBAT_PROFICIENCY_SKILL_LINE_ABILITY_ROWS}
    working_records = [
        bytearray(record)
        for record in dbc.records
        if _field(record, SKILL_LINE_ABILITY_SPELL_FIELD) not in target_spell_ids
        and _field(record, SKILL_LINE_ABILITY_ID_FIELD) not in target_ability_ids
        and _field(record, SKILL_LINE_ABILITY_ID_FIELD) not in combat_proficiency_ability_ids
        and not (
            _field(record, SKILL_LINE_ABILITY_SPELL_FIELD) in combat_proficiency_spell_ids
            and _field(record, SKILL_LINE_ABILITY_CLASS_MASK_FIELD) == CLIENT_ROGUE_CLASS_MASK
        )
    ]

    appended_count = 0
    replaced_count = len(dbc.records) - len(working_records)
    for row in spellbook_rows:
        presentation = dict(row.client_presentation or {})
        seed_spell_id = int(presentation["spellbook_seed_spell_id"])
        seed_record = source_records_by_seed_spell_id.get(seed_spell_id)
        if seed_record is None:
            raise ValueError(
                f"SkillLineAbility seed spell id {seed_spell_id} for shell spell {row.spell_id} "
                f"was not found in {source_dbc}."
            )
        materialized = bytearray(seed_record)
        _set_field(
            materialized,
            SKILL_LINE_ABILITY_ID_FIELD,
            int(presentation.get("spellbook_ability_id") or (1_000_000 + int(row.spell_id))),
        )
        _set_field(materialized, SKILL_LINE_ABILITY_SPELL_FIELD, int(row.spell_id))
        if "spellbook_skill_line_id" in presentation:
            _set_field(materialized, SKILL_LINE_ABILITY_SKILL_LINE_FIELD, int(presentation["spellbook_skill_line_id"]))
        if "spellbook_acquire_method" in presentation:
            _set_field(
                materialized,
                SKILL_LINE_ABILITY_ACQUIRE_METHOD_FIELD,
                int(presentation["spellbook_acquire_method"]),
            )
        working_records.append(materialized)
        appended_count += 1

    combat_proficiency_appended_count = 0
    for row in COMBAT_PROFICIENCY_SKILL_LINE_ABILITY_ROWS:
        working_records.append(bytearray(_pack_uint_record(row, dbc.field_count)))
        combat_proficiency_appended_count += 1

    written_path = write_spell_dbc(
        out,
        SpellDbcFile(
            path=str(Path(out)),
            signature=dbc.signature,
            record_count=len(working_records),
            field_count=dbc.field_count,
            record_size=dbc.record_size,
            string_block_size=dbc.string_block_size,
            records=[bytes(record) for record in working_records],
            string_block=dbc.string_block,
        ),
    )
    return ClientSkillLineAbilityDbcMaterializationResult(
        source_dbc=str(Path(source_dbc)),
        out=str(written_path),
        include=str(include),
        selected_spell_ids=[int(row.spell_id) for row in spellbook_rows],
        appended_count=appended_count,
        combat_proficiency_appended_count=combat_proficiency_appended_count,
        replaced_count=replaced_count,
        skipped_count=len(selected_rows) - len(spellbook_rows),
    )


def materialize_client_skill_race_class_info_dbc(
    *,
    source_dbc: str | Path,
    out: str | Path,
) -> ClientSkillRaceClassInfoDbcMaterializationResult:
    dbc = load_spell_dbc(source_dbc)
    if dbc.field_count < 8:
        raise ValueError(f"SkillRaceClassInfo.dbc has too few fields: {source_dbc}")

    target_ids = {row[0] for row in COMBAT_PROFICIENCY_SKILL_RACE_CLASS_ROWS}
    target_skill_ids = {row[1] for row in COMBAT_PROFICIENCY_SKILL_RACE_CLASS_ROWS}
    working_records = [
        bytearray(record)
        for record in dbc.records
        if _field(record, SKILL_RACE_CLASS_INFO_ID_FIELD) not in target_ids
        and not (
            _field(record, SKILL_RACE_CLASS_INFO_SKILL_ID_FIELD) in target_skill_ids
            and _field(record, SKILL_RACE_CLASS_INFO_CLASS_MASK_FIELD) == CLIENT_ROGUE_CLASS_MASK
        )
    ]
    replaced_count = len(dbc.records) - len(working_records)
    appended_count = 0
    for row in COMBAT_PROFICIENCY_SKILL_RACE_CLASS_ROWS:
        working_records.append(bytearray(_pack_uint_record(row, dbc.field_count)))
        appended_count += 1

    written_path = write_spell_dbc(
        out,
        SpellDbcFile(
            path=str(Path(out)),
            signature=dbc.signature,
            record_count=len(working_records),
            field_count=dbc.field_count,
            record_size=dbc.record_size,
            string_block_size=dbc.string_block_size,
            records=[bytes(record) for record in working_records],
            string_block=dbc.string_block,
        ),
    )
    return ClientSkillRaceClassInfoDbcMaterializationResult(
        source_dbc=str(Path(source_dbc)),
        out=str(written_path),
        appended_count=appended_count,
        replaced_count=replaced_count,
        combat_proficiency_skill_ids=[row[1] for row in COMBAT_PROFICIENCY_SKILL_RACE_CLASS_ROWS],
    )


def build_client_patch_package(
    *,
    source_dbc: str | Path,
    package_out: str | Path,
    mpq_editor: str | Path,
    payload_spell_dbc: str | Path = default_payload_spell_dbc_path(),
    source_spell_icon_dbc: str | Path | None = None,
    source_skill_line_ability_dbc: str | Path | None = None,
    source_skill_race_class_info_dbc: str | Path | None = None,
    payload_skill_line_ability_dbc: str | Path = default_payload_skill_line_ability_dbc_path(),
    payload_skill_race_class_info_dbc: str | Path = default_payload_skill_race_class_info_dbc_path(),
    include: str = "all",
    shell_bank_path: str | Path | None = None,
    spell_ids: list[int] | None = None,
    install_path: str | Path | None = None,
) -> ClientPatchPackageResult:
    source_spell_icon_dbc = (
        source_spell_icon_dbc
        if source_spell_icon_dbc is not None
        else Path(source_dbc).parent.joinpath("SpellIcon.dbc")
    )
    source_skill_line_ability_dbc = (
        source_skill_line_ability_dbc
        if source_skill_line_ability_dbc is not None
        else Path(source_dbc).parent.joinpath("SkillLineAbility.dbc")
    )
    source_skill_race_class_info_dbc = (
        source_skill_race_class_info_dbc
        if source_skill_race_class_info_dbc is not None
        else Path(source_dbc).parent.joinpath("SkillRaceClassInfo.dbc")
    )
    materialization = materialize_client_spell_dbc(
        source_dbc=source_dbc,
        out=payload_spell_dbc,
        include=include,
        shell_bank_path=shell_bank_path,
        spell_ids=spell_ids,
        source_spell_icon_dbc=source_spell_icon_dbc,
    )
    skill_line_ability_materialization = materialize_client_skill_line_ability_dbc(
        source_dbc=source_skill_line_ability_dbc,
        out=payload_skill_line_ability_dbc,
        include=include,
        shell_bank_path=shell_bank_path,
        spell_ids=spell_ids,
    )
    skill_race_class_info_materialization = materialize_client_skill_race_class_info_dbc(
        source_dbc=source_skill_race_class_info_dbc,
        out=payload_skill_race_class_info_dbc,
    )
    package_path = Path(package_out)
    package_path.parent.mkdir(parents=True, exist_ok=True)
    mpq_editor_path = Path(mpq_editor)
    if not mpq_editor_path.exists():
        raise FileNotFoundError(f"MPQEditor.exe not found: {mpq_editor_path}")

    work_dir = package_path.parent.joinpath("mpq-work")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_payload = work_dir.joinpath("DBFilesClient")
    work_payload.mkdir(parents=True, exist_ok=True)
    shutil.copy2(payload_spell_dbc, work_payload.joinpath("Spell.dbc"))
    shutil.copy2(payload_skill_line_ability_dbc, work_payload.joinpath("SkillLineAbility.dbc"))
    shutil.copy2(payload_skill_race_class_info_dbc, work_payload.joinpath("SkillRaceClassInfo.dbc"))

    work_package_name = package_path.name
    _run_mpq_editor(mpq_editor_path, ["new", work_package_name, "2048"], cwd=work_dir)
    _run_mpq_editor(
        mpq_editor_path,
        ["add", work_package_name, r"DBFilesClient\Spell.dbc", r"DBFilesClient\Spell.dbc", "/c"],
        cwd=work_dir,
    )
    _run_mpq_editor(
        mpq_editor_path,
        [
            "add",
            work_package_name,
            r"DBFilesClient\SkillLineAbility.dbc",
            r"DBFilesClient\SkillLineAbility.dbc",
            "/c",
        ],
        cwd=work_dir,
    )
    _run_mpq_editor(
        mpq_editor_path,
        [
            "add",
            work_package_name,
            r"DBFilesClient\SkillRaceClassInfo.dbc",
            r"DBFilesClient\SkillRaceClassInfo.dbc",
            "/c",
        ],
        cwd=work_dir,
    )
    _run_mpq_editor(mpq_editor_path, ["flush", work_package_name], cwd=work_dir)

    verify_dir = work_dir.joinpath("verify")
    verify_dir.mkdir(parents=True, exist_ok=True)
    _run_mpq_editor(
        mpq_editor_path,
        ["extract", work_package_name, r"DBFilesClient\Spell.dbc", str(verify_dir), "/fp"],
        cwd=work_dir,
    )
    verify_spell_dbc = verify_dir.joinpath("DBFilesClient", "Spell.dbc")
    if not verify_spell_dbc.exists():
        raise RuntimeError("MPQ verification failed: DBFilesClient\\Spell.dbc was not extractable.")
    _run_mpq_editor(
        mpq_editor_path,
        ["extract", work_package_name, r"DBFilesClient\SkillLineAbility.dbc", str(verify_dir), "/fp"],
        cwd=work_dir,
    )
    verify_skill_line_ability_dbc = verify_dir.joinpath("DBFilesClient", "SkillLineAbility.dbc")
    if not verify_skill_line_ability_dbc.exists():
        raise RuntimeError("MPQ verification failed: DBFilesClient\\SkillLineAbility.dbc was not extractable.")
    _run_mpq_editor(
        mpq_editor_path,
        ["extract", work_package_name, r"DBFilesClient\SkillRaceClassInfo.dbc", str(verify_dir), "/fp"],
        cwd=work_dir,
    )
    verify_skill_race_class_info_dbc = verify_dir.joinpath("DBFilesClient", "SkillRaceClassInfo.dbc")
    if not verify_skill_race_class_info_dbc.exists():
        raise RuntimeError("MPQ verification failed: DBFilesClient\\SkillRaceClassInfo.dbc was not extractable.")

    shutil.copy2(work_dir.joinpath(work_package_name), package_path)
    installed_to: str | None = None
    if install_path is not None:
        install_target = Path(install_path)
        install_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(package_path, install_target)
        installed_to = str(install_target)

    return ClientPatchPackageResult(
        source_dbc=str(Path(source_dbc)),
        payload_spell_dbc=str(Path(payload_spell_dbc)),
        payload_skill_line_ability_dbc=str(Path(payload_skill_line_ability_dbc)),
        payload_skill_race_class_info_dbc=str(Path(payload_skill_race_class_info_dbc)),
        package_out=str(package_path),
        mpq_editor=str(mpq_editor_path),
        installed_to=installed_to,
        selected_spell_ids=list(materialization.selected_spell_ids),
        verify_extracted_spell_dbc=str(verify_spell_dbc),
        verify_extracted_skill_line_ability_dbc=str(verify_skill_line_ability_dbc),
        verify_extracted_skill_race_class_info_dbc=str(verify_skill_race_class_info_dbc),
        materialization=materialization.to_dict(),
        skill_line_ability_materialization=skill_line_ability_materialization.to_dict(),
        skill_race_class_info_materialization=skill_race_class_info_materialization.to_dict(),
    )


def _run_mpq_editor(mpq_editor: Path, args: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(
        [str(mpq_editor), *args],
        cwd=str(cwd),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"MPQEditor failed with exit code {completed.returncode}: "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )


def _field(record: bytes | bytearray, field_index: int) -> int:
    start = int(field_index) * 4
    return int.from_bytes(record[start : start + 4], "little", signed=False)


def _set_field(record: bytearray, field_index: int, value: int) -> None:
    start = int(field_index) * 4
    record[start : start + 4] = int(value).to_bytes(4, "little", signed=False)


def _set_signed_field(record: bytearray, field_index: int, value: int) -> None:
    start = int(field_index) * 4
    record[start : start + 4] = int(value).to_bytes(4, "little", signed=True)


def _pack_uint_record(values: tuple[int, ...], field_count: int) -> bytes:
    fields = [0] * int(field_count)
    for index, value in enumerate(values):
        if index >= len(fields):
            break
        fields[index] = int(value)
    return b"".join(value.to_bytes(4, "little", signed=False) for value in fields)


def _presentation_int(row: SpellShellPatchRow, key: str) -> int | None:
    value = dict(row.client_presentation or {}).get(key)
    if value is None:
        return None
    return int(value)


def _load_spell_icon_ids_by_name(source_spell_icon_dbc: str | Path) -> dict[str, int]:
    dbc = load_spell_dbc(source_spell_icon_dbc)
    if dbc.field_count < 2:
        raise ValueError(f"SpellIcon.dbc has too few fields: {source_spell_icon_dbc}")
    icon_ids_by_name: dict[str, int] = {}
    for record in dbc.records:
        icon_id = _field(record, 0)
        path_offset = _field(record, 1)
        icon_path = _string_at_offset(dbc.string_block, path_offset)
        if not icon_path:
            continue
        normalized_names = {
            icon_path.replace("/", "\\").lower(),
            icon_path.replace("/", "\\").split("\\")[-1].lower(),
        }
        for normalized_name in normalized_names:
            icon_ids_by_name.setdefault(normalized_name, icon_id)
    return icon_ids_by_name


def _string_at_offset(string_block: bytes, offset: int) -> str:
    if offset <= 0 or offset >= len(string_block):
        return ""
    end = string_block.find(b"\x00", offset)
    if end < 0:
        end = len(string_block)
    return string_block[offset:end].decode("utf-8", "replace")


def _resolve_icon_id(row: SpellShellPatchRow, icon_ids_by_name: dict[str, int]) -> int | None:
    explicit_icon_id = _presentation_int(row, "spell_icon_id")
    if explicit_icon_id is not None:
        return explicit_icon_id
    if not row.icon_hint:
        return None
    hint = row.icon_hint.replace("/", "\\").lower()
    candidates = [hint]
    if "\\" not in hint:
        candidates.append(f"interface\\icons\\{hint}")
    for candidate in candidates:
        if candidate in icon_ids_by_name:
            return icon_ids_by_name[candidate]
    return None


def _apply_client_presentation(
    record: bytearray,
    row: SpellShellPatchRow,
    icon_ids_by_name: dict[str, int],
) -> bool:
    presentation = dict(row.client_presentation or {})
    changed = False
    icon_id = _resolve_icon_id(row, icon_ids_by_name)
    if icon_id is not None:
        _set_field(record, SPELL_ICON_ID_FIELD, icon_id)
        if "active_icon_id" not in presentation:
            _set_field(record, ACTIVE_ICON_ID_FIELD, 0)
        changed = True
    for key, field_index in {
        "category": CATEGORY_FIELD,
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
        "cast_time_index": CASTING_TIME_INDEX_FIELD,
        "power_type": POWER_TYPE_FIELD,
        "mana_cost": MANA_COST_FIELD,
        "spell_visual_id_1": SPELL_VISUAL_ID_1_FIELD,
        "spell_visual_id_2": SPELL_VISUAL_ID_2_FIELD,
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
            _set_field(record, field_index, int(presentation[key]))
            changed = True
    for key, field_index in {
        "equipped_item_class": EQUIPPED_ITEM_CLASS_FIELD,
        "equipped_item_subclass_mask": EQUIPPED_ITEM_SUBCLASS_MASK_FIELD,
        "equipped_item_inventory_type_mask": EQUIPPED_ITEM_INVENTORY_TYPE_MASK_FIELD,
        "effect_misc_value_1": EFFECT_MISC_VALUE_1_FIELD,
        "effect_misc_value_2": EFFECT_MISC_VALUE_2_FIELD,
        "effect_misc_value_3": EFFECT_MISC_VALUE_3_FIELD,
    }.items():
        if key in presentation:
            _set_signed_field(record, field_index, int(presentation[key]))
            changed = True
    for reagent_index in range(1, REAGENT_SLOT_COUNT + 1):
        item_key = f"reagent_{reagent_index}_item_id"
        count_key = f"reagent_{reagent_index}_count"
        if item_key in presentation:
            _set_field(record, REAGENT_START_FIELD + reagent_index - 1, int(presentation[item_key]))
            changed = True
        if count_key in presentation:
            _set_field(record, REAGENT_COUNT_START_FIELD + reagent_index - 1, int(presentation[count_key]))
            changed = True
    return changed


def _append_string(string_block: bytearray, text: str) -> int:
    offset = len(string_block)
    string_block.extend(text.encode("utf-8"))
    string_block.append(0)
    return offset


def _apply_localized_string(record: bytearray, start_field: int, flags_field: int, offset: int) -> None:
    for field_index in range(start_field, start_field + LOCALIZED_FIELD_COUNT):
        _set_field(record, field_index, offset)
    _set_field(record, flags_field, 0x00FF_FFFE)


def _apply_client_text(record: bytearray, string_block: bytearray, row: SpellShellPatchRow) -> None:
    label_offset = _append_string(string_block, row.label)
    tooltip = row.tooltip or f"WM shell {row.shell_key}."
    tooltip_offset = _append_string(string_block, tooltip)
    _apply_localized_string(record, SPELL_NAME_START_FIELD, SPELL_NAME_FLAGS_FIELD, label_offset)
    _apply_localized_string(record, SPELL_DESCRIPTION_START_FIELD, SPELL_DESCRIPTION_FLAGS_FIELD, tooltip_offset)
    _apply_localized_string(record, SPELL_TOOLTIP_START_FIELD, SPELL_TOOLTIP_FLAGS_FIELD, tooltip_offset)
    for field_index in range(SPELL_RANK_START_FIELD, SPELL_RANK_START_FIELD + LOCALIZED_FIELD_COUNT):
        _set_field(record, field_index, 0)
    _set_field(record, SPELL_RANK_FLAGS_FIELD, 0x00FF_FFEC)


def _zero_reagents(record: bytearray) -> None:
    for field_index in range(REAGENT_START_FIELD, REAGENT_START_FIELD + REAGENT_SLOT_COUNT):
        _set_field(record, field_index, 0)
    for field_index in range(REAGENT_COUNT_START_FIELD, REAGENT_COUNT_START_FIELD + REAGENT_SLOT_COUNT):
        _set_field(record, field_index, 0)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the local WM spell shell-bank client MPQ patch.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    materialize_parser = subparsers.add_parser("materialize", help="Write the client DBFilesClient\\Spell.dbc payload.")
    materialize_parser.add_argument("--source-dbc", default=str(default_source_dbc_path()))
    materialize_parser.add_argument("--source-spell-icon-dbc", default=str(default_source_spell_icon_dbc_path()))
    materialize_parser.add_argument("--out", default=str(default_payload_spell_dbc_path()))
    materialize_parser.add_argument("--shell-bank", default=None)
    materialize_parser.add_argument("--include", choices=["named", "all"], default="all")
    materialize_parser.add_argument("--spell-id", dest="spell_ids", action="append", type=int)
    materialize_parser.add_argument("--summary", action="store_true")

    build_parser = subparsers.add_parser("build", help="Materialize Spell.dbc and package patch-z.mpq.")
    build_parser.add_argument("--source-dbc", default=str(default_source_dbc_path()))
    build_parser.add_argument("--source-spell-icon-dbc", default=str(default_source_spell_icon_dbc_path()))
    build_parser.add_argument("--source-skill-line-ability-dbc", default=str(default_source_skill_line_ability_dbc_path()))
    build_parser.add_argument(
        "--source-skill-race-class-info-dbc",
        default=str(default_source_skill_race_class_info_dbc_path()),
    )
    build_parser.add_argument("--package-out", default=str(default_package_path()))
    build_parser.add_argument("--payload-spell-dbc", default=str(default_payload_spell_dbc_path()))
    build_parser.add_argument(
        "--payload-skill-line-ability-dbc",
        default=str(default_payload_skill_line_ability_dbc_path()),
    )
    build_parser.add_argument(
        "--payload-skill-race-class-info-dbc",
        default=str(default_payload_skill_race_class_info_dbc_path()),
    )
    build_parser.add_argument("--mpq-editor", default=str(default_mpq_editor_path()))
    build_parser.add_argument("--shell-bank", default=None)
    build_parser.add_argument("--include", choices=["named", "all"], default="all")
    build_parser.add_argument("--spell-id", dest="spell_ids", action="append", type=int)
    build_parser.add_argument("--install", action="store_true")
    build_parser.add_argument("--install-path", default=str(default_install_path()))
    build_parser.add_argument("--summary", action="store_true")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "materialize":
        result = materialize_client_spell_dbc(
            source_dbc=args.source_dbc,
            out=args.out,
            include=args.include,
            shell_bank_path=args.shell_bank,
            spell_ids=list(args.spell_ids or []),
            source_spell_icon_dbc=args.source_spell_icon_dbc,
        )
        if args.summary:
            print(json.dumps(result.to_dict(), ensure_ascii=False))
        else:
            print(result.out)
        return 0

    result = build_client_patch_package(
        source_dbc=args.source_dbc,
        package_out=args.package_out,
        payload_spell_dbc=args.payload_spell_dbc,
        source_spell_icon_dbc=args.source_spell_icon_dbc,
        source_skill_line_ability_dbc=args.source_skill_line_ability_dbc,
        source_skill_race_class_info_dbc=args.source_skill_race_class_info_dbc,
        payload_skill_line_ability_dbc=args.payload_skill_line_ability_dbc,
        payload_skill_race_class_info_dbc=args.payload_skill_race_class_info_dbc,
        mpq_editor=args.mpq_editor,
        include=args.include,
        shell_bank_path=args.shell_bank,
        spell_ids=list(args.spell_ids or []),
        install_path=args.install_path if args.install else None,
    )
    if args.summary:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print(result.package_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
