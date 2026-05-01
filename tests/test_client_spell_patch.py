from __future__ import annotations

import struct
from pathlib import Path

from wm.spells.client_patch import CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS
from wm.spells.client_patch import ACTIVE_ICON_ID_FIELD
from wm.spells.client_patch import CASTING_TIME_INDEX_FIELD
from wm.spells.client_patch import CATEGORY_FIELD
from wm.spells.client_patch import CATEGORY_RECOVERY_TIME_FIELD
from wm.spells.client_patch import DISPEL_TYPE_FIELD
from wm.spells.client_patch import DURATION_INDEX_FIELD
from wm.spells.client_patch import EQUIPPED_ITEM_CLASS_FIELD
from wm.spells.client_patch import EQUIPPED_ITEM_INVENTORY_TYPE_MASK_FIELD
from wm.spells.client_patch import EQUIPPED_ITEM_SUBCLASS_MASK_FIELD
from wm.spells.client_patch import EFFECT_1_FIELD
from wm.spells.client_patch import EFFECT_APPLY_AURA_NAME_1_FIELD
from wm.spells.client_patch import EFFECT_BASE_POINTS_1_FIELD
from wm.spells.client_patch import EFFECT_DIE_SIDES_1_FIELD
from wm.spells.client_patch import EFFECT_IMPLICIT_TARGET_A_1_FIELD
from wm.spells.client_patch import EFFECT_MISC_VALUE_1_FIELD
from wm.spells.client_patch import MANA_COST_FIELD
from wm.spells.client_patch import MANA_COST_PERCENTAGE_FIELD
from wm.spells.client_patch import POWER_TYPE_FIELD
from wm.spells.client_patch import RECOVERY_TIME_FIELD
from wm.spells.client_patch import REAGENT_COUNT_START_FIELD
from wm.spells.client_patch import REAGENT_START_FIELD
from wm.spells.client_patch import RANGE_INDEX_FIELD
from wm.spells.client_patch import SPELL_DESCRIPTION_START_FIELD
from wm.spells.client_patch import SPELL_ICON_ID_FIELD
from wm.spells.client_patch import SPELL_FAMILY_FLAGS_1_FIELD
from wm.spells.client_patch import SPELL_FAMILY_FLAGS_2_FIELD
from wm.spells.client_patch import SPELL_FAMILY_FLAGS_3_FIELD
from wm.spells.client_patch import SPELL_FAMILY_NAME_FIELD
from wm.spells.client_patch import SPELL_NAME_START_FIELD
from wm.spells.client_patch import SPELL_PRIORITY_FIELD
from wm.spells.client_patch import SPELL_TOOLTIP_START_FIELD
from wm.spells.client_patch import SPELL_VISUAL_ID_1_FIELD
from wm.spells.client_patch import SPELL_VISUAL_ID_2_FIELD
from wm.spells.client_patch import STACK_AMOUNT_FIELD
from wm.spells.client_patch import STANCE_BAR_ORDER_FIELD
from wm.spells.client_patch import START_RECOVERY_CATEGORY_FIELD
from wm.spells.client_patch import START_RECOVERY_TIME_FIELD
from wm.spells.client_patch import materialize_client_skill_race_class_info_dbc
from wm.spells.client_patch import materialize_client_spell_dbc
from wm.spells.client_patch import materialize_client_skill_line_ability_dbc


ATTRIBUTES_FIELD = 4
AURA_INTERRUPT_FLAGS_FIELD = 32
CHANNEL_INTERRUPT_FLAGS_FIELD = 33
DAMAGE_CLASS_FIELD = 213
FIELD_COUNT = 234
INTERRUPT_FLAGS_FIELD = 31
PREVENTION_TYPE_FIELD = 214
RECORD_SIZE = FIELD_COUNT * 4
RANGED_WEAPON_SUBCLASS_MASK = 0x0005000C


