from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient


BROUG_PLAYER_GUID = 5405
BROUG_LIGHTNESS_ARC_KEY = "broug_lightness_assassin_v1"
BROUG_LIGHTNESS_STAGE_KEY = "footwork_trial"
BROUG_STEPS_QUEST_ID = 910182
BROUG_NO_FOOTFALL_QUEST_ID = 910183
BROUG_STEPS_TARGET_ENTRY = 2261
BROUG_STEPS_TARGET_NAME = "Syndicate Watchman"
BROUG_STEPS_TARGET_COUNT = 8
BROUG_CLOUD_STEP_SHELL_ID = 946202
BROUG_MARKED_MERIDIAN_SHELL_ID = 946203
BROUG_KILLING_INTENT_SHELL_ID = 946620
BROUG_SILENT_MERIDIAN_SHELL_ID = 946803
BROUG_CLOUD_STEP_CREDIT_ENTRY = 920106
BROUG_LIGHTNESS_VISIBLE_SHELL_IDS = (
    BROUG_CLOUD_STEP_SHELL_ID,
    BROUG_MARKED_MERIDIAN_SHELL_ID,
    BROUG_KILLING_INTENT_SHELL_ID,
    BROUG_SILENT_MERIDIAN_SHELL_ID,
)
BROUG_LIGHTNESS_REWARD_SHELL_IDS = (BROUG_CLOUD_STEP_SHELL_ID, BROUG_SILENT_MERIDIAN_SHELL_ID)
BROUG_LIGHTNESS_MARKER_SHELL_IDS = (BROUG_MARKED_MERIDIAN_SHELL_ID, BROUG_KILLING_INTENT_SHELL_ID)
BROUG_PARALLEL_ENERGY_SURGE_ITEM_ID = 910014
BROUG_PARALLEL_ENERGY_SURGE_SELF_AURA_SHELL_ID = 946606
BROUG_LIGHTNESS_SPEC_MASK = 255
GRANT_KIND = "broug_lightness_reward"
GRANT_AUTHOR = "wm.spells.broug_lightness"


