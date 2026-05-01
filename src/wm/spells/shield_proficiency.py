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
MAIL_SKILL_ID = 413
MAIL_SKILL_VALUE = 1
MAIL_SKILL_MAX = 1
MAIL_SPELL_IDS = (8737,)
PLATE_SKILL_ID = 293
PLATE_SKILL_VALUE = 1
PLATE_SKILL_MAX = 1
PLATE_SPELL_IDS = (750,)
PLATE_MIN_LEVEL = 40
DUAL_WIELD_SKILL_ID = 118
DUAL_WIELD_SKILL_VALUE = 1
DUAL_WIELD_SKILL_MAX = 1
DUAL_WIELD_SPELL_ID = 674
TWO_HANDED_SWORDS_SKILL_ID = 55
TWO_HANDED_SWORDS_SPELL_ID = 202
TWO_HANDED_AXES_SKILL_ID = 172
TWO_HANDED_AXES_SPELL_ID = 197
POLEARMS_SKILL_ID = 229
POLEARMS_SPELL_ID = 200
WEAPON_PROFICIENCY_SKILL_VALUE = 1
WEAPON_PROFICIENCY_SKILL_MAX = 1
WEAPON_PROFICIENCY_SKILL_MAX_PER_LEVEL = 5
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
        "key": "mail_armor",
        "skill_id": MAIL_SKILL_ID,
        "skill_value": MAIL_SKILL_VALUE,
        "skill_max": MAIL_SKILL_MAX,
        "spell_ids": MAIL_SPELL_IDS,
    },
    {
        "key": "dual_wield",
        "skill_id": DUAL_WIELD_SKILL_ID,
        "skill_value": DUAL_WIELD_SKILL_VALUE,
        "skill_max": DUAL_WIELD_SKILL_MAX,
        "spell_ids": DIRECT_SPELL_IDS,
    },
    {
        "key": "two_handed_swords",
        "skill_id": TWO_HANDED_SWORDS_SKILL_ID,
        "skill_value": WEAPON_PROFICIENCY_SKILL_VALUE,
        "skill_max": WEAPON_PROFICIENCY_SKILL_MAX,
        "skill_max_per_level": WEAPON_PROFICIENCY_SKILL_MAX_PER_LEVEL,
        "spell_ids": (TWO_HANDED_SWORDS_SPELL_ID,),
    },
    {
        "key": "two_handed_axes",
        "skill_id": TWO_HANDED_AXES_SKILL_ID,
        "skill_value": WEAPON_PROFICIENCY_SKILL_VALUE,
        "skill_max": WEAPON_PROFICIENCY_SKILL_MAX,
        "skill_max_per_level": WEAPON_PROFICIENCY_SKILL_MAX_PER_LEVEL,
        "spell_ids": (TWO_HANDED_AXES_SPELL_ID,),
    },
    {
        "key": "polearms",
        "skill_id": POLEARMS_SKILL_ID,
        "skill_value": WEAPON_PROFICIENCY_SKILL_VALUE,
        "skill_max": WEAPON_PROFICIENCY_SKILL_MAX,
        "skill_max_per_level": WEAPON_PROFICIENCY_SKILL_MAX_PER_LEVEL,
        "spell_ids": (POLEARMS_SPELL_ID,),
    },
)
LEVEL_GATED_SKILL_GRANTS = (
    {
        "key": "plate_armor",
        "skill_id": PLATE_SKILL_ID,
        "skill_value": PLATE_SKILL_VALUE,
        "skill_max": PLATE_SKILL_MAX,
        "spell_ids": PLATE_SPELL_IDS,
        "min_character_level": PLATE_MIN_LEVEL,
    },
)
ALL_KNOWN_SKILL_GRANTS = SKILL_GRANTS + LEVEL_GATED_SKILL_GRANTS
ALL_SPELL_IDS = tuple(int(spell_id) for grant in ALL_KNOWN_SKILL_GRANTS for spell_id in grant["spell_ids"])
ALL_SKILL_IDS = tuple(int(grant["skill_id"]) for grant in ALL_KNOWN_SKILL_GRANTS)