def _write_test_spell_dbc(path: Path, spell_ids: list[int]) -> None:
    string_block = b"\x00"
    records = bytearray()
    for spell_id in spell_ids:
        fields = [0] * FIELD_COUNT
        fields[0] = int(spell_id)
        fields[38] = 80
        fields[39] = 80
        fields[42] = 99
        fields[133] = 1
        fields[52] = 6265
        fields[60] = 1
        fields[71] = int(spell_id) % 100
        fields[86] = 32
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
        records.extend(struct.pack("<" + "I" * FIELD_COUNT, *fields))
    header = struct.pack("<4s4I", b"WDBC", len(spell_ids), FIELD_COUNT, RECORD_SIZE, len(string_block))
    path.write_bytes(header + bytes(records) + string_block)


def _write_test_spell_icon_dbc(path: Path) -> None:
    icon_path = b"Interface\\Icons\\Spell_Shadow_AnimateDead\x00"
    string_block = b"\x00" + icon_path
    records = struct.pack("<II", 221, 1)
    header = struct.pack("<4s4I", b"WDBC", 1, 2, 8, len(string_block))
    path.write_bytes(header + records + string_block)


def _write_test_skill_line_ability_dbc(path: Path) -> None:
    fields = [0] * 14
    fields[0] = 6394
    fields[1] = 354
    fields[2] = 697
    fields[4] = 256
    fields[7] = 1
    records = struct.pack("<" + "I" * 14, *fields)
    header = struct.pack("<4s4I", b"WDBC", 1, 14, 56, 1)
    path.write_bytes(header + records + b"\x00")


def _write_test_skill_race_class_info_dbc(path: Path) -> None:
    rows = [
        [125, 55, 262143, 4, 128, 0, 0, 0],
        [122, 172, 163839, 2, 128, 0, 0, 0],
        [136, 229, 32767, 1031, 128, 20, 0, 0],
    ]
    records = b"".join(struct.pack("<" + "I" * 8, *row) for row in rows)
    header = struct.pack("<4s4I", b"WDBC", len(rows), 8, 32, 1)
    path.write_bytes(header + records + b"\x00")


def _record_fields(path: Path, spell_id: int) -> tuple[list[int], bytes]:
    raw = path.read_bytes()
    _, record_count, field_count, record_size, string_block_size = struct.unpack("<4s4I", raw[:20])
    records = raw[20 : 20 + record_count * record_size]
    string_block = raw[20 + record_count * record_size : 20 + record_count * record_size + string_block_size]
    for offset in range(0, len(records), record_size):
        fields = list(struct.unpack("<" + "I" * field_count, records[offset : offset + record_size]))
        if fields[0] == spell_id:
            return fields, string_block
    raise AssertionError(f"Spell {spell_id} not found.")


def _string_at(string_block: bytes, offset: int) -> str:
    end = string_block.index(b"\x00", offset)
    return string_block[offset:end].decode("utf-8")


def test_materialize_client_spell_dbc_uses_client_seed_and_named_text(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    icon_path = tmp_path / "SpellIcon.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))
    _write_test_spell_icon_dbc(icon_path)

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[940001],
        source_spell_icon_dbc=icon_path,
    )

    assert result.appended_count == 1
    assert result.replaced_count == 0
    assert result.selected_spell_ids == [940001]
    assert result.presentation_applied_spell_ids == [940001]
    fields, string_block = _record_fields(out_path, 940001)
    assert fields[71] == 49126 % 100
    assert fields[38] == 1
    assert fields[39] == 1
    assert fields[CASTING_TIME_INDEX_FIELD] == 14
    assert fields[POWER_TYPE_FIELD] == 0
    assert fields[MANA_COST_FIELD] == 180
    assert fields[MANA_COST_PERCENTAGE_FIELD] == 0
    assert fields[130] == 0
    assert fields[131] == 4054
    assert fields[SPELL_ICON_ID_FIELD] == 221
    assert fields[52] == 0
    assert fields[60] == 0
    assert _string_at(string_block, fields[SPELL_NAME_START_FIELD]) == "Bonebound Alpha"
    assert "WM-controlled bleed" in _string_at(string_block, fields[SPELL_DESCRIPTION_START_FIELD])
    assert "WM-controlled bleed" in _string_at(string_block, fields[SPELL_TOOLTIP_START_FIELD])


