from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.spells.broug_empty_court import BROUG_ASH_WORN_TRACK_GO
from wm.spells.broug_empty_court import BROUG_ASH_HUSHED_BEAR_ENTRY
from wm.spells.broug_empty_court import BROUG_ASH_HUSHED_BOAR_ENTRY
from wm.spells.broug_empty_court import BROUG_ASH_HUSHED_WOLF_ENTRY
from wm.spells.broug_empty_court import BROUG_BOLTED_CELLAR_HATCH_GO
from wm.spells.broug_empty_court import BROUG_BOUNTY_CREDIT_ENTRY
from wm.spells.broug_empty_court import BROUG_COURT_REMNANT_ENTRY
from wm.spells.broug_empty_court import BROUG_DOMAIN_UNSEALED_QUEST_ID
from wm.spells.broug_empty_court import BROUG_EMPTY_COURT_ARC_KEY
from wm.spells.broug_empty_court import BROUG_EMPTY_COURT_VISIBLE_SHELL_IDS
from wm.spells.broug_empty_court import BROUG_HAL_MORROW_ENTRY
from wm.spells.broug_empty_court import BROUG_NINETY_EIGHT_QUEST_ID
from wm.spells.broug_empty_court import BROUG_OATH_CREDIT_ENTRY
from wm.spells.broug_empty_court import BROUG_QI_REVERSAL_SHELL_ID
from wm.spells.broug_empty_court import BROUG_ROOM_CREDIT_ENTRY
from wm.spells.broug_empty_court import BROUG_ROOM_QUEST_ID
from wm.spells.broug_empty_court import BROUG_SILENT_HALL_FIRST_ENTRY
from wm.spells.broug_empty_court import BROUG_SILENT_HALL_LAST_ENTRY
from wm.spells.broug_empty_court import BROUG_STILLING_QUEST_ID
from wm.spells.broug_empty_court import BROUG_STILLNESS_CREDIT_ENTRY
from wm.spells.broug_empty_court import BROUG_WEIGHT_QUEST_ID
from wm.spells.broug_empty_court import BROUG_WEI_JIN_ENTRY
from wm.spells.broug_lightness import BROUG_CLOUD_STEP_CREDIT_ENTRY
from wm.spells.broug_lightness import BROUG_CLOUD_STEP_SHELL_ID
from wm.spells.broug_lightness import BROUG_LIGHTNESS_ARC_KEY
from wm.spells.broug_lightness import BROUG_LIGHTNESS_VISIBLE_SHELL_IDS
from wm.spells.broug_lightness import BROUG_MARKED_MERIDIAN_SHELL_ID
from wm.spells.broug_lightness import BROUG_NO_FOOTFALL_QUEST_ID
from wm.spells.broug_lightness import BROUG_PARALLEL_ENERGY_SURGE_SELF_AURA_SHELL_ID
from wm.spells.broug_lightness import BROUG_SILENT_MERIDIAN_SHELL_ID
from wm.spells.broug_lightness import BROUG_STEPS_QUEST_ID
from wm.spells.broug_lightness import BROUG_STEPS_TARGET_COUNT
from wm.spells.broug_lightness import BROUG_STEPS_TARGET_ENTRY
from wm.spells.shell_bank import load_spell_shell_bank


REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class ContentPreflightIssue:
    severity: str
    code: str
    message: str
    subject: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ContentPreflightReport:
    arc_key: str
    status: str
    checked: list[str]
    issues: list[ContentPreflightIssue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "arc_key": self.arc_key,
            "status": self.status,
            "checked": self.checked,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def preflight_arc(
    *,
    arc_key: str,
    player_guid: int = 5405,
    live_db: bool = False,
    client: MysqlCliClient | None = None,
    settings: Settings | None = None,
) -> ContentPreflightReport:
    if arc_key == BROUG_LIGHTNESS_ARC_KEY:
        report = _preflight_broug_lightness(player_guid=player_guid)
    elif arc_key == BROUG_EMPTY_COURT_ARC_KEY:
        report = _preflight_broug_empty_court(player_guid=player_guid)
    else:
        return ContentPreflightReport(
            arc_key=arc_key,
            status="UNKNOWN",
            checked=[],
            issues=[
                _issue(
                    "error",
                    "unknown_arc",
                    f"No content preflight profile exists for arc `{arc_key}`.",
                    arc_key,
                )
            ],
        )

    if live_db:
        if client is None or settings is None:
            client = MysqlCliClient()
            settings = Settings.from_env()
        report.issues.extend(_run_live_db_checks(arc_key=arc_key, player_guid=player_guid, client=client, settings=settings))
        report.checked.append("live_db")

    report.status = _status_from_issues(report.issues)
    return report


def _preflight_broug_lightness(*, player_guid: int) -> ContentPreflightReport:
    sql_path = REPO_ROOT / "native_modules/mod-wm-spells/data/sql/world/updates/2026_05_02_00_wm_spell_broug_lightness_assassin.sql"
    sql = _read_text(sql_path)
    registry = _load_registry()
    issues: list[ContentPreflightIssue] = []
    checked = ["source_sql", "registry", "shell_bank", "quest_target_static"]

    issues.extend(_check_registry_claims(
        registry,
        player_guid=player_guid,
        claims=[
            ("quest", BROUG_STEPS_QUEST_ID),
            ("quest", BROUG_NO_FOOTFALL_QUEST_ID),
            ("spell", BROUG_CLOUD_STEP_SHELL_ID),
            ("spell", BROUG_MARKED_MERIDIAN_SHELL_ID),
            ("spell", BROUG_SILENT_MERIDIAN_SHELL_ID),
            ("creature_template", BROUG_CLOUD_STEP_CREDIT_ENTRY),
        ],
    ))
    issues.extend(_check_shell_bank(BROUG_LIGHTNESS_VISIBLE_SHELL_IDS))
    issues.extend(_require_tokens(
        sql,
        subject=str(sql_path),
        tokens=[
            "Syndicate Watchmen",
            "@wm_broug_syndicate_watchman_entry := 2261",
            "FactionGroup 8, EnemyGroup 1",
            "RewardDisplaySpell",
            "spell_wm_shell_dispatch",
            "spell_cooldown_overrides",
            "'min_range_yards', 0.0",
            "'kill_window_ms', 10000",
            "'cooldown_reduction_ms', 6000",
        ],
    ))
    issues.extend(_forbid_tokens(
        sql,
        subject=str(sql_path),
        tokens=["Defias Profiteer", "@wm_broug_defias_profiteer_entry", "1669", "playercreateinfo", "mod_learnspells"],
    ))
    if BROUG_STEPS_TARGET_COUNT > 1 and "FactionGroup 8, EnemyGroup 1" not in sql:
        issues.append(_issue("error", "missing_hostility_proof", "Kill target count requires explicit hostility proof.", str(BROUG_STEPS_TARGET_ENTRY)))
    return ContentPreflightReport(
        arc_key=BROUG_LIGHTNESS_ARC_KEY,
        status=_status_from_issues(issues),
        checked=checked,
        issues=issues,
    )


def _preflight_broug_empty_court(*, player_guid: int) -> ContentPreflightReport:
    sql_path = REPO_ROOT / "native_modules/mod-wm-spells/data/sql/world/updates/2026_05_02_01_wm_spell_broug_empty_court_v2.sql"
    sql = _read_text(sql_path)
    registry = _load_registry()
    issues: list[ContentPreflightIssue] = []
    checked = ["source_sql", "registry", "shell_bank", "quest_text_static", "custom_actor_static", "gameobject_static"]

    issues.extend(_check_registry_claims(
        registry,
        player_guid=player_guid,
        claims=[
            ("quest", BROUG_WEIGHT_QUEST_ID),
            ("quest", BROUG_STILLING_QUEST_ID),
            ("quest", BROUG_NINETY_EIGHT_QUEST_ID),
            ("quest", BROUG_ROOM_QUEST_ID),
            ("quest", BROUG_DOMAIN_UNSEALED_QUEST_ID),
            ("spell", BROUG_QI_REVERSAL_SHELL_ID),
            *[("creature_template", entry) for entry in _empty_court_custom_creature_entries()],
            ("creature_template", BROUG_STILLNESS_CREDIT_ENTRY),
            ("creature_template", BROUG_BOUNTY_CREDIT_ENTRY),
            ("creature_template", BROUG_ROOM_CREDIT_ENTRY),
            ("creature_template", BROUG_OATH_CREDIT_ENTRY),
            ("gameobject_template", BROUG_ASH_WORN_TRACK_GO),
            ("gameobject_template", BROUG_BOLTED_CELLAR_HATCH_GO),
        ],
    ))
    issues.extend(_check_shell_bank(BROUG_EMPTY_COURT_VISIBLE_SHELL_IDS))
    issues.extend(_require_tokens(
        sql,
        subject=str(sql_path),
        tokens=[
            "creature_template_model",
            "gameobject_template",
            "8298",
            "8413",
            "Data1",
            "Data3",
            "Go to",
            "-10752",
            "-11095",
            "RewardDisplaySpell",
            "spell_wm_shell_dispatch",
            "spell_cooldown_overrides",
            "'purged_duration_ms', 30000",
            "'base_killing_intent_duration_ms', 15000",
        ],
    ))
    issues.extend(_forbid_tokens(
        sql,
        subject=str(sql_path),
        tokens=["920106", "910014", "946606", "946604", "946801", "playercreateinfo", "mod_learnspells"],
    ))
    for quest_id in (BROUG_WEIGHT_QUEST_ID, BROUG_STILLING_QUEST_ID, BROUG_NINETY_EIGHT_QUEST_ID, BROUG_ROOM_QUEST_ID, BROUG_DOMAIN_UNSEALED_QUEST_ID):
        if str(quest_id) not in sql:
            issues.append(_issue("error", "missing_quest", "Quest ID missing from source SQL.", str(quest_id)))
    return ContentPreflightReport(
        arc_key=BROUG_EMPTY_COURT_ARC_KEY,
        status=_status_from_issues(issues),
        checked=checked,
        issues=issues,
    )


def _run_live_db_checks(*, arc_key: str, player_guid: int, client: MysqlCliClient, settings: Settings) -> list[ContentPreflightIssue]:
    issues: list[ContentPreflightIssue] = []
    if arc_key == BROUG_LIGHTNESS_ARC_KEY:
        rows = _query_world(
            client,
            settings,
            "SELECT COUNT(*) AS SpawnCount FROM creature WHERE map = 0 AND id1 = 2261;",
        )
        spawn_count = int(rows[0].get("SpawnCount", 0)) if rows else 0
        if spawn_count < BROUG_STEPS_TARGET_COUNT:
            issues.append(
                _issue(
                    "error",
                    "insufficient_live_spawns",
                    f"Syndicate Watchman requires {BROUG_STEPS_TARGET_COUNT} kills but live DB has {spawn_count} map-0 spawns.",
                    str(BROUG_STEPS_TARGET_ENTRY),
                )
            )
    if arc_key == BROUG_EMPTY_COURT_ARC_KEY:
        for entry in _empty_court_custom_creature_entries():
            rows = _query_world(
                client,
                settings,
                f"SELECT COUNT(*) AS ModelRows FROM creature_template_model WHERE CreatureID = {int(entry)};",
            )
            if not rows or int(rows[0].get("ModelRows", 0)) <= 0:
                issues.append(_issue("error", "missing_live_model_row", "Live DB custom creature lacks model row.", str(entry)))
        for go_entry in (BROUG_ASH_WORN_TRACK_GO, BROUG_BOLTED_CELLAR_HATCH_GO):
            rows = _query_world(
                client,
                settings,
                f"SELECT entry, displayId, type, Data1, Data3 FROM gameobject_template WHERE entry = {int(go_entry)};",
            )
            if not rows:
                issues.append(_issue("error", "missing_live_go_template", "Live DB missing gameobject_template row.", str(go_entry)))
                continue
            row = rows[0]
            if int(row.get("displayId", 0)) <= 0:
                issues.append(_issue("error", "invisible_live_go", "Live DB gameobject displayId must be nonzero.", str(go_entry)))
            if int(row.get("type", 0)) == 10 and int(row.get("Data1", 0)) <= 0:
                issues.append(_issue("error", "clickable_go_missing_quest", "GOOBER gameobject must bind Data1 quest.", str(go_entry)))
    return issues


def _empty_court_custom_creature_entries() -> tuple[int, ...]:
    return (
        BROUG_WEI_JIN_ENTRY,
        BROUG_ASH_HUSHED_WOLF_ENTRY,
        BROUG_ASH_HUSHED_BOAR_ENTRY,
        BROUG_ASH_HUSHED_BEAR_ENTRY,
        BROUG_HAL_MORROW_ENTRY,
        *range(BROUG_SILENT_HALL_FIRST_ENTRY, BROUG_SILENT_HALL_LAST_ENTRY + 1),
        BROUG_COURT_REMNANT_ENTRY,
    )


def _query_world(client: MysqlCliClient, settings: Settings, sql: str) -> list[dict[str, Any]]:
    return client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql=sql,
    )


