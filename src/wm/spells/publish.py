from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import subprocess
import sys
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.spells.models import ManagedSpellDraft, ManagedSpellLink, ManagedSpellProcRule
from wm.spells.validator import validate_managed_spell_draft

REQUIRED_TABLES = {"wm_publish_log", "wm_rollback_snapshot"}
OPTIONAL_TABLES = {"wm_reserved_slot", "spell_linked_spell", "spell_proc"}

LINKED_TRIGGER_CANDIDATES = ["spell_trigger", "trigger_spell_id"]
LINKED_EFFECT_CANDIDATES = ["spell_effect", "effect_spell_id"]
LINKED_TYPE_CANDIDATES = ["type", "link_type"]
LINKED_COMMENT_CANDIDATES = ["comment", "comments"]

PROC_COLUMN_CANDIDATES: dict[str, list[str]] = {
    "spell_id": ["SpellId", "spell_id", "spellid"],
    "school_mask": ["SchoolMask", "school_mask", "schoolmask"],
    "spell_family_name": ["SpellFamilyName", "spell_family_name", "spellfamilyname"],
    "spell_family_mask_0": ["SpellFamilyMask0", "spell_family_mask_0", "spellfamilymask0"],
    "spell_family_mask_1": ["SpellFamilyMask1", "spell_family_mask_1", "spellfamilymask1"],
    "spell_family_mask_2": ["SpellFamilyMask2", "spell_family_mask_2", "spellfamilymask2"],
    "proc_flags": ["ProcFlags", "proc_flags", "procflags"],
    "spell_type_mask": ["SpellTypeMask", "spell_type_mask", "spelltypemask"],
    "spell_phase_mask": ["SpellPhaseMask", "spell_phase_mask", "spellphasemask"],
    "hit_mask": ["HitMask", "hit_mask", "hitmask"],
    "attributes_mask": ["AttributesMask", "attributes_mask", "attributesmask"],
    "disable_effect_mask": ["DisableEffectsMask", "disable_effect_mask", "disableeffectmask", "disableeffectsmask"],
    "procs_per_minute": ["ProcsPerMinute", "procs_per_minute", "procsperminute"],
    "chance": ["Chance", "chance"],
    "cooldown": ["Cooldown", "cooldown"],
    "charges": ["Charges", "charges"],
}


@dataclass(slots=True)
class PublishIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SpellPreflightReport:
    spell_entry: int
    issues: list[PublishIssue] = field(default_factory=list)
    reserved_slot: dict[str, Any] | None = None
    detected_tables: dict[str, bool] = field(default_factory=dict)
    linked_columns: dict[str, str] = field(default_factory=dict)
    proc_columns: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spell_entry": self.spell_entry,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
            "reserved_slot": self.reserved_slot,
            "detected_tables": self.detected_tables,
            "linked_columns": self.linked_columns,
            "proc_columns": self.proc_columns,
        }


