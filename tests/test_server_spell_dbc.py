from __future__ import annotations

import struct
from pathlib import Path

from wm.spells.server_dbc import ACTIVE_ICON_ID_FIELD
from wm.spells.server_dbc import CATEGORY_FIELD
from wm.spells.server_dbc import inspect_spell_dbc
from wm.spells.server_dbc import CATEGORY_RECOVERY_TIME_FIELD
from wm.spells.server_dbc import DISPEL_TYPE_FIELD
from wm.spells.server_dbc import DURATION_INDEX_FIELD
from wm.spells.server_dbc import EQUIPPED_ITEM_CLASS_FIELD
from wm.spells.server_dbc import EQUIPPED_ITEM_INVENTORY_TYPE_MASK_FIELD
from wm.spells.server_dbc import EQUIPPED_ITEM_SUBCLASS_MASK_FIELD
from wm.spells.server_dbc import EFFECT_1_FIELD
from wm.spells.server_dbc import EFFECT_APPLY_AURA_NAME_1_FIELD
from wm.spells.server_dbc import EFFECT_BASE_POINTS_1_FIELD
from wm.spells.server_dbc import EFFECT_DIE_SIDES_1_FIELD
from wm.spells.server_dbc import EFFECT_IMPLICIT_TARGET_A_1_FIELD
from wm.spells.server_dbc import EFFECT_MISC_VALUE_1_FIELD
from wm.spells.server_dbc import MANA_COST_FIELD
from wm.spells.server_dbc import POWER_TYPE_FIELD
from wm.spells.server_dbc import RECOVERY_TIME_FIELD
from wm.spells.server_dbc import materialize_server_spell_dbc
from wm.spells.server_dbc import REAGENT_COUNT_START_FIELD
from wm.spells.server_dbc import REAGENT_START_FIELD
from wm.spells.server_dbc import RANGE_INDEX_FIELD
from wm.spells.server_dbc import select_shell_patch_rows
from wm.spells.server_dbc import SPELL_FAMILY_FLAGS_1_FIELD
from wm.spells.server_dbc import SPELL_FAMILY_FLAGS_2_FIELD
from wm.spells.server_dbc import SPELL_FAMILY_FLAGS_3_FIELD
from wm.spells.server_dbc import SPELL_FAMILY_NAME_FIELD
from wm.spells.server_dbc import SPELL_ICON_ID_FIELD
from wm.spells.server_dbc import SPELL_PRIORITY_FIELD
from wm.spells.server_dbc import SPELL_VISUAL_ID_2_FIELD
from wm.spells.server_dbc import STACK_AMOUNT_FIELD
from wm.spells.server_dbc import STANCE_BAR_ORDER_FIELD
from wm.spells.server_dbc import START_RECOVERY_CATEGORY_FIELD
from wm.spells.server_dbc import START_RECOVERY_TIME_FIELD


ATTRIBUTES_FIELD = 4
AURA_INTERRUPT_FLAGS_FIELD = 32
CHANNEL_INTERRUPT_FLAGS_FIELD = 33
DAMAGE_CLASS_FIELD = 213
FULL_FIELD_COUNT = 234
FULL_RECORD_SIZE = FULL_FIELD_COUNT * 4
INTERRUPT_FLAGS_FIELD = 31
PREVENTION_TYPE_FIELD = 214
RANGED_WEAPON_SUBCLASS_MASK = 0x0005000C


def _write_test_spell_dbc(path: Path, records: list[tuple[int, int]]) -> None:
    record_size = 8
    field_count = 2
    string_block = b"\x00"
    payload = bytearray()
    for spell_id, marker in records:
        payload.extend(struct.pack("<II", int(spell_id), int(marker)))
    header = struct.pack("<4s4I", b"WDBC", len(records), field_count, record_size, len(string_block))
    path.write_bytes(header + bytes(payload) + string_block)


def _read_spell_markers(path: Path, spell_ids: list[int]) -> dict[int, int]:
    raw = path.read_bytes()
    _, record_count, _, record_size, _ = struct.unpack("<4s4I", raw[:20])
    records = raw[20 : 20 + record_count * record_size]
    found: dict[int, int] = {}
    for offset in range(0, len(records), record_size):
        spell_id, marker = struct.unpack("<II", records[offset : offset + record_size])
        if spell_id in spell_ids:
            found[spell_id] = marker
    return found


