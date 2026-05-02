from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient


BROUG_PLAYER_GUID = 5405
BROUG_EMPTY_COURT_ARC_KEY = "broug_empty_court_v2"
BROUG_EMPTY_COURT_STAGE_KEY = "first_peak_empty_court"
BROUG_WEIGHT_QUEST_ID = 910184
BROUG_STILLING_QUEST_ID = 910185
BROUG_NINETY_EIGHT_QUEST_ID = 910186
BROUG_ROOM_QUEST_ID = 910187
BROUG_DOMAIN_UNSEALED_QUEST_ID = 910188
BROUG_WEI_JIN_ENTRY = 915500
BROUG_ASH_HUSHED_WOLF_ENTRY = 915510
BROUG_ASH_HUSHED_BOAR_ENTRY = 915511
BROUG_ASH_HUSHED_BEAR_ENTRY = 915512
BROUG_HAL_MORROW_ENTRY = 915520
BROUG_SILENT_HALL_FIRST_ENTRY = 915530
BROUG_SILENT_HALL_LAST_ENTRY = 915539
BROUG_COURT_REMNANT_ENTRY = 915540
BROUG_ASH_WORN_TRACK_GO = 195500
BROUG_BOLTED_CELLAR_HATCH_GO = 195501
BROUG_STILLNESS_CREDIT_ENTRY = 920107
BROUG_BOUNTY_CREDIT_ENTRY = 920108
BROUG_ROOM_CREDIT_ENTRY = 920109
BROUG_OATH_CREDIT_ENTRY = 920110
BROUG_SUPPRESSED_SHELL_ID = 946204
BROUG_QI_REVERSAL_SHELL_ID = 946621
BROUG_PURGED_STATE_SHELL_ID = 946622
BROUG_KILLING_INTENT_DOMAIN_SHELL_ID = 946804
BROUG_PREDATORS_STRIKE_SHELL_ID = 946805
BROUG_VITALITY_DRAIN_SHELL_ID = 946806
BROUG_EMPTY_COURT_VISIBLE_SHELL_IDS = (
    BROUG_SUPPRESSED_SHELL_ID,
    BROUG_QI_REVERSAL_SHELL_ID,
    BROUG_PURGED_STATE_SHELL_ID,
    BROUG_KILLING_INTENT_DOMAIN_SHELL_ID,
    BROUG_PREDATORS_STRIKE_SHELL_ID,
    BROUG_VITALITY_DRAIN_SHELL_ID,
)
BROUG_EMPTY_COURT_REWARD_SHELL_IDS = (
    BROUG_QI_REVERSAL_SHELL_ID,
    BROUG_PREDATORS_STRIKE_SHELL_ID,
    BROUG_KILLING_INTENT_DOMAIN_SHELL_ID,
    BROUG_VITALITY_DRAIN_SHELL_ID,
)
BROUG_EMPTY_COURT_SUPPORT_SHELL_IDS = (
    BROUG_SUPPRESSED_SHELL_ID,
    BROUG_PURGED_STATE_SHELL_ID,
)
BROUG_EMPTY_COURT_SPEC_MASK = 255
GRANT_KIND = "broug_empty_court_reward"
GRANT_AUTHOR = "wm.spells.broug_empty_court"


