from __future__ import annotations

import struct
from pathlib import Path

from wm.spells.server_dbc import inspect_spell_dbc
from wm.spells.server_dbc import materialize_server_spell_dbc
from wm.spells.server_dbc import REAGENT_COUNT_START_FIELD
from wm.spells.server_dbc import REAGENT_START_FIELD
from wm.spells.server_dbc import select_shell_patch_rows


FULL_FIELD_COUNT = 234
FULL_RECORD_SIZE = FULL_FIELD_COUNT * 4


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
            (1459, 2459),
            (16827, 116827),
        ],
    )

    result = materialize_server_spell_dbc(source_dbc=source_path, out=out_path, include="named")

    assert result.appended_count == 5
    assert result.replaced_count == 0
    assert result.inspection.checked_ids[940000] is True
    assert result.inspection.checked_ids[940001] is True
    assert result.inspection.checked_ids[944000] is True
    assert result.inspection.checked_ids[945000] is True
    assert result.inspection.checked_ids[946600] is True
    markers = _read_spell_markers(out_path, [940000, 940001, 944000, 945000, 946600])
    assert markers[940000] == 1133
    assert markers[940001] == 1133
    assert markers[944000] == 1007
    assert markers[945000] == 116827
    assert markers[946600] == 2459


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


def test_materialize_all_shell_rows_adds_generic_family_entries(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_test_spell_dbc(
        source_path,
        [
            (107, 1007),
            (133, 1133),
            (770, 1770),
            (1459, 2459),
            (5740, 6740),
            (16827, 116827),
        ],
    )

    result = materialize_server_spell_dbc(source_dbc=source_path, out=out_path, include="all")

    assert result.appended_count == 504
    assert result.replaced_count == 0
    assert result.inspection.checked_ids[946000] is True
    assert result.inspection.checked_ids[946200] is True
    assert result.inspection.checked_ids[946400] is True
    assert result.inspection.checked_ids[946600] is True
    assert result.inspection.checked_ids[946800] is True
    markers = _read_spell_markers(out_path, [946000, 946200, 946400, 946600, 946800])
    assert markers[946000] == 1133
    assert markers[946200] == 1770
    assert markers[946400] == 6740
    assert markers[946600] == 2459
    assert markers[946800] == 1007


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