def _write_full_test_spell_dbc(path: Path, spell_ids: list[int]) -> None:
    string_block = b"\x00"
    payload = bytearray()
    for spell_id in spell_ids:
        fields = [0] * FULL_FIELD_COUNT
        fields[0] = int(spell_id)
        fields[28] = 1
        fields[41] = 0
        fields[42] = 0
        fields[204] = 0
        if spell_id == 2764:
            fields[ATTRIBUTES_FIELD] = 0x410012
            fields[EQUIPPED_ITEM_CLASS_FIELD] = 2
            fields[EQUIPPED_ITEM_SUBCLASS_MASK_FIELD] = 0x10000
            fields[DAMAGE_CLASS_FIELD] = 3
        if spell_id == 107:
            fields[EQUIPPED_ITEM_CLASS_FIELD] = 4
            fields[EQUIPPED_ITEM_SUBCLASS_MASK_FIELD] = 96
            fields[EQUIPPED_ITEM_INVENTORY_TYPE_MASK_FIELD] = 13
            fields[EFFECT_1_FIELD] = 23
            fields[EFFECT_DIE_SIDES_1_FIELD] = 6
            fields[EFFECT_BASE_POINTS_1_FIELD] = 1
            fields[EFFECT_APPLY_AURA_NAME_1_FIELD] = 42
            fields[EFFECT_MISC_VALUE_1_FIELD] = 90
        payload.extend(struct.pack("<" + "I" * FULL_FIELD_COUNT, *fields))
    header = struct.pack("<4s4I", b"WDBC", len(spell_ids), FULL_FIELD_COUNT, FULL_RECORD_SIZE, len(string_block))
    path.write_bytes(header + bytes(payload) + string_block)


def _read_full_spell_fields(path: Path, spell_id: int) -> list[int]:
    raw = path.read_bytes()
    _, record_count, field_count, record_size, _ = struct.unpack("<4s4I", raw[:20])
    records = raw[20 : 20 + record_count * record_size]
    for offset in range(0, len(records), record_size):
        fields = list(struct.unpack("<" + "I" * field_count, records[offset : offset + record_size]))
        if fields[0] == spell_id:
            return fields
    raise AssertionError(f"Spell {spell_id} not found.")


def test_materialize_named_shell_rows_clones_seed_records(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(
        source_path,
        [
            (107, 1007),
            (133, 1133),
            (770, 1770),
            (1459, 2459),
            (16827, 116827),
            (2764, 3764),
            (24755, 124755),
            (8092, 18092),
        ],
    )

    result = materialize_server_spell_dbc(source_dbc=source_path, out=out_path, include="named")

    assert result.appended_count == 26
    assert result.replaced_count == 0
    assert result.inspection.checked_ids[940000] is True
    assert result.inspection.checked_ids[940001] is True
    assert result.inspection.checked_ids[944000] is True
    assert result.inspection.checked_ids[945000] is True
    assert result.inspection.checked_ids[946099] is True
    assert result.inspection.checked_ids[946098] is True
    assert result.inspection.checked_ids[946200] is True
    assert result.inspection.checked_ids[946201] is True
    assert result.inspection.checked_ids[946202] is True
    assert result.inspection.checked_ids[946203] is True
    assert result.inspection.checked_ids[946204] is True
    assert result.inspection.checked_ids[946600] is True
    assert result.inspection.checked_ids[946601] is True
    assert result.inspection.checked_ids[946602] is True
    assert result.inspection.checked_ids[946603] is True
    assert result.inspection.checked_ids[946605] is True
    assert result.inspection.checked_ids[946606] is True
    assert result.inspection.checked_ids[946620] is True
    assert result.inspection.checked_ids[946621] is True
    assert result.inspection.checked_ids[946622] is True
    assert result.inspection.checked_ids[946800] is True
    assert result.inspection.checked_ids[946802] is True
    assert result.inspection.checked_ids[946803] is True
    assert result.inspection.checked_ids[946804] is True
    assert result.inspection.checked_ids[946805] is True
    assert result.inspection.checked_ids[946806] is True
    markers = _read_spell_markers(out_path, [940000, 940001, 944000, 945000, 946098, 946099, 946200, 946201, 946202, 946203, 946204, 946600, 946601, 946602, 946603, 946605, 946606, 946620, 946621, 946622, 946800, 946802, 946803, 946804, 946805, 946806])
    assert markers[940000] == 1133
    assert markers[940001] == 1133
    assert markers[944000] == 1007
    assert markers[945000] == 116827
    assert markers[946098] == 3764
    assert markers[946099] == 18092
    assert markers[946200] == 1770
    assert markers[946201] == 1770
    assert markers[946202] == 1770
    assert markers[946203] == 1770
    assert markers[946204] == 1770
    assert markers[946600] == 2459
    assert markers[946601] == 2459
    assert markers[946602] == 124755
    assert markers[946603] == 2459
    assert markers[946605] == 2459
    assert markers[946606] == 2459
    assert markers[946620] == 2459
    assert markers[946621] == 2459
    assert markers[946622] == 2459
    assert markers[946800] == 1007
    assert markers[946802] == 1007
    assert markers[946803] == 1007
    assert markers[946804] == 1007
    assert markers[946805] == 1007
    assert markers[946806] == 1007


def test_materialize_castable_profile_uses_client_cast_shape_seed(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(
        source_path,
        [
            (107, 1007),
            (16827, 116827),
            (49126, 149126),
        ],
    )

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[940001],
    )

    assert result.seed_profile == "castable"
    assert result.source_seed_spell_ids["wm_summon_pet"] == 49126
    markers = _read_spell_markers(out_path, [940001])
    assert markers[940001] == 149126


def test_materialize_castable_profile_applies_named_shell_presentation(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [49126])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[940001],
    )

    assert result.selected_spell_ids == [940001]
    fields = _read_full_spell_fields(out_path, 940001)
    assert fields[28] == 14
    assert fields[41] == 0
    assert fields[42] == 180
    assert fields[130] == 0
    assert fields[131] == 4054
    assert fields[133] == 221
    assert fields[204] == 0


