from __future__ import annotations

import struct
from pathlib import Path

from wm.spells.client_patch import CLIENT_SEED_TEMPLATE_SOURCE_SPELL_IDS
from wm.spells.client_patch import CASTING_TIME_INDEX_FIELD
from wm.spells.client_patch import MANA_COST_FIELD
from wm.spells.client_patch import MANA_COST_PERCENTAGE_FIELD
from wm.spells.client_patch import POWER_TYPE_FIELD
from wm.spells.client_patch import REAGENT_COUNT_START_FIELD
from wm.spells.client_patch import REAGENT_START_FIELD
from wm.spells.client_patch import SPELL_DESCRIPTION_START_FIELD
from wm.spells.client_patch import SPELL_ICON_ID_FIELD
from wm.spells.client_patch import SPELL_NAME_START_FIELD
from wm.spells.client_patch import SPELL_TOOLTIP_START_FIELD
from wm.spells.client_patch import materialize_client_spell_dbc
from wm.spells.client_patch import materialize_client_skill_line_ability_dbc


FIELD_COUNT = 234
RECORD_SIZE = FIELD_COUNT * 4


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
    raw = out_path.read_bytes()
    _, record_count, field_count, record_size, _ = struct.unpack("<4s4I", raw[:20])
    assert record_count == 2
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
