from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient

SHIELD_SKILL_ID = 433
SHIELD_SKILL_VALUE = 1
SHIELD_SKILL_MAX = 1
SHIELD_SPELL_IDS = (107, 9116)
LEATHER_SKILL_ID = 414
LEATHER_SKILL_VALUE = 1
LEATHER_SKILL_MAX = 1
LEATHER_SPELL_IDS = (9077,)
DUAL_WIELD_SKILL_ID = 118
DUAL_WIELD_SKILL_VALUE = 1
DUAL_WIELD_SKILL_MAX = 1
DUAL_WIELD_SPELL_ID = 674
DIRECT_SPELL_IDS = (DUAL_WIELD_SPELL_ID,)
SHIELD_SPEC_MASK = 255
PASSIVE_SHELL_ID = 944000
GRANT_KIND = "combat_proficiency"
GRANT_AUTHOR = "wm.spells.shield_proficiency"

SKILL_GRANTS = (
    {
        "key": "shield",
        "skill_id": SHIELD_SKILL_ID,
        "skill_value": SHIELD_SKILL_VALUE,
        "skill_max": SHIELD_SKILL_MAX,
        "spell_ids": SHIELD_SPELL_IDS,
    },
    {
        "key": "leather_armor",
        "skill_id": LEATHER_SKILL_ID,
        "skill_value": LEATHER_SKILL_VALUE,
        "skill_max": LEATHER_SKILL_MAX,
        "spell_ids": LEATHER_SPELL_IDS,
    },
    {
        "key": "dual_wield",
        "skill_id": DUAL_WIELD_SKILL_ID,
        "skill_value": DUAL_WIELD_SKILL_VALUE,
        "skill_max": DUAL_WIELD_SKILL_MAX,
        "spell_ids": DIRECT_SPELL_IDS,
    },
)
ALL_SPELL_IDS = SHIELD_SPELL_IDS + LEATHER_SPELL_IDS + DIRECT_SPELL_IDS


@dataclass(slots=True)
class ShieldProficiencyGrantResult:
    mode: str
    ok: bool
    applied: bool
    player_guid: int
    skill_id: int = SHIELD_SKILL_ID
    skill_value: int = SHIELD_SKILL_VALUE
    skill_max: int = SHIELD_SKILL_MAX
    skill_ids: tuple[int, ...] = (SHIELD_SKILL_ID, LEATHER_SKILL_ID, DUAL_WIELD_SKILL_ID)
    spell_ids: tuple[int, ...] = ALL_SPELL_IDS
    passive_shell_id: int = PASSIVE_SHELL_ID
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_character_grant_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    skill_values = ", ".join(
        f"({guid}, {int(grant['skill_id'])}, {int(grant['skill_value'])}, {int(grant['skill_max'])})"
        for grant in SKILL_GRANTS
    )
    spell_values = ", ".join(f"({guid}, {int(spell_id)}, {SHIELD_SPEC_MASK})" for spell_id in ALL_SPELL_IDS)
    return "\n".join(
        [
            "INSERT INTO character_skills (`guid`, `skill`, `value`, `max`) VALUES "
            f"{skill_values} "
            "ON DUPLICATE KEY UPDATE `value` = VALUES(`value`), `max` = VALUES(`max`);",
            "INSERT INTO character_spell (`guid`, `spell`, `specMask`) VALUES "
            f"{spell_values} "
            "ON DUPLICATE KEY UPDATE `specMask` = VALUES(`specMask`);",
        ]
    )


def build_world_grant_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    metadata = json.dumps(
        {
            "capabilities": ["shield", "leather_armor", "dual_wield"],
            "skill_grants": list(SKILL_GRANTS),
            "direct_spell_ids": list(DIRECT_SPELL_IDS),
            "spell_ids": list(ALL_SPELL_IDS),
            "requires_dbc_restart": True,
        },
        sort_keys=True,
    )
    return "\n".join(
        [
            "UPDATE wm_spell_grant "
            f"SET GrantKind = {_sql_string(GRANT_KIND)}, Author = {_sql_string(GRANT_AUTHOR)}, MetadataJSON = {_sql_string(metadata)} "
            f"WHERE PlayerGUID = {guid} "
            f"AND ShellSpellID = {PASSIVE_SHELL_ID} "
            "AND RevokedAt IS NULL;",
            "INSERT INTO wm_spell_grant "
            "(PlayerGUID, ShellSpellID, GrantKind, Author, MetadataJSON) "
            f"SELECT {guid}, {PASSIVE_SHELL_ID}, {_sql_string(GRANT_KIND)}, {_sql_string(GRANT_AUTHOR)}, {_sql_string(metadata)} "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM wm_spell_grant "
            f"WHERE PlayerGUID = {guid} "
            f"AND ShellSpellID = {PASSIVE_SHELL_ID} "
            "AND RevokedAt IS NULL"
            ");",
        ]
    )


def grant_shield_proficiency(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    mode: str = "dry-run",
) -> ShieldProficiencyGrantResult:
    guid = _validate_player_guid(player_guid)
    if mode not in {"dry-run", "apply"}:
        raise ValueError(f"Unsupported shield grant mode: {mode}")

    notes = [
        "explicit_player_guid_required=true",
        "does_not_touch_playercreateinfo=true",
        "does_not_touch_mod_learnspells=true",
        "leather_armor_skill=414",
        "dual_wield_skill=118",
        "dual_wield_spell=674",
        "dbc_override_requires_worldserver_restart=true",
    ]

    if mode == "dry-run":
        return ShieldProficiencyGrantResult(
            mode=mode,
            ok=True,
            applied=False,
            player_guid=guid,
            notes=notes,
        )

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
    return ShieldProficiencyGrantResult(
        mode=mode,
        ok=True,
        applied=True,
        player_guid=guid,
        notes=notes,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wm.spells.shield_proficiency",
        description=(
            "Explicit WM Shield proficiency grant. This writes persistent character skill/spell rows "
            "for one player GUID and adds WM combat proficiency metadata for Shield, Leather, and Dual Wield."
        ),
    )
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--show-sql", action="store_true", help="Print the character/world SQL plan without executing extra work.")
    return parser


def _print_summary(result: ShieldProficiencyGrantResult) -> None:
    print(
        f"mode={result.mode} ok={str(result.ok).lower()} applied={str(result.applied).lower()} "
        f"player_guid={result.player_guid} skill_id={result.skill_id} "
        f"skill_value={result.skill_value}/{result.skill_max} "
        f"skill_ids={','.join(str(skill_id) for skill_id in result.skill_ids)} "
        f"spell_ids={','.join(str(spell_id) for spell_id in result.spell_ids)} "
        f"passive_shell_id={result.passive_shell_id}"
    )
    if result.notes:
        for note in result.notes:
            print(f"note={note}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    result = grant_shield_proficiency(
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


def _validate_player_guid(player_guid: int) -> int:
    guid = int(player_guid)
    if guid <= 0:
        raise ValueError("player_guid must be a positive explicit character GUID")
    return guid


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