def test_materialize_castable_profile_applies_stasis_reagent_presentation(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [1459])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946600],
    )

    assert result.selected_spell_ids == [946600]
    fields = _read_full_spell_fields(out_path, 946600)
    assert fields[28] == 6
    assert fields[42] == 0
    assert fields[REAGENT_START_FIELD] == 6265
    assert fields[REAGENT_COUNT_START_FIELD] == 1


def test_materialize_castable_profile_applies_lanathel_stance_presentation(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [1459])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946601],
    )

    assert result.selected_spell_ids == [946601]
    fields = _read_full_spell_fields(out_path, 946601)
    assert fields[28] == 1
    assert fields[42] == 0
    assert fields[133] == 4165
    assert fields[204] == 0


def test_materialize_castable_profile_applies_energy_surge_potion_aura(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [1459])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946606],
    )

    assert result.selected_spell_ids == [946606]
    fields = _read_full_spell_fields(out_path, 946606)
    assert fields[POWER_TYPE_FIELD] == 0
    assert fields[MANA_COST_FIELD] == 0
    assert fields[DISPEL_TYPE_FIELD] == 0
    assert fields[DURATION_INDEX_FIELD] == 0
    assert fields[EFFECT_1_FIELD] == 6
    assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
    assert fields[EFFECT_IMPLICIT_TARGET_A_1_FIELD] == 1
    assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 4
    assert fields[EFFECT_MISC_VALUE_1_FIELD] == 0
    assert fields[SPELL_ICON_ID_FIELD] == 1299
    assert fields[SPELL_FAMILY_NAME_FIELD] == 0
    assert fields[SPELL_FAMILY_FLAGS_1_FIELD] == 0
    assert fields[SPELL_FAMILY_FLAGS_2_FIELD] == 0
    assert fields[SPELL_FAMILY_FLAGS_3_FIELD] == 0
    assert fields[DAMAGE_CLASS_FIELD] == 0
    assert fields[PREVENTION_TYPE_FIELD] == 0


def test_materialize_castable_profile_applies_broug_cloud_step_cost_and_cooldown(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [770])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946202],
    )

    assert result.selected_spell_ids == [946202]
    assert result.source_seed_spell_ids["wm_unit_target_effect"] == 770
    fields = _read_full_spell_fields(out_path, 946202)
    assert fields[POWER_TYPE_FIELD] == 3
    assert fields[MANA_COST_FIELD] == 20
    assert fields[RECOVERY_TIME_FIELD] == 12000
    assert fields[CATEGORY_RECOVERY_TIME_FIELD] == 1000
    assert fields[START_RECOVERY_CATEGORY_FIELD] == 0
    assert fields[START_RECOVERY_TIME_FIELD] == 1000
    assert fields[DISPEL_TYPE_FIELD] == 0
    assert fields[DURATION_INDEX_FIELD] == 0
    assert fields[EFFECT_1_FIELD] == 0
    assert fields[EFFECT_DIE_SIDES_1_FIELD] == 0
    assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
    assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 0
    assert fields[EFFECT_MISC_VALUE_1_FIELD] == 0
    assert fields[SPELL_ICON_ID_FIELD] == 2363