@dataclass(slots=True)
class SpellSqlPlan:
    spell_entry: int
    statements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SpellPublishResult:
    mode: str
    draft: dict[str, Any]
    validation: dict[str, Any]
    preflight: dict[str, Any]
    snapshot_preview: dict[str, Any]
    sql_plan: dict[str, Any]
    applied: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpellPublisher:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def preflight(self, draft: ManagedSpellDraft) -> SpellPreflightReport:
        report = SpellPreflightReport(spell_entry=draft.spell_entry)
        table_presence = self._table_presence(REQUIRED_TABLES | OPTIONAL_TABLES)
        report.detected_tables = table_presence

        for table_name in sorted(REQUIRED_TABLES):
            if not table_presence.get(table_name, False):
                report.issues.append(
                    PublishIssue(path=f"table.{table_name}", message=f"Required table `{table_name}` is missing.")
                )

        if draft.linked_spells:
            if not table_presence.get("spell_linked_spell", False):
                report.issues.append(
                    PublishIssue(path="table.spell_linked_spell", message="spell_linked_spell is required for linked_spells.")
                )
            else:
                columns = self._table_columns("spell_linked_spell")
                report.linked_columns = {
                    "trigger": _resolve_column(columns, LINKED_TRIGGER_CANDIDATES) or "",
                    "effect": _resolve_column(columns, LINKED_EFFECT_CANDIDATES) or "",
                    "type": _resolve_column(columns, LINKED_TYPE_CANDIDATES) or "",
                    "comment": _resolve_column(columns, LINKED_COMMENT_CANDIDATES) or "",
                }
                for key in ["trigger", "effect"]:
                    if not report.linked_columns.get(key):
                        report.issues.append(
                            PublishIssue(
                                path=f"spell_linked_spell.{key}",
                                message=f"Could not find a supported `{key}` column in spell_linked_spell.",
                            )
                        )
                if any(link.comment for link in draft.linked_spells) and not report.linked_columns.get("comment"):
                    report.issues.append(
                        PublishIssue(
                            path="spell_linked_spell.comment",
                            message="linked spell comments were requested but no comment column exists.",
                            severity="warning",
                        )
                    )

        if draft.proc_rules:
            if not table_presence.get("spell_proc", False):
                report.issues.append(PublishIssue(path="table.spell_proc", message="spell_proc is required for proc_rules."))
            else:
                columns = self._table_columns("spell_proc")
                report.proc_columns = {
                    logical: (_resolve_column(columns, candidates) or "")
                    for logical, candidates in PROC_COLUMN_CANDIDATES.items()
                }
                if not report.proc_columns.get("spell_id"):
                    report.issues.append(
                        PublishIssue(
                            path="spell_proc.spell_id",
                            message="Could not find a supported spell id column in spell_proc.",
                        )
                    )

        if table_presence.get("wm_reserved_slot", False):
            slot_rows = self._query_world(
                "SELECT EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON "
                "FROM wm_reserved_slot "
                f"WHERE EntityType = 'spell' AND ReservedID = {int(draft.spell_entry)}"
            )
            if slot_rows:
                report.reserved_slot = slot_rows[0]
                slot_status = str(slot_rows[0].get("SlotStatus") or "")
                if slot_status not in {"staged", "active"}:
                    report.issues.append(
                        PublishIssue(
                            path="reserved_slot.status",
                            message=(
                                f"Reserved slot for spell {draft.spell_entry} exists but has status `{slot_status}`; expected `staged` or `active`."
                            ),
                            severity="warning",
                        )
                    )
            else:
                report.issues.append(
                    PublishIssue(
                        path="reserved_slot",
                        message=(
                            f"No wm_reserved_slot row exists for spell {draft.spell_entry}. Publishing can continue, but managed spell-slot tracking is not wired yet."
                        ),
                        severity="warning",
                    )
                )
        else:
            report.issues.append(
                PublishIssue(
                    path="table.wm_reserved_slot",
                    message="Optional table `wm_reserved_slot` is missing; reserved spell-slot tracking is disabled.",
                    severity="warning",
                )
            )
        return report

    def capture_snapshot_preview(self, draft: ManagedSpellDraft, preflight: SpellPreflightReport) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if draft.linked_spells and preflight.linked_columns.get("trigger") and preflight.linked_columns.get("effect"):
            trigger_col = preflight.linked_columns["trigger"]
            effect_col = preflight.linked_columns["effect"]
            payload["spell_linked_spell"] = self._query_world(
                f"SELECT * FROM `spell_linked_spell` WHERE `{trigger_col}` = {int(draft.spell_entry)} OR `{effect_col}` = {int(draft.spell_entry)}"
            )
        else:
            payload["spell_linked_spell"] = []
        if draft.proc_rules and preflight.proc_columns.get("spell_id"):
            spell_id_col = preflight.proc_columns["spell_id"]
            payload["spell_proc"] = self._query_world(
                f"SELECT * FROM `spell_proc` WHERE `{spell_id_col}` = {int(draft.spell_entry)}"
            )
        else:
            payload["spell_proc"] = []
        return payload

    def build_sql_plan(self, draft: ManagedSpellDraft, preflight: SpellPreflightReport) -> SpellSqlPlan:
        statements: list[str] = [f"-- WM managed spell slot {draft.spell_entry}"]

        if draft.linked_spells and preflight.linked_columns.get("trigger") and preflight.linked_columns.get("effect"):
            trigger_col = preflight.linked_columns["trigger"]
            effect_col = preflight.linked_columns["effect"]
            statements.append(
                f"DELETE FROM `spell_linked_spell` WHERE `{trigger_col}` = {int(draft.spell_entry)} OR `{effect_col}` = {int(draft.spell_entry)};"
            )
            for link in draft.linked_spells:
                row: dict[str, Any] = {
                    trigger_col: int(link.trigger_spell_id),
                    effect_col: int(link.effect_spell_id),
                }
                type_col = preflight.linked_columns.get("type")
                comment_col = preflight.linked_columns.get("comment")
                if type_col:
                    row[type_col] = int(link.link_type)
                if comment_col and link.comment is not None:
                    row[comment_col] = str(link.comment)
                statements.append(_insert_sql("spell_linked_spell", row))

        if draft.proc_rules and preflight.proc_columns.get("spell_id"):
            spell_id_col = preflight.proc_columns["spell_id"]
            statements.append(f"DELETE FROM `spell_proc` WHERE `{spell_id_col}` = {int(draft.spell_entry)};")
            for rule in draft.proc_rules:
                row = _proc_rule_row(rule, preflight.proc_columns)
                statements.append(_insert_sql("spell_proc", row))

        return SpellSqlPlan(spell_entry=draft.spell_entry, statements=statements)

    def publish(self, *, draft: ManagedSpellDraft, mode: str) -> SpellPublishResult:
        validation = validate_managed_spell_draft(draft)
        preflight = self.preflight(draft)
        snapshot_preview = self.capture_snapshot_preview(draft, preflight)
        sql_plan = self.build_sql_plan(draft, preflight) if validation.ok and preflight.ok else SpellSqlPlan(spell_entry=draft.spell_entry)

        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported publish mode: {mode}")

        if mode == "dry-run" or not validation.ok or not preflight.ok:
            return SpellPublishResult(
                mode=mode,
                draft=draft.to_dict(),
                validation=validation.to_dict(),
                preflight=preflight.to_dict(),
                snapshot_preview=snapshot_preview,
                sql_plan=sql_plan.to_dict(),
                applied=False,
            )

        snapshot_json = json.dumps(snapshot_preview, ensure_ascii=False).replace("'", "''")
        plan_statements = [stmt for stmt in sql_plan.statements if stmt.strip() and not stmt.strip().startswith("--")]
        try:
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('spell', {int(draft.spell_entry)}, 'publish', 'started', 'Managed spell publish started by wm.spells.publish')"
            )
            self._execute_world(
                "INSERT INTO wm_rollback_snapshot (artifact_type, artifact_entry, snapshot_json) VALUES "
                f"('spell', {int(draft.spell_entry)}, '{snapshot_json}')"
            )
            for statement in plan_statements:
                self._execute_world(statement)
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('spell', {int(draft.spell_entry)}, 'publish', 'success', 'Managed spell publish completed successfully')"
            )
            if preflight.reserved_slot is not None:
                self._execute_world(
                    "UPDATE wm_reserved_slot SET SlotStatus = 'active' "
                    "WHERE EntityType = 'spell' "
                    f"AND ReservedID = {int(draft.spell_entry)}"
                )
        except MysqlCliError as exc:
            self._log_failure(draft.spell_entry, str(exc))
            raise

        return SpellPublishResult(
            mode=mode,
            draft=draft.to_dict(),
            validation=validation.to_dict(),
            preflight=preflight.to_dict(),
            snapshot_preview=snapshot_preview,
            sql_plan=sql_plan.to_dict(),
            applied=True,
        )

    def _table_presence(self, table_names: set[str]) -> dict[str, bool]:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database="information_schema",
            sql=(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.world_db_name)} "
                f"AND TABLE_NAME IN ({_sql_list(table_names)})"
            ),
        )
        present = {str(row['TABLE_NAME']): True for row in rows}
        return {name: present.get(name, False) for name in table_names}

    def _table_columns(self, table_name: str) -> set[str]:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database="information_schema",
            sql=(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.world_db_name)} AND TABLE_NAME = {_sql_string(table_name)}"
            ),
        )
        return {str(row['COLUMN_NAME']) for row in rows}

    def _query_world(self, sql: str) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=sql,
        )

    def _execute_world(self, sql: str) -> None:
        command = [
            str(self.client.mysql_bin_path),
            f"--host={self.settings.world_db_host}",
            f"--port={self.settings.world_db_port}",
            f"--user={self.settings.world_db_user}",
            f"--password={self.settings.world_db_password}",
            f"--database={self.settings.world_db_name}",
            f"--execute={sql}",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise MysqlCliError(completed.stderr.strip() or completed.stdout.strip() or "mysql execute failed")

    def _log_failure(self, spell_entry: int, error_message: str) -> None:
        safe = error_message.replace("'", "''")
        try:
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('spell', {int(spell_entry)}, 'publish', 'failed', '{safe}')"
            )
        except MysqlCliError:
            pass


