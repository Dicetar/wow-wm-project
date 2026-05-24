from __future__ import annotations

import struct
from pathlib import Path

from wm.spells.server_dbc import SPELL_NAME_START_FIELD
from wm.spells.server_dbc import load_spell_dbc
from wm.spells.server_dbc import materialize_server_spell_dbc
from wm.spells.server_dbc import record_spell_id
from wm.spells.server_dbc import write_spell_dbc
from wm.spells.shell_audit import audit_spell_shells


FULL_FIELD_COUNT = 234
FULL_RECORD_SIZE = FULL_FIELD_COUNT * 4


def _write_full_test_spell_dbc(path: Path, spell_ids: list[int]) -> None:
    string_block = b"\x00"
    payload = bytearray()
    for spell_id in spell_ids:
        fields = [0] * FULL_FIELD_COUNT
        fields[0] = int(spell_id)
        fields[28] = 1
        payload.extend(struct.pack("<" + "I" * FULL_FIELD_COUNT, *fields))
    header = struct.pack("<4s4I", b"WDBC", len(spell_ids), FULL_FIELD_COUNT, FULL_RECORD_SIZE, len(string_block))
    path.write_bytes(header + bytes(payload) + string_block)


def test_audit_flags_visible_buff_with_zero_duration() -> None:
    # 946606 energy_surge_potion_v1 is a dummy aura (effect_1=6, aura=4) with duration_index 0:
    # a visible buff that ships invisible. This must be an error, not a warning.
    report = audit_spell_shells(spell_ids=[946606])

    assert report.status == "BROKEN"
    codes = [issue.code for issue in report.spell_results[0].issues]
    assert "visible_buff_zero_duration" in codes


def test_audit_passes_infinite_duration_marker_aura() -> None:
    # 946602 watcher beacon is a dummy aura with the infinite duration index (21); it must not trip
    # the zero-duration rule.
    report = audit_spell_shells(spell_ids=[946602])

    codes = [issue.code for issue in report.spell_results[0].issues]
    assert "visible_buff_zero_duration" not in codes


def test_audit_passes_authored_server_dbc_name(tmp_path: Path) -> None:
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [49126])
    materialize_server_spell_dbc(
        source_dbc=source_path, out=out_path, include="named", seed_profile="castable", spell_ids=[940001]
    )

    report = audit_spell_shells(spell_ids=[940001], server_dbc=out_path)

    codes = [issue.code for issue in report.spell_results[0].issues]
    assert "server_dbc_name_mismatch" not in codes


def test_audit_flags_server_dbc_name_leaked_from_seed(tmp_path: Path) -> None:
    # A materialized server row whose name does not match the shell-bank label (e.g. the seed's
    # original name leaked through) must be an error.
    source_path = tmp_path / "source.dbc"
    out_path = tmp_path / "out.dbc"
    _write_full_test_spell_dbc(source_path, [49126])
    materialize_server_spell_dbc(
        source_dbc=source_path, out=out_path, include="named", seed_profile="castable", spell_ids=[940001]
    )

    # Corrupt the authored name back to offset 0 (empty / leaked seed name).
    dbc = load_spell_dbc(out_path)
    records = [bytearray(r) for r in dbc.records]
    for record in records:
        if record_spell_id(record) == 940001:
            struct.pack_into("<I", record, SPELL_NAME_START_FIELD * 4, 0)
    dbc.records = [bytes(r) for r in records]
    write_spell_dbc(out_path, dbc)

    report = audit_spell_shells(spell_ids=[940001], server_dbc=out_path)

    assert report.status == "BROKEN"
    codes = [issue.code for issue in report.spell_results[0].issues]
    assert "server_dbc_name_mismatch" in codes