def test_materialize_castable_profile_applies_broug_lightness_visible_auras(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [770, 1459])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946203, 946620],
    )

    assert result.selected_spell_ids == [946203, 946620]
    marked_fields = _read_full_spell_fields(out_path, 946203)
    intent_fields = _read_full_spell_fields(out_path, 946620)
    for fields in (marked_fields, intent_fields):
        assert fields[POWER_TYPE_FIELD] == 0
        assert fields[MANA_COST_FIELD] == 0
        assert fields[DISPEL_TYPE_FIELD] == 0
        assert fields[DURATION_INDEX_FIELD] == 36
        assert fields[EFFECT_1_FIELD] == 6
        assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
        assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 4
        assert fields[EFFECT_MISC_VALUE_1_FIELD] == 0
    assert marked_fields[STACK_AMOUNT_FIELD] == 1
    assert marked_fields[SPELL_ICON_ID_FIELD] == 2112
    assert intent_fields[SPELL_ICON_ID_FIELD] == 2112
    assert intent_fields[SPELL_FAMILY_NAME_FIELD] == 0
    assert intent_fields[SPELL_FAMILY_FLAGS_1_FIELD] == 0
    assert intent_fields[SPELL_FAMILY_FLAGS_2_FIELD] == 0
    assert intent_fields[SPELL_FAMILY_FLAGS_3_FIELD] == 0
    assert intent_fields[DAMAGE_CLASS_FIELD] == 0
    assert intent_fields[PREVENTION_TYPE_FIELD] == 0


def test_materialize_castable_profile_applies_qi_reversal_self_range(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [1459])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946621, 946622],
    )

    assert result.selected_spell_ids == [946621, 946622]
    fields = _read_full_spell_fields(out_path, 946621)
    assert fields[RANGE_INDEX_FIELD] == 1
    assert fields[EFFECT_1_FIELD] == 0
    assert fields[SPELL_ICON_ID_FIELD] == 1933
    purged_fields = _read_full_spell_fields(out_path, 946622)
    assert purged_fields[EFFECT_1_FIELD] == 6
    assert purged_fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 4
    assert purged_fields[SPELL_ICON_ID_FIELD] == 1933
    assert purged_fields[SPELL_FAMILY_NAME_FIELD] == 0
    assert purged_fields[SPELL_FAMILY_FLAGS_1_FIELD] == 0
    assert purged_fields[SPELL_FAMILY_FLAGS_2_FIELD] == 0
    assert purged_fields[SPELL_FAMILY_FLAGS_3_FIELD] == 0
    assert purged_fields[DAMAGE_CLASS_FIELD] == 0
    assert purged_fields[PREVENTION_TYPE_FIELD] == 0


def test_materialize_castable_profile_applies_echo_mind_blast_range(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [8092])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946099],
    )

    assert result.selected_spell_ids == [946099]
    assert result.source_seed_spell_ids["wm_mind_blast"] == 8092
    fields = _read_full_spell_fields(out_path, 946099)
    assert fields[RANGE_INDEX_FIELD] == 157


def test_materialize_castable_profile_builds_active_skirmisher_mark(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [2764])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946098],
    )

    assert result.selected_spell_ids == [946098]
    assert result.source_seed_spell_ids["wm_weapon_ranged_attack"] == 2764
    fields = _read_full_spell_fields(out_path, 946098)
    assert fields[ATTRIBUTES_FIELD] == 0x410010
    assert fields[ATTRIBUTES_FIELD] & 0x10
    assert not fields[ATTRIBUTES_FIELD] & 0x2
    assert fields[INTERRUPT_FLAGS_FIELD] == 0
    assert fields[AURA_INTERRUPT_FLAGS_FIELD] == 0
    assert fields[CHANNEL_INTERRUPT_FLAGS_FIELD] == 0
    assert fields[DAMAGE_CLASS_FIELD] == 3
    assert fields[EQUIPPED_ITEM_CLASS_FIELD] == 2
    assert fields[EQUIPPED_ITEM_SUBCLASS_MASK_FIELD] == RANGED_WEAPON_SUBCLASS_MASK
    assert fields[EFFECT_1_FIELD] == 58