@dataclass(slots=True)
class ShieldProficiencyGrantResult:
    mode: str
    ok: bool
    applied: bool
    player_guid: int
    skill_id: int = SHIELD_SKILL_ID
    skill_value: int = SHIELD_SKILL_VALUE
    skill_max: int = SHIELD_SKILL_MAX
    skill_ids: tuple[int, ...] = ALL_SKILL_IDS
    spell_ids: tuple[int, ...] = ALL_SPELL_IDS
    passive_shell_id: int = PASSIVE_SHELL_ID
    player_level: int | None = None
    plate_granted: bool = False
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_character_grant_sql(
    player_guid: int,
    *,
    include_plate: bool = False,
    player_level: int | None = None,
) -> str:
    guid = _validate_player_guid(player_guid)
    level = _normalize_player_level(player_level)
    skill_grants = _active_skill_grants(include_plate=include_plate)
    skill_values = ", ".join(
        f"({guid}, {int(grant['skill_id'])}, {int(grant['skill_value'])}, {_skill_max_for_grant(grant, level)})"
        for grant in skill_grants
    )
    spell_ids = tuple(int(spell_id) for grant in skill_grants for spell_id in grant["spell_ids"])
    spell_values = ", ".join(f"({guid}, {int(spell_id)}, {SHIELD_SPEC_MASK})" for spell_id in spell_ids)
    return "\n".join(
        [
            "INSERT INTO character_skills (`guid`, `skill`, `value`, `max`) VALUES "
            f"{skill_values} "
            "ON DUPLICATE KEY UPDATE `value` = GREATEST(`value`, VALUES(`value`)), "
            "`max` = GREATEST(`max`, VALUES(`max`));",
            "INSERT INTO character_spell (`guid`, `spell`, `specMask`) VALUES "
            f"{spell_values} "
            "ON DUPLICATE KEY UPDATE `specMask` = VALUES(`specMask`);",
        ]
    )


def build_world_grant_sql(player_guid: int, *, include_plate: bool = False, player_level: int | None = None) -> str:
    guid = _validate_player_guid(player_guid)
    skill_grants = _active_skill_grants(include_plate=include_plate)
    active_capabilities = [str(grant["key"]) for grant in skill_grants]
    locked_capabilities = []
    if not include_plate:
        locked_capabilities.append(
            {
                "key": "plate_armor",
                "min_character_level": PLATE_MIN_LEVEL,
                "current_level": int(player_level) if player_level is not None else None,
            }
        )
    metadata = json.dumps(
        {
            "capabilities": active_capabilities,
            "locked_capabilities": locked_capabilities,
            "weapon_capabilities": ["two_handed_swords", "two_handed_axes", "polearms"],
            "armor_capabilities": ["shield", "leather_armor", "mail_armor"] + (["plate_armor"] if include_plate else []),
            "skill_grants": list(skill_grants),
            "level_gated_skill_grants": list(LEVEL_GATED_SKILL_GRANTS),
            "direct_spell_ids": list(DIRECT_SPELL_IDS),
            "spell_ids": [int(spell_id) for grant in skill_grants for spell_id in grant["spell_ids"]],
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
    player_level_override: int | None = None,
) -> ShieldProficiencyGrantResult:
    guid = _validate_player_guid(player_guid)
    if mode not in {"dry-run", "apply"}:
        raise ValueError(f"Unsupported shield grant mode: {mode}")

    notes = [
        "explicit_player_guid_required=true",
        "does_not_touch_playercreateinfo=true",
        "does_not_touch_mod_learnspells=true",
        "leather_armor_skill=414",
        "mail_armor_skill=413",
        "mail_armor_spell=8737",
        f"plate_armor_min_level={PLATE_MIN_LEVEL}",
        "plate_armor_skill=293",
        "plate_armor_spell=750",
        "dual_wield_skill=118",
        "dual_wield_spell=674",
        "two_handed_swords_skill=55",
        "two_handed_swords_spell=202",
        "two_handed_axes_skill=172",
        "two_handed_axes_spell=197",
        "polearms_skill=229",
        "polearms_spell=200",
        "dbc_override_requires_worldserver_restart=true",
    ]

    if mode == "dry-run":
        return ShieldProficiencyGrantResult(
            mode=mode,
            ok=True,
            applied=False,
            player_guid=guid,
            skill_ids=ALL_SKILL_IDS,
            spell_ids=ALL_SPELL_IDS,
            notes=notes,
        )

    player_level = (
        _normalize_player_level(player_level_override)
        if player_level_override is not None
        else _load_player_level(client=client, settings=settings, player_guid=guid)
    )
    include_plate = player_level is not None and player_level >= PLATE_MIN_LEVEL
    if include_plate:
        notes.append("plate_armor_granted=true")
    else:
        notes.append("plate_armor_granted=false")
        notes.append("plate_armor_locked_until_level=40")

    client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=build_character_grant_sql(guid, include_plate=include_plate, player_level=player_level),
    )
    client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql=build_world_grant_sql(guid, include_plate=include_plate, player_level=player_level),
    )
    return ShieldProficiencyGrantResult(
        mode=mode,
        ok=True,
        applied=True,
        player_guid=guid,
        skill_ids=tuple(int(grant["skill_id"]) for grant in _active_skill_grants(include_plate=include_plate)),
        spell_ids=tuple(
            int(spell_id)
            for grant in _active_skill_grants(include_plate=include_plate)
            for spell_id in grant["spell_ids"]
        ),
        player_level=player_level,
        plate_granted=include_plate,
        notes=notes,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wm.spells.shield_proficiency",
        description=(
            "Explicit WM combat proficiency grant. This writes persistent character skill/spell rows "
            "for one player GUID and adds WM combat proficiency metadata for Shield, Leather, Dual Wield, "
            "Mail, level-gated Plate, two-handed swords, two-handed axes, and polearms."
        ),
    )
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--show-sql", action="store_true", help="Print the character/world SQL plan without executing extra work.")
    parser.add_argument(
        "--player-level-override",
        type=int,
        help="Use a live-observed level for weapon skill caps when the character DB level is stale.",
    )
    return parser


