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
from wm.items.compiler import ItemSqlPlan, compile_managed_item_sql_plan
from wm.items.models import ItemSpellLine, ItemStatLine, ManagedItemDraft
from wm.items.validator import validate_managed_item_draft


REQUIRED_TABLES = {
    "item_template",
    "wm_publish_log",
    "wm_rollback_snapshot",
}

OPTIONAL_TABLES = {"wm_reserved_slot"}


@dataclass(slots=True)
class PublishIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ItemPreflightReport:
    item_entry: int
    issues: list[PublishIssue] = field(default_factory=list)
    existing_item_rows: list[dict[str, Any]] = field(default_factory=list)
    base_item_rows: list[dict[str, Any]] = field(default_factory=list)
    reserved_slot: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_entry": self.item_entry,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
            "existing_item_rows": self.existing_item_rows,
            "base_item_rows": self.base_item_rows,
            "reserved_slot": self.reserved_slot,
        }


@dataclass(slots=True)
class ItemPublishResult:
    mode: str
    draft: dict[str, Any]
    validation: dict[str, Any]
    preflight: dict[str, Any]
    snapshot_preview: dict[str, Any]
    sql_plan: dict[str, Any]
    final_row_preview: dict[str, Any]
    applied: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ItemPublisher:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def preflight(self, draft: ManagedItemDraft) -> ItemPreflightReport:
        report = ItemPreflightReport(item_entry=draft.item_entry)

        table_presence = self._table_presence(REQUIRED_TABLES | OPTIONAL_TABLES)
        for table_name in sorted(REQUIRED_TABLES):
            if not table_presence.get(table_name, False):
                report.issues.append(
                    PublishIssue(
                        path=f"table.{table_name}",
                        message=f"Required table `{table_name}` is missing from `{self.settings.world_db_name}`.",
                    )
                )

        if not table_presence.get("item_template", False):
            return report

        available_columns = self._item_template_columns()
        report.existing_item_rows = self._query_world(
            "SELECT entry, name, description FROM item_template "
            f"WHERE entry = {int(draft.item_entry)}"
        )
        report.base_item_rows = self._query_world(
            "SELECT entry, name, description FROM item_template "
            f"WHERE entry = {int(draft.base_item_entry)}"
        )
        if not report.base_item_rows:
            report.issues.append(
                PublishIssue(
                    path="base_item_entry",
                    message=f"Base item entry {draft.base_item_entry} does not exist in item_template.",
                )
            )
        if report.existing_item_rows:
            report.issues.append(
                PublishIssue(
                    path="item_entry",
                    message="Managed item slot already exists and will be replaced if apply mode is used.",
                    severity="warning",
                )
            )

        if "entry" not in available_columns_lower(available_columns):
            report.issues.append(
                PublishIssue(path="item_template.entry", message="item_template.entry is missing.")
            )
        if "name" not in available_columns_lower(available_columns):
            report.issues.append(
                PublishIssue(path="item_template.name", message="item_template.name is missing.")
            )

        report.issues.extend(self._compatibility_issues(draft=draft, available_columns=available_columns))

        if table_presence.get("wm_reserved_slot", False):
            slot_rows = self._query_world(
                "SELECT EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON "
                "FROM wm_reserved_slot "
                f"WHERE EntityType = 'item' AND ReservedID = {int(draft.item_entry)}"
            )
            if slot_rows:
                report.reserved_slot = slot_rows[0]
                slot_status = str(slot_rows[0].get("SlotStatus") or "")
                if slot_status not in {"staged", "active"}:
                    report.issues.append(
                        PublishIssue(
                            path="reserved_slot.status",
                            message=(
                                f"Reserved slot for item {draft.item_entry} exists but has status `{slot_status}`; "
                                "expected `staged` or `active`."
                            ),
                            severity="warning",
                        )
                    )
            else:
                report.issues.append(
                    PublishIssue(
                        path="reserved_slot",
                        message=(
                            f"No wm_reserved_slot row exists for item {draft.item_entry}. "
                            "Publishing can continue, but managed item-slot tracking is not wired for this item yet."
                        ),
                        severity="warning",
                    )
                )
        else:
            report.issues.append(
                PublishIssue(
                    path="table.wm_reserved_slot",
                    message="Optional table `wm_reserved_slot` is missing; reserved item-slot tracking is disabled.",
                    severity="warning",
                )
            )
        return report

    def capture_snapshot_preview(self, draft: ManagedItemDraft) -> dict[str, Any]:
        return {
            "existing_item_template": self._query_world(
                "SELECT * FROM item_template "
                f"WHERE entry = {int(draft.item_entry)}"
            ),
            "base_item_template": self._query_world(
                "SELECT * FROM item_template "
                f"WHERE entry = {int(draft.base_item_entry)}"
            ),
        }

    def build_final_row(self, draft: ManagedItemDraft) -> tuple[dict[str, Any], list[str]]:
        base_rows = self._query_world(
            "SELECT * FROM item_template "
            f"WHERE entry = {int(draft.base_item_entry)} LIMIT 1"
        )
        if not base_rows:
            raise ValueError(f"Base item entry {draft.base_item_entry} does not exist in item_template.")
        row = dict(base_rows[0])
        column_order = list(row.keys())
        column_map = {column.lower(): column for column in column_order}

        self._set_required(row, column_map, "entry", int(draft.item_entry))
        self._set_required(row, column_map, "name", draft.name.strip())

        self._set_optional(row, column_map, "displayid", draft.display_id)
        self._set_optional(row, column_map, "class", draft.item_class)
        self._set_optional(row, column_map, "subclass", draft.item_subclass)
        self._set_optional(row, column_map, "inventorytype", draft.inventory_type)
        self._set_optional(row, column_map, "quality", draft.quality)
        self._set_optional(row, column_map, "itemlevel", draft.item_level)
        self._set_optional(row, column_map, "requiredlevel", draft.required_level)
        self._set_optional(row, column_map, "bonding", draft.bonding)
        self._set_optional(row, column_map, "buyprice", draft.buy_price)
        self._set_optional(row, column_map, "sellprice", draft.sell_price)
        self._set_optional(row, column_map, "maxcount", draft.max_count)
        self._set_optional(row, column_map, "stackable", draft.stackable)
        self._set_optional(row, column_map, "allowableclass", draft.allowable_class)
        self._set_optional(row, column_map, "allowablerace", draft.allowable_race)
        self._set_optional(row, column_map, "description", draft.description)

        if draft.clear_stats or draft.stats:
            for index in range(1, 11):
                self._set_optional(row, column_map, f"stat_type{index}", 0)
                self._set_optional(row, column_map, f"stat_value{index}", 0)
            for index, stat in enumerate(draft.stats, start=1):
                self._set_optional(row, column_map, f"stat_type{index}", stat.stat_type)
                self._set_optional(row, column_map, f"stat_value{index}", stat.stat_value)

        if draft.clear_spells or draft.spells:
            for index in range(1, 6):
                self._set_optional(row, column_map, f"spellid_{index}", 0)
                self._set_optional(row, column_map, f"spelltrigger_{index}", 0)
                self._set_optional(row, column_map, f"spellcharges_{index}", 0)
                self._set_optional(row, column_map, f"spellppmrate_{index}", 0)
                self._set_optional(row, column_map, f"spellcooldown_{index}", -1)
                self._set_optional(row, column_map, f"spellcategory_{index}", 0)
                self._set_optional(row, column_map, f"spellcategorycooldown_{index}", -1)
            for index, spell in enumerate(draft.spells, start=1):
                self._set_optional(row, column_map, f"spellid_{index}", spell.spell_id)
                self._set_optional(row, column_map, f"spelltrigger_{index}", spell.trigger)
                self._set_optional(row, column_map, f"spellcharges_{index}", spell.charges)
                self._set_optional(row, column_map, f"spellppmrate_{index}", spell.ppm_rate)
                self._set_optional(row, column_map, f"spellcooldown_{index}", spell.cooldown_ms)
                self._set_optional(row, column_map, f"spellcategory_{index}", spell.category)
                self._set_optional(row, column_map, f"spellcategorycooldown_{index}", spell.category_cooldown_ms)

        for key, value in draft.template_defaults.items():
            actual = column_map.get(str(key).lower())
            if actual is not None:
                row[actual] = value

        return row, column_order

    def publish(self, *, draft: ManagedItemDraft, mode: str) -> ItemPublishResult:
        validation = validate_managed_item_draft(draft)
        preflight = self.preflight(draft)
        snapshot_preview = self.capture_snapshot_preview(draft)

        final_row_preview: dict[str, Any] = {}
        sql_plan = ItemSqlPlan(item_entry=draft.item_entry, statements=[])
        if validation.ok and preflight.ok:
            final_row, column_order = self.build_final_row(draft)
            final_row_preview = final_row
            sql_plan = compile_managed_item_sql_plan(
                item_entry=draft.item_entry,
                final_row=final_row,
                column_order=column_order,
                note=f"cloned from base item {draft.base_item_entry}",
            )

        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported publish mode: {mode}")

        if mode == "dry-run" or not validation.ok or not preflight.ok:
            return ItemPublishResult(
                mode=mode,
                draft=draft.to_dict(),
                validation=validation.to_dict(),
                preflight=preflight.to_dict(),
                snapshot_preview=snapshot_preview,
                sql_plan=sql_plan.to_dict(),
                final_row_preview=final_row_preview,
                applied=False,
            )

        snapshot_json = json.dumps(snapshot_preview, ensure_ascii=False).replace("'", "''")
        plan_statements = [stmt for stmt in sql_plan.statements if stmt.strip() and not stmt.strip().startswith("--")]

        try:
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('item', {int(draft.item_entry)}, 'publish', 'started', 'Managed item publish started by wm.items.publish')"
            )
            self._execute_world(
                "INSERT INTO wm_rollback_snapshot (artifact_type, artifact_entry, snapshot_json) VALUES "
                f"('item', {int(draft.item_entry)}, '{snapshot_json}')"
            )
            for statement in plan_statements:
                self._execute_world(statement)
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('item', {int(draft.item_entry)}, 'publish', 'success', 'Managed item publish completed successfully')"
            )
            if preflight.reserved_slot is not None:
                self._execute_world(
                    "UPDATE wm_reserved_slot SET SlotStatus = 'active' "
                    "WHERE EntityType = 'item' "
                    f"AND ReservedID = {int(draft.item_entry)}"
                )
        except MysqlCliError as exc:
            self._execute_publish_failure_log(draft.item_entry, str(exc))
            raise

        return ItemPublishResult(
            mode=mode,
            draft=draft.to_dict(),
            validation=validation.to_dict(),
            preflight=preflight.to_dict(),
            snapshot_preview=snapshot_preview,
            sql_plan=sql_plan.to_dict(),
            final_row_preview=final_row_preview,
            applied=True,
        )

    def _compatibility_issues(
        self,
        *,
        draft: ManagedItemDraft,
        available_columns: set[str],
    ) -> list[PublishIssue]:
        issues: list[PublishIssue] = []
        lower = available_columns_lower(available_columns)

        def has(column_name: str) -> bool:
            return column_name.lower() in lower

        required_for_publish = ["entry", "name"]
        for column_name in required_for_publish:
            if not has(column_name):
                issues.append(
                    PublishIssue(
                        path=f"item_template.{column_name}",
                        message=f"Required item_template column `{column_name}` is missing.",
                    )
                )

        field_requirements = [
            ("display_id", draft.display_id, "displayid"),
            ("description", draft.description, "description"),
            ("item_class", draft.item_class, "class"),
            ("item_subclass", draft.item_subclass, "subclass"),
            ("inventory_type", draft.inventory_type, "inventorytype"),
            ("quality", draft.quality, "quality"),
            ("item_level", draft.item_level, "itemlevel"),
            ("required_level", draft.required_level, "requiredlevel"),
            ("bonding", draft.bonding, "bonding"),
            ("buy_price", draft.buy_price, "buyprice"),
            ("sell_price", draft.sell_price, "sellprice"),
            ("max_count", draft.max_count, "maxcount"),
            ("stackable", draft.stackable, "stackable"),
            ("allowable_class", draft.allowable_class, "allowableclass"),
            ("allowable_race", draft.allowable_race, "allowablerace"),
        ]
        for path, value, column_name in field_requirements:
            if value is not None and not has(column_name):
                issues.append(
                    PublishIssue(
                        path=path,
                        message=f"Requested field `{path}` cannot be published because item_template.`{column_name}` is missing.",
                    )
                )

        if draft.clear_stats or draft.stats:
            for index in range(1, max(len(draft.stats), 1) + 1):
                if not has(f"stat_type{index}") or not has(f"stat_value{index}"):
                    issues.append(
                        PublishIssue(
                            path=f"stats[{index}]",
                            message=f"Stat slot {index} is unavailable because item_template stat columns are missing.",
                        )
                    )
        if draft.clear_spells or draft.spells:
            for index in range(1, max(len(draft.spells), 1) + 1):
                needed = [
                    f"spellid_{index}",
                    f"spelltrigger_{index}",
                    f"spellcharges_{index}",
                    f"spellppmrate_{index}",
                    f"spellcooldown_{index}",
                    f"spellcategory_{index}",
                    f"spellcategorycooldown_{index}",
                ]
                missing = [name for name in needed if not has(name)]
                if missing:
                    issues.append(
                        PublishIssue(
                            path=f"spells[{index}]",
                            message=(
                                f"Spell slot {index} is unavailable because item_template is missing: "
                                + ", ".join(missing)
                            ),
                        )
                    )

        for key in draft.template_defaults:
            if str(key).lower() not in lower:
                issues.append(
                    PublishIssue(
                        path=f"template_defaults.{key}",
                        message=f"template_defaults field `{key}` does not match any live item_template column.",
                        severity="warning",
                    )
                )
        return issues

    def _item_template_columns(self) -> set[str]:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database="information_schema",
            sql=(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.world_db_name)} "
                "AND TABLE_NAME = 'item_template'"
            ),
        )
        return {str(row["COLUMN_NAME"]) for row in rows}

    def _table_presence(self, table_names: set[str]) -> dict[str, bool]:
        if not table_names:
            return {}
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
        present = {str(row["TABLE_NAME"]): True for row in rows}
        return {name: present.get(name, False) for name in table_names}

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

    def _execute_publish_failure_log(self, item_entry: int, error_message: str) -> None:
        safe_error = error_message.replace("'", "''")
        try:
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('item', {int(item_entry)}, 'publish', 'failed', '{safe_error}')"
            )
        except MysqlCliError:
            pass

    @staticmethod
    def _set_required(row: dict[str, Any], column_map: dict[str, str], logical: str, value: Any) -> None:
        actual = column_map.get(logical.lower())
        if actual is None:
            raise KeyError(logical)
        row[actual] = value

    @staticmethod
    def _set_optional(row: dict[str, Any], column_map: dict[str, str], logical: str, value: Any) -> None:
        if value is None:
            return
        actual = column_map.get(logical.lower())
        if actual is not None:
            row[actual] = value