def test_materialize_client_spell_dbc_applies_stasis_reagent_presentation(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946600],
    )

    assert result.appended_count == 1
    assert result.selected_spell_ids == [946600]
    assert result.presentation_applied_spell_ids == [946600]
    fields, string_block = _record_fields(out_path, 946600)
    assert fields[CASTING_TIME_INDEX_FIELD] == 6
    assert fields[MANA_COST_FIELD] == 0
    assert fields[REAGENT_START_FIELD] == 6265
    assert fields[REAGENT_COUNT_START_FIELD] == 1
    assert _string_at(string_block, fields[SPELL_NAME_START_FIELD]) == "Bonebound Echo Stasis"
    assert "restore the stored echo counts" in _string_at(string_block, fields[SPELL_DESCRIPTION_START_FIELD])


def test_materialize_client_spell_dbc_applies_lanathel_stance_presentation(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946601],
    )

    assert result.appended_count == 1
    assert result.selected_spell_ids == [946601]
    assert result.presentation_applied_spell_ids == [946601]
    fields, string_block = _record_fields(out_path, 946601)
    assert fields[CASTING_TIME_INDEX_FIELD] == 1
    assert fields[MANA_COST_FIELD] == 0
    assert fields[SPELL_ICON_ID_FIELD] == 4165
    assert _string_at(string_block, fields[SPELL_NAME_START_FIELD]) == "Blood Queen's Pursuit"
    assert "Lana'thel battle stance" in _string_at(string_block, fields[SPELL_DESCRIPTION_START_FIELD])


def test_materialize_client_spell_dbc_applies_watcher_beacon_marker_text(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946602],
    )

    assert result.appended_count == 1
    assert result.selected_spell_ids == [946602]
    assert result.presentation_applied_spell_ids == [946602]
    fields, string_block = _record_fields(out_path, 946602)
    assert fields[EFFECT_1_FIELD] == 6
    assert fields[CASTING_TIME_INDEX_FIELD] == 1
    assert fields[DISPEL_TYPE_FIELD] == 0
    assert fields[DURATION_INDEX_FIELD] == 0
    assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
    assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 4
    assert fields[MANA_COST_FIELD] == 0
    assert fields[SPELL_ICON_ID_FIELD] == 135
    assert _string_at(string_block, fields[SPELL_NAME_START_FIELD]) == "WM Watcher Beacon"
    assert "fixed its attention" in _string_at(string_block, fields[SPELL_DESCRIPTION_START_FIELD])


def test_materialize_client_spell_dbc_applies_energy_surge_potion_aura(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946606],
    )

    assert result.appended_count == 1
    assert result.selected_spell_ids == [946606]
    assert result.presentation_applied_spell_ids == [946606]
    fields, string_block = _record_fields(out_path, 946606)
    assert fields[CASTING_TIME_INDEX_FIELD] == 1
    assert fields[POWER_TYPE_FIELD] == 0
    assert fields[MANA_COST_FIELD] == 0
    assert fields[MANA_COST_PERCENTAGE_FIELD] == 0
    assert fields[DISPEL_TYPE_FIELD] == 0
    assert fields[DURATION_INDEX_FIELD] == 0
    assert fields[EFFECT_1_FIELD] == 6
    assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
    assert fields[EFFECT_IMPLICIT_TARGET_A_1_FIELD] == 1
    assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 4
    assert fields[EFFECT_MISC_VALUE_1_FIELD] == 0
    assert fields[SPELL_VISUAL_ID_1_FIELD] == 0
    assert fields[SPELL_VISUAL_ID_2_FIELD] == 0
    assert fields[SPELL_ICON_ID_FIELD] == 1299
    assert _string_at(string_block, fields[SPELL_NAME_START_FIELD]) == "Energy Surge"
    assert "10 additional energy" in _string_at(string_block, fields[SPELL_DESCRIPTION_START_FIELD])