def _check_shell_bank(spell_ids: tuple[int, ...]) -> list[ContentPreflightIssue]:
    bank = load_spell_shell_bank()
    issues: list[ContentPreflightIssue] = []
    for spell_id in spell_ids:
        shell = bank.shell_by_spell_id(spell_id)
        if shell is None:
            issues.append(_issue("error", "missing_shell_bank_row", "Shell ID missing from shell bank.", str(spell_id)))
            continue
        if not shell.tooltip:
            issues.append(_issue("error", "missing_shell_tooltip", "Shell bank row must include tooltip.", str(spell_id)))
        if not shell.client_presentation or "spell_icon_id" not in shell.client_presentation:
            issues.append(_issue("error", "missing_shell_icon", "Shell bank row must include spell_icon_id.", str(spell_id)))
    return issues


def _check_registry_claims(registry: dict[str, Any], *, player_guid: int, claims: list[tuple[str, int]]) -> list[ContentPreflightIssue]:
    claim_map = {(str(entry.get("namespace")), int(entry.get("id"))): entry for entry in registry.get("claims", [])}
    issues: list[ContentPreflightIssue] = []
    for namespace, id_ in claims:
        entry = claim_map.get((namespace, int(id_)))
        if entry is None:
            issues.append(_issue("error", "missing_registry_claim", "ID is not claimed in custom_id_registry.json.", f"{namespace}:{id_}"))
            continue
        if entry.get("status") not in {"PARTIAL", "WORKING"}:
            issues.append(_issue("error", "registry_claim_not_active", f"ID claim status is {entry.get('status')!r}.", f"{namespace}:{id_}"))
        if entry.get("player_guid_scope") not in (None, player_guid):
            issues.append(
                _issue(
                    "error",
                    "registry_scope_mismatch",
                    f"Expected player_guid_scope {player_guid}, found {entry.get('player_guid_scope')!r}.",
                    f"{namespace}:{id_}",
                )
            )
    return issues