def _print_summary(result: ShieldProficiencyGrantResult) -> None:
    print(
        f"mode={result.mode} ok={str(result.ok).lower()} applied={str(result.applied).lower()} "
        f"player_guid={result.player_guid} skill_id={result.skill_id} "
        f"skill_value={result.skill_value}/{result.skill_max} "
        f"skill_ids={','.join(str(skill_id) for skill_id in result.skill_ids)} "
        f"spell_ids={','.join(str(spell_id) for spell_id in result.spell_ids)} "
        f"passive_shell_id={result.passive_shell_id} "
        f"player_level={result.player_level} plate_granted={str(result.plate_granted).lower()}"
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
        player_level_override=args.player_level_override,
    )
    payload = result.to_dict()
    if args.show_sql:
        player_level = args.player_level_override
        payload["character_sql"] = build_character_grant_sql(
            int(args.player_guid),
            include_plate=player_level is not None and player_level >= PLATE_MIN_LEVEL,
            player_level=player_level,
        )
        payload["world_sql"] = build_world_grant_sql(
            int(args.player_guid),
            include_plate=player_level is not None and player_level >= PLATE_MIN_LEVEL,
            player_level=player_level,
        )

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


def _active_skill_grants(*, include_plate: bool) -> tuple[dict[str, object], ...]:
    return SKILL_GRANTS + (LEVEL_GATED_SKILL_GRANTS if include_plate else ())


def _normalize_player_level(player_level: int | None) -> int:
    if player_level is None:
        return 1
    return max(1, int(player_level))


def _skill_max_for_grant(grant: dict[str, object], player_level: int) -> int:
    skill_max = int(grant["skill_max"])
    skill_max_per_level = grant.get("skill_max_per_level")
    if skill_max_per_level is None:
        return skill_max
    return max(skill_max, player_level * int(skill_max_per_level))


def _load_player_level(*, client: MysqlCliClient, settings: Settings, player_guid: int) -> int | None:
    rows = client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=f"SELECT level FROM characters WHERE guid = {int(player_guid)} LIMIT 1",
    )
    if not rows:
        return None
    try:
        return int(rows[0].get("level") or rows[0].get("Level") or 0)
    except (TypeError, ValueError):
        return None


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
