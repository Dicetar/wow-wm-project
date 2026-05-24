from __future__ import annotations

import struct
from pathlib import Path

from wm.spells.client_patch_pending import load_pending
from wm.spells.unified_dbc_publish import publish_spell_dbc


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


def _common_paths(tmp_path: Path) -> dict[str, Path]:
    source = tmp_path / "source.dbc"
    _write_full_test_spell_dbc(source, [49126, 1459])
    return {
        "source_dbc": source,
        "server_out": tmp_path / "server" / "Spell.dbc",
        "client_out": tmp_path / "client" / "Spell.dbc",
        "target_server_dbc": tmp_path / "datadir" / "Spell.dbc",
        "backup_dir": tmp_path / "backups",
        "pending_path": tmp_path / "client_patch_pending.json",
    }


def test_dry_run_verifies_client_server_agree_without_staging(tmp_path: Path) -> None:
    paths = _common_paths(tmp_path)

    result = publish_spell_dbc(spell_ids=[940001], apply=False, **paths)

    assert result.verified is True
    assert result.staged is False
    assert result.selected_spell_ids == [940001]
    assert not paths["target_server_dbc"].exists()
    assert not paths["pending_path"].exists()


def test_apply_stages_server_dbc_and_queues_client_patch(tmp_path: Path) -> None:
    paths = _common_paths(tmp_path)

    result = publish_spell_dbc(spell_ids=[940001], apply=True, **paths)

    assert result.verified is True
    assert result.staged is True
    # Staged server DBC matches the materialized server payload.
    assert paths["target_server_dbc"].read_bytes() == paths["server_out"].read_bytes()
    # Client patch was queued for the close-watcher to rebuild.
    pending = load_pending(path=paths["pending_path"])
    assert 940001 in [int(e["spell_id"]) for e in pending["entries"]]


def test_apply_backs_up_existing_target_before_overwriting(tmp_path: Path) -> None:
    paths = _common_paths(tmp_path)
    paths["target_server_dbc"].parent.mkdir(parents=True, exist_ok=True)
    paths["target_server_dbc"].write_bytes(b"OLD-DBC-CONTENT")

    result = publish_spell_dbc(spell_ids=[940001], apply=True, **paths)

    assert result.staged is True
    assert result.backup_path is not None
    assert Path(result.backup_path).read_bytes() == b"OLD-DBC-CONTENT"


def test_broken_shell_refuses_to_stage_even_with_apply(tmp_path: Path) -> None:
    # 946606 energy_surge is a visible dummy-aura buff with duration_index 0 -> audit BROKEN.
    paths = _common_paths(tmp_path)

    result = publish_spell_dbc(spell_ids=[946606], apply=True, **paths)

    assert result.verified is False
    assert result.staged is False
    assert not paths["target_server_dbc"].exists()