@dataclass(slots=True)
class BrougLightnessGrantResult:
    mode: str
    ok: bool
    applied: bool
    player_guid: int
    grant_rewards: bool
    shell_spell_ids: tuple[int, ...] = BROUG_LIGHTNESS_REWARD_SHELL_IDS
    notes: list[str] | None = None
    verification: dict[str, list[dict[str, Any]]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_character_journey_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    summary = (
        "Broug pivots out of guard expansion into a murim-style lightness assassin arc: "
        "qinggong movement, killing intent, afterimage timing, and thrown-blade followups."
    )
    return "\n".join(
        [
            "INSERT INTO wm_character_profile "
            "(CharacterGUID, CharacterName, WMPersona, Tone, PreferredThemesJSON, AvoidedThemesJSON) VALUES "
            f"({guid}, 'Broug', 'lightness_assassin_candidate', 'direct', "
            "'[\"murim lightness\", \"rogue movement\", \"assassin timing\", \"visible shell powers\"]', "
            "'[\"more parry expansion\", \"stock spell carriers\", \"invisible-only passives\"]') "
            "ON DUPLICATE KEY UPDATE "
            "CharacterName = VALUES(CharacterName), WMPersona = VALUES(WMPersona), Tone = VALUES(Tone), "
            "PreferredThemesJSON = VALUES(PreferredThemesJSON), AvoidedThemesJSON = VALUES(AvoidedThemesJSON);",
            "INSERT INTO wm_character_arc_state "
            "(CharacterGUID, ArcKey, StageKey, Status, BranchKey, Summary) VALUES "
            f"({guid}, {_sql_string(BROUG_LIGHTNESS_ARC_KEY)}, {_sql_string(BROUG_LIGHTNESS_STAGE_KEY)}, "
            "'active', 'lightness_assassin', "
            f"{_sql_string(summary)}) "
            "ON DUPLICATE KEY UPDATE "
            "StageKey = VALUES(StageKey), Status = VALUES(Status), BranchKey = VALUES(BranchKey), Summary = VALUES(Summary);",
            "INSERT INTO wm_character_conversation_steering "
            "(CharacterGUID, SteeringKey, SteeringKind, Body, Priority, Source, IsActive, MetadataJSON) VALUES "
            f"({guid}, 'broug_lightness_over_guard', 'operator_direction', "
            "'Treat Broug''s old guard kit as completed foundation. Do not add new parry mechanics in the lightness V1 arc.', "
            "100, 'operator', 1, "
            f"{_sql_string(json.dumps({'arc_key': BROUG_LIGHTNESS_ARC_KEY, 'stage_key': BROUG_LIGHTNESS_STAGE_KEY}, sort_keys=True))}) "
            "ON DUPLICATE KEY UPDATE "
            "SteeringKind = VALUES(SteeringKind), Body = VALUES(Body), Priority = VALUES(Priority), "
            "Source = VALUES(Source), IsActive = VALUES(IsActive), MetadataJSON = VALUES(MetadataJSON);",
        ]
    )


def build_character_grant_sql(player_guid: int, *, include_manual: bool = False) -> str:
    guid = _validate_player_guid(player_guid)
    shell_ids = _reward_shell_ids(include_manual=include_manual)
    spell_values = ", ".join(f"({guid}, {int(spell_id)}, {BROUG_LIGHTNESS_SPEC_MASK})" for spell_id in shell_ids)
    return (
        "INSERT INTO character_spell (`guid`, `spell`, `specMask`) VALUES "
        f"{spell_values} "
        "ON DUPLICATE KEY UPDATE `specMask` = VALUES(`specMask`);"
    )


def build_world_grant_sql(player_guid: int, *, include_manual: bool = False) -> str:
    guid = _validate_player_guid(player_guid)
    statements: list[str] = []
    for shell_id in _reward_shell_ids(include_manual=include_manual):
        metadata = json.dumps(_grant_metadata(shell_id), sort_keys=True)
        source_quest_id = BROUG_NO_FOOTFALL_QUEST_ID if shell_id == BROUG_SILENT_MERIDIAN_SHELL_ID else BROUG_STEPS_QUEST_ID
        statements.extend(
            [
                "UPDATE wm_spell_grant "
                f"SET GrantKind = {_sql_string(GRANT_KIND)}, SourceQuestID = {source_quest_id}, "
                f"Author = {_sql_string(GRANT_AUTHOR)}, MetadataJSON = {_sql_string(metadata)} "
                f"WHERE PlayerGUID = {guid} "
                f"AND ShellSpellID = {int(shell_id)} "
                "AND RevokedAt IS NULL;",
                "INSERT INTO wm_spell_grant "
                "(PlayerGUID, ShellSpellID, GrantKind, SourceQuestID, Author, MetadataJSON) "
                f"SELECT {guid}, {int(shell_id)}, {_sql_string(GRANT_KIND)}, {source_quest_id}, "
                f"{_sql_string(GRANT_AUTHOR)}, {_sql_string(metadata)} "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM wm_spell_grant "
                f"WHERE PlayerGUID = {guid} "
                f"AND ShellSpellID = {int(shell_id)} "
                "AND RevokedAt IS NULL"
                ");",
            ]
        )
    return "\n".join(statements)


def build_world_verify_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    shell_ids = ", ".join(str(spell_id) for spell_id in BROUG_LIGHTNESS_VISIBLE_SHELL_IDS)
    return "\n".join(
        [
            "SELECT ShellSpellID, ShellKey, FamilyID, Label FROM wm_spell_shell "
            f"WHERE ShellSpellID IN ({shell_ids}) ORDER BY ShellSpellID;",
            "SELECT ShellSpellID, BehaviorKind, Status FROM wm_spell_behavior "
            f"WHERE ShellSpellID IN ({shell_ids}) ORDER BY ShellSpellID;",
            "SELECT PlayerGUID, ShellSpellID, GrantKind, SourceQuestID, RevokedAt FROM wm_spell_grant "
            f"WHERE PlayerGUID = {guid} AND ShellSpellID IN ({BROUG_CLOUD_STEP_SHELL_ID}, {BROUG_SILENT_MERIDIAN_SHELL_ID}) "
            "ORDER BY ShellSpellID, GrantID;",
            "SELECT PlayerGUID, CounterKey, CounterValue FROM wm_broug_lightness_counter "
            f"WHERE PlayerGUID = {guid} ORDER BY CounterKey;",
        ]
    )


def build_character_verify_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    reward_shells = ", ".join(str(spell_id) for spell_id in BROUG_LIGHTNESS_REWARD_SHELL_IDS)
    return "\n".join(
        [
            "SELECT CharacterGUID, ArcKey, StageKey, Status, BranchKey FROM wm_character_arc_state "
            f"WHERE CharacterGUID = {guid} AND ArcKey = {_sql_string(BROUG_LIGHTNESS_ARC_KEY)};",
            "SELECT `guid`, `spell`, `specMask` FROM character_spell "
            f"WHERE `guid` = {guid} AND `spell` IN ({reward_shells}) ORDER BY `spell`;",
        ]
    )


def grant_broug_lightness(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    mode: str = "dry-run",
    grant_rewards: bool = False,
    include_manual: bool = False,
) -> BrougLightnessGrantResult:
    guid = _validate_player_guid(player_guid)
    if mode not in {"dry-run", "apply", "verify"}:
        raise ValueError(f"Unsupported Broug lightness grant mode: {mode}")

    notes = [
        "explicit_player_guid_required=true",
        "journey_arc_key=broug_lightness_assassin_v1",
        "journey_stage_key=footwork_trial",
        f"cloud_step_shell_id={BROUG_CLOUD_STEP_SHELL_ID}",
        f"marked_meridian_shell_id={BROUG_MARKED_MERIDIAN_SHELL_ID}",
        f"killing_intent_shell_id={BROUG_KILLING_INTENT_SHELL_ID}",
        f"silent_meridian_shell_id={BROUG_SILENT_MERIDIAN_SHELL_ID}",
        f"parallel_energy_surge_item_reserved={BROUG_PARALLEL_ENERGY_SURGE_ITEM_ID}",
        f"parallel_energy_surge_self_aura_reserved={BROUG_PARALLEL_ENERGY_SURGE_SELF_AURA_SHELL_ID}",
        "does_not_touch_playercreateinfo=true",
        "does_not_touch_mod_learnspells=true",
        "does_not_expand_parry_behavior=true",
    ]
    grant_shell_ids = _reward_shell_ids(include_manual=include_manual) if grant_rewards else ()
    if mode == "verify":
        verification: dict[str, list[dict[str, Any]]] = {}
        for index, statement in enumerate(_split_sql_statements(build_character_verify_sql(guid)), start=1):
            verification[f"character_{index}"] = client.query(
                host=settings.char_db_host,
                port=settings.char_db_port,
                user=settings.char_db_user,
                password=settings.char_db_password,
                database=settings.char_db_name,
                sql=statement,
            )
        for index, statement in enumerate(_split_sql_statements(build_world_verify_sql(guid)), start=1):
            verification[f"world_{index}"] = client.query(
                host=settings.world_db_host,
                port=settings.world_db_port,
                user=settings.world_db_user,
                password=settings.world_db_password,
                database=settings.world_db_name,
                sql=statement,
            )
        return BrougLightnessGrantResult(
            mode=mode,
            ok=True,
            applied=False,
            player_guid=guid,
            grant_rewards=grant_rewards,
            shell_spell_ids=grant_shell_ids,
            notes=[*notes, "verify_only=true"],
            verification=verification,
        )
    if mode == "dry-run":
        return BrougLightnessGrantResult(
            mode=mode,
            ok=True,
            applied=False,
            player_guid=guid,
            grant_rewards=grant_rewards,
            shell_spell_ids=grant_shell_ids,
            notes=notes,
        )

    client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=build_character_journey_sql(guid),
    )
    if grant_rewards:
        client.query(
            host=settings.char_db_host,
            port=settings.char_db_port,
            user=settings.char_db_user,
            password=settings.char_db_password,
            database=settings.char_db_name,
            sql=build_character_grant_sql(guid, include_manual=include_manual),
        )
        client.query(
            host=settings.world_db_host,
            port=settings.world_db_port,
            user=settings.world_db_user,
            password=settings.world_db_password,
            database=settings.world_db_name,
            sql=build_world_grant_sql(guid, include_manual=include_manual),
        )
    return BrougLightnessGrantResult(
        mode=mode,
        ok=True,
        applied=True,
        player_guid=guid,
        grant_rewards=grant_rewards,
        shell_spell_ids=grant_shell_ids,
        notes=notes,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wm.spells.broug_lightness",
        description=(
            "Explicit Broug lightness-assassin helper. By default apply records the journey arc only; "
            "reward shell grants stay quest-owned unless --grant-rewards is supplied for lab recovery."
        ),
    )
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply", "verify"], default="dry-run")
    parser.add_argument("--grant-rewards", action="store_true")
    parser.add_argument("--include-manual", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--show-sql", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    result = grant_broug_lightness(
        client=MysqlCliClient(),
        settings=settings,
        player_guid=int(args.player_guid),
        mode=str(args.mode),
        grant_rewards=bool(args.grant_rewards),
        include_manual=bool(args.include_manual),
    )
    payload = result.to_dict()
    if args.show_sql:
        payload["character_journey_sql"] = build_character_journey_sql(int(args.player_guid))
        payload["character_verify_sql"] = build_character_verify_sql(int(args.player_guid))
        payload["world_verify_sql"] = build_world_verify_sql(int(args.player_guid))
        if args.grant_rewards:
            payload["character_grant_sql"] = build_character_grant_sql(
                int(args.player_guid),
                include_manual=bool(args.include_manual),
            )
            payload["world_grant_sql"] = build_world_grant_sql(
                int(args.player_guid),
                include_manual=bool(args.include_manual),
            )

    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary:
        _print_summary(result)
        if args.show_sql:
            print("character_journey_sql:")
            print(payload["character_journey_sql"])
            if args.grant_rewards:
                print("character_grant_sql:")
                print(payload["character_grant_sql"])
                print("world_grant_sql:")
                print(payload["world_grant_sql"])
            print("character_verify_sql:")
            print(payload["character_verify_sql"])
            print("world_verify_sql:")
            print(payload["world_verify_sql"])
    else:
        print(raw)
    return 0 if result.ok else 1