def test_materialize_client_spell_dbc_applies_echo_mind_blast_range(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946099],
    )

    assert result.appended_count == 1
    assert result.selected_spell_ids == [946099]
    fields, string_block = _record_fields(out_path, 946099)
    assert fields[71] == 8092 % 100
    assert fields[RANGE_INDEX_FIELD] == 157
    assert _string_at(string_block, fields[SPELL_NAME_START_FIELD]) == "Echo Mind Blast"
    assert "three times the stock cast range" in _string_at(string_block, fields[SPELL_DESCRIPTION_START_FIELD])


def test_materialize_client_spell_dbc_applies_broug_deflect_cost_cooldown_and_text(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946603],
    )

    assert result.appended_count == 1
    assert result.selected_spell_ids == [946603]
    fields, string_block = _record_fields(out_path, 946603)
    assert fields[CASTING_TIME_INDEX_FIELD] == 1
    assert fields[POWER_TYPE_FIELD] == 3
    assert fields[MANA_COST_FIELD] == 5
    assert fields[MANA_COST_PERCENTAGE_FIELD] == 0
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
    assert _string_at(string_block, fields[SPELL_NAME_START_FIELD]) == "Deflect"
    assert "split-second guard" in _string_at(string_block, fields[SPELL_DESCRIPTION_START_FIELD])


def test_materialize_client_spell_dbc_applies_broug_counterstrike_stance(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946605],
    )

    assert result.appended_count == 1
    assert result.selected_spell_ids == [946605]
    fields, string_block = _record_fields(out_path, 946605)
    assert fields[CASTING_TIME_INDEX_FIELD] == 1
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
    assert fields[SPELL_ICON_ID_FIELD] == 132
    assert fields[ACTIVE_ICON_ID_FIELD] == 132
    assert fields[SPELL_PRIORITY_FIELD] == 50
    assert fields[SPELL_FAMILY_NAME_FIELD] == 8
    assert fields[SPELL_FAMILY_FLAGS_1_FIELD] == 0
    assert fields[SPELL_FAMILY_FLAGS_2_FIELD] == 0
    assert fields[SPELL_FAMILY_FLAGS_3_FIELD] == 0
    assert fields[DAMAGE_CLASS_FIELD] == 0
    assert fields[PREVENTION_TYPE_FIELD] == 0
    assert _string_at(string_block, fields[SPELL_NAME_START_FIELD]) == "Counterstrike Stance"
    assert "Counterstrike Stance" in _string_at(string_block, fields[SPELL_DESCRIPTION_START_FIELD])


def test_materialize_client_spell_dbc_applies_broug_deflect_visible_state_auras(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946200, 946201],
    )

    assert result.appended_count == 2
    assert result.selected_spell_ids == [946200, 946201]
    vulnerable_fields, vulnerable_string_block = _record_fields(out_path, 946200)
    deflected_fields, deflected_string_block = _record_fields(out_path, 946201)
    for fields in (vulnerable_fields, deflected_fields):
        assert fields[CASTING_TIME_INDEX_FIELD] == 1
        assert fields[POWER_TYPE_FIELD] == 0
        assert fields[MANA_COST_FIELD] == 0
        assert fields[MANA_COST_PERCENTAGE_FIELD] == 0
        assert fields[DISPEL_TYPE_FIELD] == 0
        assert fields[EFFECT_1_FIELD] == 6
        assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
        assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 4
        assert fields[EFFECT_MISC_VALUE_1_FIELD] == 0
        assert fields[SPELL_VISUAL_ID_1_FIELD] == 0
        assert fields[SPELL_VISUAL_ID_2_FIELD] == 0
        assert fields[STACK_AMOUNT_FIELD] == 255
        assert fields[SPELL_ICON_ID_FIELD] == 558
    assert vulnerable_fields[DURATION_INDEX_FIELD] == 3
    assert deflected_fields[DURATION_INDEX_FIELD] == 36
    assert _string_at(vulnerable_string_block, vulnerable_fields[SPELL_NAME_START_FIELD]) == "Vulnerable"
    assert _string_at(deflected_string_block, deflected_fields[SPELL_NAME_START_FIELD]) == "Deflected"