def _normalize(name: str) -> str:
    return name.replace("_", "").lower()


def _resolve_column(columns: set[str], candidates: list[str]) -> str | None:
    normalized = {_normalize(column): column for column in columns}
    for candidate in candidates:
        found = normalized.get(_normalize(candidate))
        if found is not None:
            return found
    return None


def _proc_rule_row(rule: ManagedSpellProcRule, proc_columns: dict[str, str]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    mapping = {
        "spell_id": rule.spell_id,
        "school_mask": rule.school_mask,
        "spell_family_name": rule.spell_family_name,
        "spell_family_mask_0": rule.spell_family_mask_0,
        "spell_family_mask_1": rule.spell_family_mask_1,
        "spell_family_mask_2": rule.spell_family_mask_2,
        "proc_flags": rule.proc_flags,
        "spell_type_mask": rule.spell_type_mask,
        "spell_phase_mask": rule.spell_phase_mask,
        "hit_mask": rule.hit_mask,
        "attributes_mask": rule.attributes_mask,
        "disable_effect_mask": rule.disable_effect_mask,
        "procs_per_minute": rule.procs_per_minute,
        "chance": rule.chance,
        "cooldown": rule.cooldown,
        "charges": rule.charges,
    }
    for logical, value in mapping.items():
        actual = proc_columns.get(logical)
        if actual:
            row[actual] = value
    return row


def _insert_sql(table_name: str, row: dict[str, Any]) -> str:
    columns_sql = ", ".join(f"`{column}`" for column in row.keys())
    values_sql = ", ".join(_sql_value(value) for value in row.values())
    return f"INSERT INTO `{table_name}` ({columns_sql}) VALUES ({values_sql});"


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_list(values: set[str]) -> str:
    return ", ".join(_sql_string(value) for value in sorted(values))


def _sql_value(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    return _sql_string(str(value))


def load_managed_spell_draft(path: str | Path) -> ManagedSpellDraft:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("draft"), dict):
        raw = raw["draft"]
    if not isinstance(raw, dict):
        raise ValueError("Managed spell draft JSON must be an object.")
    return ManagedSpellDraft(
        spell_entry=int(raw["spell_entry"]),
        slot_kind=str(raw["slot_kind"]),
        name=str(raw["name"]),
        base_visible_spell_id=(int(raw["base_visible_spell_id"]) if raw.get("base_visible_spell_id") not in (None, "") else None),
        helper_spell_id=(int(raw["helper_spell_id"]) if raw.get("helper_spell_id") not in (None, "") else None),
        trigger_item_entry=(int(raw["trigger_item_entry"]) if raw.get("trigger_item_entry") not in (None, "") else None),
        aura_description=(str(raw["aura_description"]) if raw.get("aura_description") not in (None, "") else None),
        proc_rules=[ManagedSpellProcRule(**{k: v for k, v in item.items()}) for item in raw.get("proc_rules", [])],
        linked_spells=[ManagedSpellLink(**{k: v for k, v in item.items()}) for item in raw.get("linked_spells", [])],
        tags=[str(value) for value in raw.get("tags", [])],
    )


def _demo_draft() -> ManagedSpellDraft:
    return ManagedSpellDraft(
        spell_entry=940000,
        slot_kind="item_trigger_slot",
        name="WM Prototype Item Trigger",
        helper_spell_id=133,
        trigger_item_entry=910000,
        aura_description="Prototype managed trigger used by a WM item reward.",
        proc_rules=[ManagedSpellProcRule(spell_id=940000, chance=25.0)],
        linked_spells=[ManagedSpellLink(trigger_spell_id=940000, effect_spell_id=133, link_type=0, comment="Prototype trigger link")],
        tags=["wm_generated", "spell_slot", "item_trigger"],
    )


def _render_summary(result: SpellPublishResult) -> str:
    preflight = result.preflight
    validation = result.validation
    lines = [
        f"mode: {result.mode}",
        f"applied: {str(bool(result.applied)).lower()}",
        f"validation.ok: {str(bool(validation.get('ok', False))).lower()}",
        f"preflight.ok: {str(bool(preflight.get('ok', False))).lower()}",
        f"detected_tables: {', '.join(sorted(k for k, v in (preflight.get('detected_tables') or {}).items() if v)) or '(none)'}",
        "",
        "issues:",
    ]
    issues = list(validation.get("issues", [])) + list(preflight.get("issues", []))
    if not issues:
        lines.append("- none")
    else:
        for issue in issues:
            lines.append(f"- {issue.get('path')} | {issue.get('severity')} | {issue.get('message')}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.spells.publish")
    parser.add_argument("--draft-json", type=Path)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.demo and args.draft_json is None:
        raise SystemExit("Provide --draft-json PATH or use --demo.")
    draft = _demo_draft() if args.demo else load_managed_spell_draft(args.draft_json)
    settings = Settings.from_env()
    client = MysqlCliClient()
    publisher = SpellPublisher(client=client, settings=settings)
    result = publisher.publish(draft=draft, mode=args.mode)
    raw = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    print(_render_summary(result))
    if args.output_json is not None:
        print("")
        print(f"output_json: {args.output_json}")
    return 0 if bool(result.validation.get("ok", False) and result.preflight.get("ok", False)) else 2


if __name__ == "__main__":
    sys.exit(main())
