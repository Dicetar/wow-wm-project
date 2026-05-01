from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient


BROUG_UNIVERSAL_PARRY_SHELL_ID = 946800
BROUG_RETIRED_MOBILE_MARKSMAN_SHELL_ID = 946801
BROUG_RETIRED_SKIRMISHER_TOGGLE_SHELL_ID = 946604
BROUG_SKIRMISHER_MARK_SHELL_ID = 946098
BROUG_VULNERABLE_SHELL_ID = 946200
BROUG_DEFLECTED_SHELL_ID = 946201
BROUG_DEFLECT_SHELL_ID = 946603
BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID = 946605
BROUG_AUTO_RETALIATION_SHELL_ID = 946802
BROUG_GUARD_SHELL_IDS = (BROUG_UNIVERSAL_PARRY_SHELL_ID, BROUG_SKIRMISHER_MARK_SHELL_ID)
BROUG_GUARD_REWARD_SHELL_IDS = (
    BROUG_DEFLECT_SHELL_ID,
    BROUG_DEFLECT_COUNTER_STANCE_SHELL_ID,
    BROUG_AUTO_RETALIATION_SHELL_ID,
)
BROUG_GUARD_SPEC_MASK = 255
GRANT_KIND = "broug_guard"
GRANT_AUTHOR = "wm.spells.broug_guard"


@dataclass(slots=True)
class BrougGuardGrantResult:
    mode: str
    ok: bool
    applied: bool
    player_guid: int
    shell_spell_ids: tuple[int, ...] = BROUG_GUARD_SHELL_IDS
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_character_grant_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    spell_values = ", ".join(f"({guid}, {int(spell_id)}, {BROUG_GUARD_SPEC_MASK})" for spell_id in BROUG_GUARD_SHELL_IDS)
    retired_spell_values = ", ".join(
        str(spell_id) for spell_id in (BROUG_RETIRED_MOBILE_MARKSMAN_SHELL_ID, BROUG_RETIRED_SKIRMISHER_TOGGLE_SHELL_ID)
    )
    return (
        f"DELETE FROM character_spell WHERE `guid` = {guid} AND `spell` IN ({retired_spell_values});\n"
        "INSERT INTO character_spell (`guid`, `spell`, `specMask`) VALUES "
        f"{spell_values} "
        "ON DUPLICATE KEY UPDATE `specMask` = VALUES(`specMask`);"
    )


def build_world_grant_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    statements: list[str] = [
        "UPDATE wm_spell_grant "
        "SET RevokedAt = COALESCE(RevokedAt, CURRENT_TIMESTAMP), "
        "MetadataJSON = '{\"status\":\"BROKEN\",\"replaced_by\":946098,\"reason\":\"replaced_by_targeted_skirmisher_shot_v1\"}' "
        f"WHERE PlayerGUID = {guid} "
        f"AND ShellSpellID IN ({BROUG_RETIRED_MOBILE_MARKSMAN_SHELL_ID}, {BROUG_RETIRED_SKIRMISHER_TOGGLE_SHELL_ID});",
    ]
    for shell_id in BROUG_GUARD_SHELL_IDS:
        metadata = json.dumps(_grant_metadata(shell_id), sort_keys=True)
        statements.extend(
            [
                "UPDATE wm_spell_grant "
                f"SET GrantKind = {_sql_string(GRANT_KIND)}, Author = {_sql_string(GRANT_AUTHOR)}, MetadataJSON = {_sql_string(metadata)} "
                f"WHERE PlayerGUID = {guid} "
                f"AND ShellSpellID = {int(shell_id)} "
                "AND RevokedAt IS NULL;",
                "INSERT INTO wm_spell_grant "
                "(PlayerGUID, ShellSpellID, GrantKind, Author, MetadataJSON) "
                f"SELECT {guid}, {int(shell_id)}, {_sql_string(GRANT_KIND)}, {_sql_string(GRANT_AUTHOR)}, {_sql_string(metadata)} "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM wm_spell_grant "
                f"WHERE PlayerGUID = {guid} "
                f"AND ShellSpellID = {int(shell_id)} "
                "AND RevokedAt IS NULL"
                ");",
            ]
        )
    return "\n".join(statements)