def test_materialize_client_spell_dbc_clears_broug_passive_block_requirements(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946800, 946802],
    )

    assert result.appended_count == 2
    assert result.selected_spell_ids == [946800, 946802]
    parry_fields, parry_string_block = _record_fields(out_path, 946800)
    retaliation_fields, _ = _record_fields(out_path, 946802)
    for fields in (parry_fields, retaliation_fields):
        assert fields[EQUIPPED_ITEM_CLASS_FIELD] == 0xFFFFFFFF
        assert fields[EQUIPPED_ITEM_SUBCLASS_MASK_FIELD] == 0
        assert fields[EQUIPPED_ITEM_INVENTORY_TYPE_MASK_FIELD] == 0
        assert fields[EFFECT_1_FIELD] == 0
        assert fields[EFFECT_DIE_SIDES_1_FIELD] == 0
        assert fields[EFFECT_BASE_POINTS_1_FIELD] == 0
        assert fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 0
        assert fields[EFFECT_MISC_VALUE_1_FIELD] == 0
    assert parry_fields[SPELL_ICON_ID_FIELD] == 26
    parry_tooltip = _string_at(parry_string_block, parry_fields[SPELL_TOOLTIP_START_FIELD])
    assert "Strength" in parry_tooltip
    assert "Expertise" in parry_tooltip
    assert "weapon mastery" in parry_tooltip


def test_materialize_client_spell_dbc_builds_active_skirmisher_mark(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, list(CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values()))

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946098],
    )

    assert result.appended_count == 1
    assert result.selected_spell_ids == [946098]
    marksman_fields, marksman_string_block = _record_fields(out_path, 946098)
    assert marksman_fields[CASTING_TIME_INDEX_FIELD] == 1
    assert marksman_fields[MANA_COST_FIELD] == 0
    assert marksman_fields[RECOVERY_TIME_FIELD] == 0
    assert marksman_fields[CATEGORY_RECOVERY_TIME_FIELD] == 0
    assert marksman_fields[START_RECOVERY_TIME_FIELD] == 0
    assert marksman_fields[EFFECT_1_FIELD] == 58
    assert marksman_fields[EFFECT_APPLY_AURA_NAME_1_FIELD] == 0
    assert marksman_fields[ATTRIBUTES_FIELD] == 0x410010
    assert marksman_fields[ATTRIBUTES_FIELD] & 0x10
    assert not marksman_fields[ATTRIBUTES_FIELD] & 0x2
    assert marksman_fields[INTERRUPT_FLAGS_FIELD] == 0
    assert marksman_fields[AURA_INTERRUPT_FLAGS_FIELD] == 0
    assert marksman_fields[CHANNEL_INTERRUPT_FLAGS_FIELD] == 0
    assert marksman_fields[DAMAGE_CLASS_FIELD] == 3
    assert marksman_fields[EQUIPPED_ITEM_CLASS_FIELD] == 2
    assert marksman_fields[EQUIPPED_ITEM_SUBCLASS_MASK_FIELD] == RANGED_WEAPON_SUBCLASS_MASK
    assert marksman_fields[SPELL_VISUAL_ID_1_FIELD] == 0
    assert marksman_fields[SPELL_VISUAL_ID_2_FIELD] == 0
    assert _string_at(marksman_string_block, marksman_fields[SPELL_NAME_START_FIELD]) == "Skirmisher's Mark"
    tooltip = _string_at(marksman_string_block, marksman_fields[SPELL_TOOLTIP_START_FIELD])
    assert "ranged or thrown attack" in tooltip
    assert "while moving" in tooltip