def _require_tokens(source: str, *, subject: str, tokens: list[str]) -> list[ContentPreflightIssue]:
    return [
        _issue("error", "missing_required_token", f"Required token `{token}` missing.", subject)
        for token in tokens
        if token not in source
    ]


def _forbid_tokens(source: str, *, subject: str, tokens: list[str]) -> list[ContentPreflightIssue]:
    lowered = source.lower()
    return [
        _issue("error", "forbidden_token_present", f"Forbidden token `{token}` is present.", subject)
        for token in tokens
        if token.lower() in lowered
    ]


def _load_registry() -> dict[str, Any]:
    return json.loads((REPO_ROOT / "data/specs/custom_id_registry.json").read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _issue(severity: str, code: str, message: str, subject: str) -> ContentPreflightIssue:
    return ContentPreflightIssue(severity=severity, code=code, message=message, subject=subject)


def _status_from_issues(issues: list[ContentPreflightIssue]) -> str:
    if any(issue.severity == "error" for issue in issues):
        return "BROKEN"
    if any(issue.severity == "warning" for issue in issues):
        return "PARTIAL"
    return "WORKING"


def render_summary(report: ContentPreflightReport) -> str:
    lines = [f"arc={report.arc_key}", f"status={report.status}", f"checked={','.join(report.checked)}"]
    for issue in report.issues:
        lines.append(f"{issue.severity} {issue.code} {issue.subject}: {issue.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight player-facing WM content before BridgeLab deploy.")
    parser.add_argument("--arc", required=True)
    parser.add_argument("--player-guid", type=int, default=5405)
    parser.add_argument("--live-db", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    report = preflight_arc(arc_key=args.arc, player_guid=args.player_guid, live_db=args.live_db)
    if args.summary:
        print(render_summary(report))
    else:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.status != "BROKEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