def grant_broug_guard(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    mode: str = "dry-run",
) -> BrougGuardGrantResult:
    guid = _validate_player_guid(player_guid)
    if mode not in {"dry-run", "apply"}:
        raise ValueError(f"Unsupported Broug guard grant mode: {mode}")

    notes = [
        "explicit_player_guid_required=true",
        "does_not_touch_playercreateinfo=true",
        "does_not_touch_mod_learnspells=true",
        f"universal_parry_shell_id={BROUG_UNIVERSAL_PARRY_SHELL_ID}",
        f"retired_mobile_marksman_shell_id={BROUG_RETIRED_MOBILE_MARKSMAN_SHELL_ID}",
        f"retired_skirmisher_toggle_shell_id={BROUG_RETIRED_SKIRMISHER_TOGGLE_SHELL_ID}",
        f"skirmisher_mark_shell_id={BROUG_SKIRMISHER_MARK_SHELL_ID}",
        "native_runtime_requires_worldserver_restart=true",
        "client_spellbook_requires_patch_restart=true",
    ]
    if mode == "dry-run":
        return BrougGuardGrantResult(mode=mode, ok=True, applied=False, player_guid=guid, notes=notes)

    client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=build_character_grant_sql(guid),
    )
    client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql=build_world_grant_sql(guid),
    )
    return BrougGuardGrantResult(mode=mode, ok=True, applied=True, player_guid=guid, notes=notes)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wm.spells.broug_guard",
        description=(
            "Explicit Broug guard grant. This writes persistent character_spell rows for one player GUID "
            "and records active wm_spell_grant rows for Impossible Guard and Skirmisher's Mark."
        ),
    )
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--show-sql", action="store_true", help="Print the character/world SQL plan.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    result = grant_broug_guard(
        client=MysqlCliClient(),
        settings=settings,
        player_guid=int(args.player_guid),
        mode=str(args.mode),
    )
    payload = result.to_dict()
    if args.show_sql:
        payload["character_sql"] = build_character_grant_sql(int(args.player_guid))
        payload["world_sql"] = build_world_grant_sql(int(args.player_guid))

    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary:
        _print_summary(result)
        if args.show_sql:
            print("character_sql:")
            print(payload["character_sql"])
            print("world_sql:")
            print(payload["world_sql"])
    else:
        print(raw)
    return 0 if result.ok else 1


def _print_summary(result: BrougGuardGrantResult) -> None:
    print(
        f"mode={result.mode} ok={str(result.ok).lower()} applied={str(result.applied).lower()} "
        f"player_guid={result.player_guid} shell_spell_ids={','.join(str(spell_id) for spell_id in result.shell_spell_ids)}"
    )
    if result.notes:
        for note in result.notes:
            print(f"note={note}")


def _grant_metadata(shell_id: int) -> dict[str, object]:
    if int(shell_id) == BROUG_UNIVERSAL_PARRY_SHELL_ID:
        return {
            "capability": "universal_parry",
            "behavior_kind": "broug_universal_parry_v1",
            "counter_key": "universal_parry",
            "scales_with": ["strength", "agility", "expertise", "weapon_mastery"],
            "status": "PARTIAL",
        }
    if int(shell_id) == BROUG_SKIRMISHER_MARK_SHELL_ID:
        return {
            "capability": "skirmisher_mark",
            "behavior_kind": "broug_skirmisher_shot_v1",
            "counter_key": "skirmisher_shot_hit",
            "scales_with": ["ranged_auto_attack_damage", "ranged_attack_power", "ranged_weapon_speed"],
            "status": "PARTIAL",
        }
    return {"capability": "unknown", "status": "PARTIAL"}


def _validate_player_guid(player_guid: int) -> int:
    guid = int(player_guid)
    if guid <= 0:
        raise ValueError("player_guid must be a positive explicit character GUID")
    return guid


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