def _print_summary(result: BrougLightnessGrantResult) -> None:
    shell_ids = ",".join(str(spell_id) for spell_id in result.shell_spell_ids) if result.shell_spell_ids else "none"
    print(
        f"mode={result.mode} ok={str(result.ok).lower()} applied={str(result.applied).lower()} "
        f"player_guid={result.player_guid} grant_rewards={str(result.grant_rewards).lower()} "
        f"shell_spell_ids={shell_ids}"
    )
    if result.notes:
        for note in result.notes:
            print(f"note={note}")


def _reward_shell_ids(*, include_manual: bool) -> tuple[int, ...]:
    if include_manual:
        return BROUG_LIGHTNESS_REWARD_SHELL_IDS
    return (BROUG_CLOUD_STEP_SHELL_ID,)


def _grant_metadata(shell_id: int) -> dict[str, object]:
    if int(shell_id) == BROUG_CLOUD_STEP_SHELL_ID:
        return {
            "capability": "cloud_step",
            "behavior_kind": "broug_cloud_step_v1",
            "counter_key": "cloud_step_strike",
            "arc_key": BROUG_LIGHTNESS_ARC_KEY,
            "status": "PARTIAL",
        }
    if int(shell_id) == BROUG_SILENT_MERIDIAN_SHELL_ID:
        return {
            "capability": "silent_meridian",
            "behavior_kind": "broug_silent_meridian_v1",
            "counter_key": "silent_meridian_kill",
            "arc_key": BROUG_LIGHTNESS_ARC_KEY,
            "status": "PARTIAL",
        }
    return {"capability": "unknown", "arc_key": BROUG_LIGHTNESS_ARC_KEY, "status": "PARTIAL"}


def _split_sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def _validate_player_guid(player_guid: int) -> int:
    guid = int(player_guid)
    if guid <= 0:
        raise ValueError("player_guid must be a positive explicit character GUID")
    return guid


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