def test_materialize_castable_profile_applies_broug_deflect_cost_and_cooldown(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [1459])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946603],
    )

    assert result.selected_spell_ids == [946603]
    fields = _read_full_spell_fields(out_path, 946603)
    assert fields[POWER_TYPE_FIELD] == 3
    assert fields[MANA_COST_FIELD] == 5
    assert fields[RECOVERY_TIME_FIELD] == 500
    assert fields[CATEGORY_RECOVERY_TIME_FIELD] == 0
    assert fields[START_RECOVERY_CATEGORY_FIELD] == 0
    assert fields[START_RECOVERY_TIME_FIELD] == 0
    assert fields[DISPEL_TYPE_FIELD] == 0
    assert fields[DURATION_INDEX_FIELD] == 0
    assert fields[EFFECT_1_FIELD] == 0
    assert fields[EFFECT_DIE_SIDES_1_FIELD] == 0
    assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
    assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 0
    assert fields[EFFECT_MISC_VALUE_1_FIELD] == 0
    assert fields[SPELL_ICON_ID_FIELD] == 278


def test_materialize_castable_profile_applies_broug_counterstrike_stance(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [1459])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946605],
    )

    assert result.selected_spell_ids == [946605]
    fields = _read_full_spell_fields(out_path, 946605)
    assert fields[POWER_TYPE_FIELD] == 3
    assert fields[MANA_COST_FIELD] == 0
    assert fields[RECOVERY_TIME_FIELD] == 0
    assert fields[CATEGORY_FIELD] == 47
    assert fields[CATEGORY_RECOVERY_TIME_FIELD] == 1000
    assert fields[START_RECOVERY_TIME_FIELD] == 0
    assert fields[DISPEL_TYPE_FIELD] == 0
    assert fields[DURATION_INDEX_FIELD] == 21
    assert fields[EFFECT_1_FIELD] == 6
    assert fields[EFFECT_DIE_SIDES_1_FIELD] == 1
    assert fields[EFFECT_BASE_POINTS_1_FIELD] == 4294967295
    assert fields[EFFECT_IMPLICIT_TARGET_A_1_FIELD] == 1
    assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 36
    assert fields[EFFECT_MISC_VALUE_1_FIELD] == 13
    assert fields[STANCE_BAR_ORDER_FIELD] == 1
    assert fields[SPELL_VISUAL_ID_2_FIELD] == 0
    assert fields[SPELL_ICON_ID_FIELD] == 563
    assert fields[ACTIVE_ICON_ID_FIELD] == 563
    assert fields[SPELL_PRIORITY_FIELD] == 50
    assert fields[SPELL_FAMILY_NAME_FIELD] == 8
    assert fields[SPELL_FAMILY_FLAGS_1_FIELD] == 0
    assert fields[SPELL_FAMILY_FLAGS_2_FIELD] == 0
    assert fields[SPELL_FAMILY_FLAGS_3_FIELD] == 0
    assert fields[DAMAGE_CLASS_FIELD] == 0
    assert fields[PREVENTION_TYPE_FIELD] == 0


def test_materialize_castable_profile_applies_broug_deflect_visible_state_auras(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [770])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946200, 946201],
    )

    assert result.selected_spell_ids == [946200, 946201]
    assert result.source_seed_spell_ids["wm_unit_target_effect"] == 770
    vulnerable_fields = _read_full_spell_fields(out_path, 946200)
    deflected_fields = _read_full_spell_fields(out_path, 946201)
    for fields in (vulnerable_fields, deflected_fields):
        assert fields[POWER_TYPE_FIELD] == 0
        assert fields[MANA_COST_FIELD] == 0
        assert fields[DISPEL_TYPE_FIELD] == 0
        assert fields[EFFECT_1_FIELD] == 6
        assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
        assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 4
        assert fields[EFFECT_MISC_VALUE_1_FIELD] == 0
        assert fields[STACK_AMOUNT_FIELD] == 255
        assert fields[SPELL_ICON_ID_FIELD] == 558
    assert vulnerable_fields[DURATION_INDEX_FIELD] == 3
    assert deflected_fields[DURATION_INDEX_FIELD] == 36