@dataclass(slots=True)
class BrougEmptyCourtGrantResult:
    mode: str
    ok: bool
    applied: bool
    player_guid: int
    grant_rewards: bool
    shell_spell_ids: tuple[int, ...] = ()
    notes: list[str] | None = None
    verification: dict[str, list[dict[str, Any]]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_character_journey_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    summary = (
        "Broug continues from Cloud Step into the First Peak of the Empty Court: "
        "room pressure, active cleanse, and sustain, without adding new guard mechanics."
    )
    steering_metadata = json.dumps(
        {"arc_key": BROUG_EMPTY_COURT_ARC_KEY, "stage_key": BROUG_EMPTY_COURT_STAGE_KEY},
        sort_keys=True,
    )
    return "\n".join(
        [
            "INSERT INTO wm_character_profile "
            "(CharacterGUID, CharacterName, WMPersona, Tone, PreferredThemesJSON, AvoidedThemesJSON) VALUES "
            f"({guid}, 'Broug', 'empty_court_lightness_assassin', 'direct', "
            "'[\"murim room pressure\", \"active cleanse\", \"marked sustain\", \"assassin domain\"]', "
            "'[\"new parry expansion\", \"stock spell carriers\", \"vulnerable stack mutation\"]') "
            "ON DUPLICATE KEY UPDATE "
            "CharacterName = VALUES(CharacterName), WMPersona = VALUES(WMPersona), Tone = VALUES(Tone), "
            "PreferredThemesJSON = VALUES(PreferredThemesJSON), AvoidedThemesJSON = VALUES(AvoidedThemesJSON);",
            "INSERT INTO wm_character_arc_state "
            "(CharacterGUID, ArcKey, StageKey, Status, BranchKey, Summary) VALUES "
            f"({guid}, {_sql_string(BROUG_EMPTY_COURT_ARC_KEY)}, {_sql_string(BROUG_EMPTY_COURT_STAGE_KEY)}, "
            "'active', 'empty_court_first_peak', "
            f"{_sql_string(summary)}) "
            "ON DUPLICATE KEY UPDATE "
            "StageKey = VALUES(StageKey), Status = VALUES(Status), BranchKey = VALUES(BranchKey), Summary = VALUES(Summary);",
            "INSERT INTO wm_character_conversation_steering "
            "(CharacterGUID, SteeringKey, SteeringKind, Body, Priority, Source, IsActive, MetadataJSON) VALUES "
            f"({guid}, 'broug_empty_court_v2_scope', 'operator_direction', "
            "'Build only the Empty Court V2 First Peak: room pressure, Qi Reversal, Predator sustain, and Vitality Drain. Do not add new parry mechanics or mutate Vulnerable stacks.', "
            "100, 'operator', 1, "
            f"{_sql_string(steering_metadata)}) "
            "ON DUPLICATE KEY UPDATE "
            "SteeringKind = VALUES(SteeringKind), Body = VALUES(Body), Priority = VALUES(Priority), "
            "Source = VALUES(Source), IsActive = VALUES(IsActive), MetadataJSON = VALUES(MetadataJSON);",
        ]
    )


def build_character_grant_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    values = ", ".join(
        f"({guid}, {int(spell_id)}, {BROUG_EMPTY_COURT_SPEC_MASK})"
        for spell_id in BROUG_EMPTY_COURT_REWARD_SHELL_IDS
    )
    return (
        "INSERT INTO character_spell (`guid`, `spell`, `specMask`) VALUES "
        f"{values} "
        "ON DUPLICATE KEY UPDATE `specMask` = VALUES(`specMask`);"
    )


def build_world_grant_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    statements: list[str] = []
    for shell_id in BROUG_EMPTY_COURT_REWARD_SHELL_IDS:
        quest_id = _source_quest_for_shell(shell_id)
        metadata = json.dumps(_grant_metadata(shell_id), sort_keys=True)
        statements.extend(
            [
                "UPDATE wm_spell_grant "
                f"SET GrantKind = {_sql_string(GRANT_KIND)}, SourceQuestID = {quest_id}, "
                f"Author = {_sql_string(GRANT_AUTHOR)}, MetadataJSON = {_sql_string(metadata)} "
                f"WHERE PlayerGUID = {guid} "
                f"AND ShellSpellID = {int(shell_id)} "
                "AND RevokedAt IS NULL;",
                "INSERT INTO wm_spell_grant "
                "(PlayerGUID, ShellSpellID, GrantKind, SourceQuestID, Author, MetadataJSON) "
                f"SELECT {guid}, {int(shell_id)}, {_sql_string(GRANT_KIND)}, {quest_id}, "
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
    visible_shells = ", ".join(str(spell_id) for spell_id in BROUG_EMPTY_COURT_VISIBLE_SHELL_IDS)
    reward_shells = ", ".join(str(spell_id) for spell_id in BROUG_EMPTY_COURT_REWARD_SHELL_IDS)
    quests = ", ".join(str(quest_id) for quest_id in _quest_ids())
    return "\n".join(
        [
            "SELECT ShellSpellID, ShellKey, FamilyID, Label FROM wm_spell_shell "
            f"WHERE ShellSpellID IN ({visible_shells}) ORDER BY ShellSpellID;",
            "SELECT ShellSpellID, BehaviorKind, Status FROM wm_spell_behavior "
            f"WHERE ShellSpellID IN ({visible_shells}) ORDER BY ShellSpellID;",
            "SELECT PlayerGUID, ShellSpellID, GrantKind, SourceQuestID, RevokedAt FROM wm_spell_grant "
            f"WHERE PlayerGUID = {guid} AND ShellSpellID IN ({reward_shells}) ORDER BY ShellSpellID, GrantID;",
            "SELECT ID, LogTitle, RewardDisplaySpell FROM quest_template "
            f"WHERE ID IN ({quests}) ORDER BY ID;",
            "SELECT PlayerGUID, CounterKey, CounterValue FROM wm_broug_empty_court_counter "
            f"WHERE PlayerGUID = {guid} ORDER BY CounterKey;",
        ]
    )


def build_character_verify_sql(player_guid: int) -> str:
    guid = _validate_player_guid(player_guid)
    reward_shells = ", ".join(str(spell_id) for spell_id in BROUG_EMPTY_COURT_REWARD_SHELL_IDS)
    return "\n".join(
        [
            "SELECT CharacterGUID, ArcKey, StageKey, Status, BranchKey FROM wm_character_arc_state "
            f"WHERE CharacterGUID = {guid} AND ArcKey = {_sql_string(BROUG_EMPTY_COURT_ARC_KEY)};",
            "SELECT `guid`, `spell`, `specMask` FROM character_spell "
            f"WHERE `guid` = {guid} AND `spell` IN ({reward_shells}) ORDER BY `spell`;",
        ]
    )


def build_sql_summary(player_guid: int, *, grant_rewards: bool = False) -> dict[str, str]:
    summary = {
        "character_journey_sql": build_character_journey_sql(player_guid),
        "character_verify_sql": build_character_verify_sql(player_guid),
        "world_verify_sql": build_world_verify_sql(player_guid),
    }
    if grant_rewards:
        summary["character_grant_sql"] = build_character_grant_sql(player_guid)
        summary["world_grant_sql"] = build_world_grant_sql(player_guid)
    return summary


def grant_broug_empty_court(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    mode: str = "dry-run",
    grant_rewards: bool = False,
) -> BrougEmptyCourtGrantResult:
    guid = _validate_player_guid(player_guid)
    if mode not in {"dry-run", "apply", "verify"}:
        raise ValueError(f"Unsupported Broug Empty Court grant mode: {mode}")

    notes = [
        "explicit_player_guid_required=true",
        f"journey_arc_key={BROUG_EMPTY_COURT_ARC_KEY}",
        f"journey_stage_key={BROUG_EMPTY_COURT_STAGE_KEY}",
        f"reward_shell_ids={','.join(str(spell_id) for spell_id in BROUG_EMPTY_COURT_REWARD_SHELL_IDS)}",
        f"support_shell_ids={','.join(str(spell_id) for spell_id in BROUG_EMPTY_COURT_SUPPORT_SHELL_IDS)}",
        "does_not_touch_playercreateinfo=true",
        "does_not_touch_mod_learnspells=true",
        "does_not_touch_item_910014=true",
        "does_not_reuse_920106=true",
        "does_not_mutate_vulnerable=true",
    ]
    grant_shell_ids = BROUG_EMPTY_COURT_REWARD_SHELL_IDS if grant_rewards else ()

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
        return BrougEmptyCourtGrantResult(
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
        return BrougEmptyCourtGrantResult(
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
    return BrougEmptyCourtGrantResult(
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
        prog="python -m wm.spells.broug_empty_court",
        description=(
            "Explicit Broug Empty Court V2 helper. By default apply records the journey arc only; "
            "reward shell grants stay quest-owned unless --grant-rewards is supplied for lab recovery."
        ),
    )
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply", "verify"], default="dry-run")
    parser.add_argument("--grant-rewards", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--show-sql", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    result = grant_broug_empty_court(
        client=MysqlCliClient(),
        settings=settings,
        player_guid=int(args.player_guid),
        mode=str(args.mode),
        grant_rewards=bool(args.grant_rewards),
    )
    payload = result.to_dict()
    if args.show_sql:
        payload.update(build_sql_summary(int(args.player_guid), grant_rewards=bool(args.grant_rewards)))

    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary:
        _print_summary(result)
        if args.show_sql:
            for key, value in build_sql_summary(int(args.player_guid), grant_rewards=bool(args.grant_rewards)).items():
                print(f"{key}:")
                print(value)
    else:
        print(raw)
    return 0 if result.ok else 1


def _print_summary(result: BrougEmptyCourtGrantResult) -> None:
    shell_ids = ",".join(str(spell_id) for spell_id in result.shell_spell_ids) if result.shell_spell_ids else "none"
    print(
        f"mode={result.mode} ok={str(result.ok).lower()} applied={str(result.applied).lower()} "
        f"player_guid={result.player_guid} grant_rewards={str(result.grant_rewards).lower()} "
        f"shell_spell_ids={shell_ids}"
    )
    if result.notes:
        for note in result.notes:
            print(f"note={note}")


def _quest_ids() -> tuple[int, ...]:
    return (
        BROUG_WEIGHT_QUEST_ID,
        BROUG_STILLING_QUEST_ID,
        BROUG_NINETY_EIGHT_QUEST_ID,
        BROUG_ROOM_QUEST_ID,
        BROUG_DOMAIN_UNSEALED_QUEST_ID,
    )


def _source_quest_for_shell(shell_id: int) -> int:
    if int(shell_id) == BROUG_QI_REVERSAL_SHELL_ID:
        return BROUG_STILLING_QUEST_ID
    if int(shell_id) == BROUG_PREDATORS_STRIKE_SHELL_ID:
        return BROUG_NINETY_EIGHT_QUEST_ID
    if int(shell_id) == BROUG_KILLING_INTENT_DOMAIN_SHELL_ID:
        return BROUG_ROOM_QUEST_ID
    if int(shell_id) == BROUG_VITALITY_DRAIN_SHELL_ID:
        return BROUG_DOMAIN_UNSEALED_QUEST_ID
    raise ValueError(f"Unsupported Broug Empty Court reward shell: {shell_id}")


def _grant_metadata(shell_id: int) -> dict[str, object]:
    metadata_by_shell = {
        BROUG_QI_REVERSAL_SHELL_ID: {
            "capability": "qi_reversal",
            "behavior_kind": "broug_qi_reversal_v1",
            "counter_key": "qi_reversal_cleanse",
        },
        BROUG_PREDATORS_STRIKE_SHELL_ID: {
            "capability": "predators_strike",
            "behavior_kind": "broug_predators_strike_v1",
            "counter_key": "predator_heal",
        },
        BROUG_KILLING_INTENT_DOMAIN_SHELL_ID: {
            "capability": "killing_intent_domain",
            "behavior_kind": "broug_killing_intent_domain_v1",
            "counter_key": "domain_pulse",
        },
        BROUG_VITALITY_DRAIN_SHELL_ID: {
            "capability": "vitality_drain",
            "behavior_kind": "broug_vitality_drain_v1",
            "counter_key": "vitality_kill",
        },
    }
    payload = dict(metadata_by_shell.get(int(shell_id), {"capability": "unknown"}))
    payload["arc_key"] = BROUG_EMPTY_COURT_ARC_KEY
    payload["stage_key"] = BROUG_EMPTY_COURT_STAGE_KEY
    payload["status"] = "PARTIAL"
    return payload


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