def test_materialize_client_spell_dbc_replaces_existing_shell_row(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(source_path, [*CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS.values(), 940001])

    result = materialize_client_spell_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[940001],
    )

    assert result.appended_count == 0
    assert result.replaced_count == 1
    assert result.inspection["checked_ids"][940001] is True


def test_materialize_client_skill_line_ability_adds_spellbook_mapping(tmp_path: Path) -> None:
    source_path = tmp_path / "SkillLineAbility.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_skill_line_ability_dbc(source_path)

    result = materialize_client_skill_line_ability_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[940001],
    )

    assert result.selected_spell_ids == [940001]
    assert result.appended_count == 1
    assert result.combat_proficiency_appended_count == 5
    raw = out_path.read_bytes()
    _, record_count, field_count, record_size, _ = struct.unpack("<4s4I", raw[:20])
    assert record_count == 7
    records = raw[20 : 20 + record_count * record_size]
    rows = [
        list(struct.unpack("<" + "I" * field_count, records[offset : offset + record_size]))
        for offset in range(0, len(records), record_size)
    ]
    row = next(entry for entry in rows if entry[2] == 940001)
    assert row[0] == 1940001
    assert row[1] == 354
    assert row[4] == 256
    assert row[7] == 1
    two_handed_sword_row = next(entry for entry in rows if entry[0] == 100055)
    assert two_handed_sword_row[1] == 55
    assert two_handed_sword_row[2] == 202
    assert two_handed_sword_row[4] == 8
    assert two_handed_sword_row[7] == 1
    assert two_handed_sword_row[9] == 2


def test_materialize_client_skill_line_ability_adds_lanathel_spellbook_mapping(tmp_path: Path) -> None:
    source_path = tmp_path / "SkillLineAbility.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_skill_line_ability_dbc(source_path)

    result = materialize_client_skill_line_ability_dbc(
        source_dbc=source_path,
        out=out_path,
        include="named",
        spell_ids=[946601],
    )

    assert result.selected_spell_ids == [946601]
    assert result.appended_count == 1
    assert result.combat_proficiency_appended_count == 5
    raw = out_path.read_bytes()
    _, record_count, field_count, record_size, _ = struct.unpack("<4s4I", raw[:20])
    assert record_count == 7
    records = raw[20 : 20 + record_count * record_size]
    rows = [
        list(struct.unpack("<" + "I" * field_count, records[offset : offset + record_size]))
        for offset in range(0, len(records), record_size)
    ]
    row = next(entry for entry in rows if entry[2] == 946601)
    assert row[0] == 1946601
    assert row[1] == 354
    assert row[4] == 256
    assert row[7] == 1
    polearm_row = next(entry for entry in rows if entry[0] == 100229)
    assert polearm_row[1] == 229
    assert polearm_row[2] == 200
    assert polearm_row[4] == 8
    assert polearm_row[7] == 1
    assert polearm_row[9] == 2


def test_materialize_client_skill_race_class_info_adds_rogue_combat_proficiency_rows(tmp_path: Path) -> None:
    source_path = tmp_path / "SkillRaceClassInfo.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_skill_race_class_info_dbc(source_path)

    result = materialize_client_skill_race_class_info_dbc(source_dbc=source_path, out=out_path)

    assert result.appended_count == 5
    raw = out_path.read_bytes()
    _, record_count, field_count, record_size, _ = struct.unpack("<4s4I", raw[:20])
    assert record_count == 8
    records = raw[20 : 20 + record_count * record_size]
    rows = [
        list(struct.unpack("<" + "I" * field_count, records[offset : offset + record_size]))
        for offset in range(0, len(records), record_size)
    ]
    two_handed_sword_row = next(entry for entry in rows if entry[0] == 100055)
    assert two_handed_sword_row == [100055, 55, 2047, 8, 128, 0, 0, 0]
    plate_row = next(entry for entry in rows if entry[0] == 100293)
    assert plate_row == [100293, 293, 2047, 8, 128, 40, 0, 0]