def available_columns_lower(columns: set[str]) -> set[str]:
    return {column.lower() for column in columns}


def load_managed_item_draft(path: str | Path) -> ManagedItemDraft:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("draft"), dict):
        raw = raw["draft"]
    if not isinstance(raw, dict):
        raise ValueError("Managed item draft JSON must be an object.")

    stats_raw = raw.get("stats") or []
    spells_raw = raw.get("spells") or []

    return ManagedItemDraft(
        item_entry=int(raw["item_entry"]),
        base_item_entry=int(raw["base_item_entry"]),
        name=str(raw["name"]),
        display_id=(int(raw["display_id"]) if raw.get("display_id") not in (None, "") else None),
        description=(str(raw["description"]) if raw.get("description") not in (None, "") else None),
        item_class=(int(raw["item_class"]) if raw.get("item_class") not in (None, "") else None),
        item_subclass=(int(raw["item_subclass"]) if raw.get("item_subclass") not in (None, "") else None),
        inventory_type=(int(raw["inventory_type"]) if raw.get("inventory_type") not in (None, "") else None),
        quality=(int(raw["quality"]) if raw.get("quality") not in (None, "") else None),
        item_level=(int(raw["item_level"]) if raw.get("item_level") not in (None, "") else None),
        required_level=(int(raw["required_level"]) if raw.get("required_level") not in (None, "") else None),
        bonding=(int(raw["bonding"]) if raw.get("bonding") not in (None, "") else None),
        buy_price=(int(raw["buy_price"]) if raw.get("buy_price") not in (None, "") else None),
        sell_price=(int(raw["sell_price"]) if raw.get("sell_price") not in (None, "") else None),
        max_count=(int(raw["max_count"]) if raw.get("max_count") not in (None, "") else None),
        stackable=(int(raw["stackable"]) if raw.get("stackable") not in (None, "") else None),
        allowable_class=(int(raw["allowable_class"]) if raw.get("allowable_class") not in (None, "") else None),
        allowable_race=(int(raw["allowable_race"]) if raw.get("allowable_race") not in (None, "") else None),
        clear_stats=bool(raw.get("clear_stats", False)),
        clear_spells=bool(raw.get("clear_spells", False)),
        stats=[
            ItemStatLine(stat_type=int(item["stat_type"]), stat_value=int(item["stat_value"]))
            for item in stats_raw
        ],
        spells=[
            ItemSpellLine(
                spell_id=int(item["spell_id"]),
                trigger=int(item.get("trigger", 0)),
                charges=int(item.get("charges", 0)),
                ppm_rate=float(item.get("ppm_rate", 0.0)),
                cooldown_ms=int(item.get("cooldown_ms", -1)),
                category=int(item.get("category", 0)),
                category_cooldown_ms=int(item.get("category_cooldown_ms", -1)),
            )
            for item in spells_raw
        ],
        tags=[str(value) for value in raw.get("tags", [])],
        template_defaults=dict(raw.get("template_defaults", {})),
    )