def test_materialize_castable_profile_clears_broug_passive_block_requirements(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [107])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946800, 946802, 946803],
    )

    assert result.selected_spell_ids == [946800, 946802, 946803]
    for spell_id in (946800, 946802, 946803):
        fields = _read_full_spell_fields(out_path, spell_id)
        assert fields[EQUIPPED_ITEM_CLASS_FIELD] == 0xFFFFFFFF
        assert fields[EQUIPPED_ITEM_SUBCLASS_MASK_FIELD] == 0
        assert fields[EQUIPPED_ITEM_INVENTORY_TYPE_MASK_FIELD] == 0
        assert fields[EFFECT_1_FIELD] == 0
        assert fields[EFFECT_DIE_SIDES_1_FIELD] == 0
        assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
        assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 0
        assert fields[EFFECT_MISC_VALUE_1_FIELD] == 0
    parry_fields = _read_full_spell_fields(out_path, 946800)
    silent_fields = _read_full_spell_fields(out_path, 946803)
    assert parry_fields[SPELL_ICON_ID_FIELD] == 26
    assert silent_fields[SPELL_ICON_ID_FIELD] == 167


def test_materialize_all_shell_rows_adds_generic_family_entries(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(
        source_path,
        [
            (107, 1007),
            (120, 1120),
            (133, 1133),
            (770, 1770),
            (1449, 2449),
                (1459, 2459),
                (2061, 3061),
                (2764, 3764),
                (5740, 6740),
            (16827, 116827),
            (24755, 124755),
            (8092, 18092),
            (27243, 37243),
            (48505, 58505),
        ],
    )

    result = materialize_server_spell_dbc(source_dbc=source_path, out=out_path, include="all")

    assert result.appended_count == 1004
    assert result.replaced_count == 0
    assert result.inspection.checked_ids[946000] is True
    assert result.inspection.checked_ids[946100] is True
    assert result.inspection.checked_ids[946200] is True
    assert result.inspection.checked_ids[946300] is True
    assert result.inspection.checked_ids[946400] is True
    assert result.inspection.checked_ids[946500] is True
    assert result.inspection.checked_ids[946600] is True
    assert result.inspection.checked_ids[946700] is True
    assert result.inspection.checked_ids[946800] is True
    assert result.inspection.checked_ids[946900] is True
    markers = _read_spell_markers(
        out_path,
        [946000, 946100, 946200, 946300, 946400, 946500, 946600, 946700, 946800, 946900],
    )
    assert markers[946000] == 1133
    assert markers[946100] == 3061
    assert markers[946200] == 1770
    assert markers[946300] == 37243
    assert markers[946400] == 6740
    assert markers[946500] == 2449
    assert markers[946600] == 2459
    assert markers[946700] == 58505
    assert markers[946800] == 1007
    assert markers[946900] == 1120

    watcher_markers = _read_spell_markers(out_path, [946602])
    assert watcher_markers[946602] == 124755


def test_materialize_castable_profile_applies_undispellable_no_timer_watcher_marker(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [24755])

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        seed_profile="castable",
        spell_ids=[946602],
    )

    assert result.selected_spell_ids == [946602]
    fields = _read_full_spell_fields(out_path, 946602)
    assert fields[DISPEL_TYPE_FIELD] == 0
    assert fields[DURATION_INDEX_FIELD] == 0
    assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
    assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 4


def test_materialize_replaces_existing_shell_rows_with_current_seed_record(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(
        source_path,
        [
            (107, 1007),
            (133, 1133),
            (16827, 116827),
            (940001, 5555),
        ],
    )

    result = materialize_server_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[940001],
    )

    assert result.appended_count == 0
    assert result.replaced_count == 1
    markers = _read_spell_markers(out_path, [940001])
    assert markers[940001] == 1133


def test_inspect_spell_dbc_reports_missing_and_present_ids(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    _write_test_spell_dbc(source_path, [(107, 1007), (697, 1697)])

    inspection = inspect_spell_dbc(source_path, spell_ids=[107, 940001])

    assert inspection.record_count == 2
    assert inspection.min_id == 107
    assert inspection.max_id == 697
    assert inspection.checked_ids == {107: True, 940001: False}


def test_select_shell_patch_rows_rejects_unknown_requested_spell_id() -> None:
    try:
        select_shell_patch_rows(include="named", spell_ids=[999999])
    except ValueError as exc:
        assert "not part of the selected shell-bank rows" in str(exc)
    else:
        raise AssertionError("Expected select_shell_patch_rows to reject unknown shell spell ids.")