def _demo_draft() -> ManagedItemDraft:
    return ManagedItemDraft(
        item_entry=910000,
        base_item_entry=6948,
        name="WM Prototype Token",
        description="Managed item-slot demo cloned from Hearthstone and stripped for WM testing.",
        quality=2,
        item_level=10,
        required_level=1,
        stackable=1,
        max_count=1,
        clear_spells=True,
        tags=["wm_generated", "managed_item_slot", "demo"],
    )


def _render_summary(result: ItemPublishResult) -> str:
    preflight = result.preflight
    validation = result.validation
    lines = [
        f"mode: {result.mode}",
        f"applied: {str(bool(result.applied)).lower()}",
        f"validation.ok: {str(bool(validation.get('ok', False))).lower()}",
        f"preflight.ok: {str(bool(preflight.get('ok', False))).lower()}",
        "",
        "issues:",
    ]
    issues = preflight.get("issues", [])
    if not issues:
        lines.append("- none")
    else:
        for issue in issues:
            lines.append(f"- {issue.get('path')} | {issue.get('severity')} | {issue.get('message')}")
    final_row = result.final_row_preview
    if final_row:
        lines.extend(
            [
                "",
                f"final_row.name: {final_row.get('name') or final_row.get('Name')}",
                f"final_row.entry: {final_row.get('entry') or final_row.get('Entry')}",
            ]
        )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.items.publish")
    parser.add_argument("--draft-json", type=Path, help="Path to a managed item draft JSON file.")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--demo", action="store_true", help="Use the built-in managed item demo draft.")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _sql_string(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _sql_list(values: set[str]) -> str:
    return ", ".join(_sql_string(value) for value in sorted(values))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.demo and args.draft_json is None:
        parser.error("Provide --draft-json PATH or use --demo.")

    draft = _demo_draft() if args.demo else load_managed_item_draft(args.draft_json)
    settings = Settings.from_env()
    client = MysqlCliClient()
    publisher = ItemPublisher(client=client, settings=settings)
    result = publisher.publish(draft=draft, mode=args.mode)
    raw = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary or args.output_json is not None:
        print(_render_summary(result))
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(raw)
    return 0 if (result.preflight.get("ok", False) and result.validation.get("ok", False)) else 2


if __name__ == "__main__":
    sys.exit(main())
