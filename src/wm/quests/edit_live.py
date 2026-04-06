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
from wm.runtime_sync import RuntimeSyncResult, SoapRuntimeClient, build_default_quest_reload_commands

XP_REWARD_COLUMNS = ["RewardXPDifficulty", "RewardXPId", "RewardXP"]


@dataclass(slots=True)
class EditIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class QuestEditResult:
    quest_id: int
    applied: bool
    changed_fields: dict[str, Any] = field(default_factory=dict)
    issues: list[EditIssue] = field(default_factory=list)
    runtime_sync: dict[str, Any] = field(default_factory=dict)
    restart_recommended: bool = False

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "quest_id": self.quest_id,
            "applied": self.applied,
            "ok": self.ok,
            "changed_fields": self.changed_fields,
            "issues": [issue.to_dict() for issue in self.issues],
            "runtime_sync": self.runtime_sync,
            "restart_recommended": self.restart_recommended,
        }


class QuestLiveEditor:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def edit(
        self,
        *,
        quest_id: int,
        title: str | None,
        reward_money_copper: int | None,
        reward_item_entry: int | None,
        reward_item_count: int | None,
        clear_reward_item: bool,
        reward_xp: int | None,
        offer_reward_text: str | None,
        runtime_sync_mode: str,
        apply: bool,
    ) -> QuestEditResult:
        issues: list[EditIssue] = []
        changed_fields: dict[str, Any] = {}
        columns = self._quest_template_columns()
        tables = self._table_presence({"quest_offer_reward", "item_template", "creature_queststarter"})

        if not self._quest_exists(quest_id):
            issues.append(EditIssue(path="quest_id", message=f"Quest {quest_id} was not found in quest_template."))
            return QuestEditResult(quest_id=quest_id, applied=False, issues=issues)

        updates: list[str] = []

        if title is not None:
            if "LogTitle" not in columns:
                issues.append(EditIssue(path="LogTitle", message="quest_template.LogTitle is missing."))
            else:
                updates.append(f"`LogTitle` = {self._sql_string(title)}")
                changed_fields["LogTitle"] = title

        if reward_money_copper is not None:
            if "RewardMoney" not in columns:
                issues.append(EditIssue(path="RewardMoney", message="quest_template.RewardMoney is missing."))
            else:
                updates.append(f"`RewardMoney` = {int(reward_money_copper)}")
                changed_fields["RewardMoney"] = int(reward_money_copper)

        if clear_reward_item:
            if "RewardItem1" in columns:
                updates.append("`RewardItem1` = 0")
                changed_fields["RewardItem1"] = 0
            if "RewardAmount1" in columns:
                updates.append("`RewardAmount1` = 0")
                changed_fields["RewardAmount1"] = 0

        if reward_item_entry is not None:
            if "RewardItem1" not in columns:
                issues.append(EditIssue(path="RewardItem1", message="quest_template.RewardItem1 is missing."))
            else:
                if tables.get("item_template", False) and reward_item_entry > 0 and not self._item_exists(reward_item_entry):
                    issues.append(
                        EditIssue(
                            path="RewardItem1",
                            message=f"Item entry {reward_item_entry} was not found in item_template.",
                        )
                    )
                updates.append(f"`RewardItem1` = {int(reward_item_entry)}")
                changed_fields["RewardItem1"] = int(reward_item_entry)

        if reward_item_count is not None:
            if "RewardAmount1" not in columns:
                issues.append(EditIssue(path="RewardAmount1", message="quest_template.RewardAmount1 is missing."))
            else:
                updates.append(f"`RewardAmount1` = {int(reward_item_count)}")
                changed_fields["RewardAmount1"] = int(reward_item_count)

        if reward_xp is not None:
            xp_column = self._detect_xp_column(columns)
            if xp_column is None:
                issues.append(
                    EditIssue(
                        path="reward_xp",
                        message="No supported XP reward column was found in quest_template.",
                    )
                )
            else:
                updates.append(f"`{xp_column}` = {int(reward_xp)}")
                changed_fields[xp_column] = int(reward_xp)

        offer_reward_update_sql: str | None = None
        if offer_reward_text is not None:
            if "OfferRewardText" in columns:
                updates.append(f"`OfferRewardText` = {self._sql_string(offer_reward_text)}")
                changed_fields["OfferRewardText"] = offer_reward_text
            elif tables.get("quest_offer_reward", False):
                offer_reward_update_sql = (
                    "INSERT INTO `quest_offer_reward` (`ID`, `RewardText`) VALUES "
                    f"({int(quest_id)}, {self._sql_string(offer_reward_text)}) "
                    "ON DUPLICATE KEY UPDATE "
                    f"`RewardText` = {self._sql_string(offer_reward_text)}"
                )
                changed_fields["quest_offer_reward.RewardText"] = offer_reward_text
            else:
                issues.append(
                    EditIssue(
                        path="OfferRewardText",
                        message="No supported offer-reward text storage was found.",
                    )
                )

        if not changed_fields:
            issues.append(EditIssue(path="edit", message="No quest changes were requested.", severity="warning"))

        if any(issue.severity == "error" for issue in issues):
            return QuestEditResult(quest_id=quest_id, applied=False, changed_fields=changed_fields, issues=issues)

        if apply and updates:
            self._execute_world(
                "UPDATE `quest_template` SET " + ", ".join(updates) + f" WHERE `ID` = {int(quest_id)}"
            )
            if offer_reward_update_sql is not None:
                self._execute_world(offer_reward_update_sql)

        runtime_sync = self._sync_runtime(
            quest_id=quest_id,
            runtime_sync_mode=runtime_sync_mode,
            apply=apply,
        )

        return QuestEditResult(
            quest_id=quest_id,
            applied=bool(apply),
            changed_fields=changed_fields,
            issues=issues,
            runtime_sync=runtime_sync.to_dict(),
            restart_recommended=bool(runtime_sync.restart_recommended),
        )

    def _sync_runtime(self, *, quest_id: int, runtime_sync_mode: str, apply: bool) -> RuntimeSyncResult:
        if not apply:
            return RuntimeSyncResult(
                protocol="none",
                enabled=False,
                overall_ok=True,
                restart_recommended=False,
                note="Dry-run mode does not touch the live runtime.",
            )
        enabled = runtime_sync_mode == "soap" or (runtime_sync_mode == "auto" and self.settings.soap_enabled)
        if not enabled:
            return RuntimeSyncResult(
                protocol="none",
                enabled=False,
                overall_ok=True,
                restart_recommended=True,
                note="Runtime sync is disabled. Restart worldserver before testing the edited quest.",
            )
        if not self.settings.soap_user or not self.settings.soap_password:
            return RuntimeSyncResult(
                protocol="soap",
                enabled=True,
                overall_ok=False,
                restart_recommended=True,
                note="SOAP runtime sync was requested but WM_SOAP_USER / WM_SOAP_PASSWORD are not configured.",
            )
        starter_entry = self._starter_entry(quest_id)
        client = SoapRuntimeClient(settings=self.settings)
        commands = build_default_quest_reload_commands(questgiver_entry=starter_entry)
        results = []
        overall_ok = True
        for command in commands:
            result = client.execute_command(command)
            result.command = command
            results.append(result)
            if not result.ok:
                overall_ok = False
        return RuntimeSyncResult(
            protocol="soap",
            enabled=True,
            overall_ok=overall_ok,
            commands=results,
            restart_recommended=False,
            note="Quest rows were edited and reload commands were sent.",
        )

    def _quest_exists(self, quest_id: int) -> bool:
        rows = self._query_world(f"SELECT `ID` FROM `quest_template` WHERE `ID` = {int(quest_id)} LIMIT 1")
        return bool(rows)

    def _item_exists(self, item_entry: int) -> bool:
        rows = self._query_world(f"SELECT `entry` FROM `item_template` WHERE `entry` = {int(item_entry)} LIMIT 1")
        return bool(rows)

    def _starter_entry(self, quest_id: int) -> int | None:
        rows = self._query_world(
            f"SELECT `id` FROM `creature_queststarter` WHERE `quest` = {int(quest_id)} ORDER BY `id` LIMIT 1"
        )
        if not rows:
            return None
        return int(rows[0]["id"])

    def _detect_xp_column(self, columns: set[str]) -> str | None:
        for column_name in XP_REWARD_COLUMNS:
            if column_name in columns:
                return column_name
        return None

    def _quest_template_columns(self) -> set[str]:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database="information_schema",
            sql=(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                f"WHERE TABLE_SCHEMA = {self._sql_string(self.settings.world_db_name)} "
                "AND TABLE_NAME = 'quest_template'"
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
                f"WHERE TABLE_SCHEMA = {self._sql_string(self.settings.world_db_name)} "
                f"AND TABLE_NAME IN ({self._sql_list(table_names)})"
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

    @staticmethod
    def _sql_string(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    @staticmethod
    def _sql_list(values: set[str]) -> str:
        return ", ".join(QuestLiveEditor._sql_string(value) for value in sorted(values))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.edit_live")
    parser.add_argument("--quest-id", type=int, required=True)
    parser.add_argument("--title")
    parser.add_argument("--reward-money-copper", type=int)
    parser.add_argument("--reward-item-entry", type=int)
    parser.add_argument("--reward-item-count", type=int)
    parser.add_argument("--clear-reward-item", action="store_true")
    parser.add_argument("--reward-xp", type=int)
    parser.add_argument("--offer-reward-text")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _render_summary(result: QuestEditResult) -> str:
    runtime_sync = result.runtime_sync
    lines = [
        f"quest_id: {result.quest_id}",
        f"applied: {str(result.applied).lower()}",
        f"ok: {str(result.ok).lower()}",
        f"runtime_sync.enabled: {str(bool(runtime_sync.get('enabled', False))).lower()}",
        f"runtime_sync.protocol: {runtime_sync.get('protocol')}",
        f"runtime_sync.overall_ok: {str(bool(runtime_sync.get('overall_ok', False))).lower()}",
        f"restart_recommended: {str(bool(result.restart_recommended)).lower()}",
        "",
        "changed_fields:",
    ]
    if not result.changed_fields:
        lines.append("- none")
    else:
        for key, value in result.changed_fields.items():
            lines.append(f"- {key} = {value}")
    lines.extend(["", "issues:"])
    if not result.issues:
        lines.append("- none")
    else:
        for issue in result.issues:
            lines.append(f"- {issue.path} | {issue.severity} | {issue.message}")
    lines.extend(["", "runtime_commands:"])
    commands = runtime_sync.get("commands", [])
    if not commands:
        lines.append("- none")
    else:
        for command in commands:
            if command.get("ok"):
                preview = str(command.get("result") or "").strip().splitlines()
                preview_text = preview[0] if preview else "ok"
                lines.append(f"- ok | {command.get('command')} | {preview_text}")
            else:
                lines.append(
                    f"- fail | {command.get('command')} | {command.get('fault_string') or command.get('fault_code')}"
                )
    if runtime_sync.get("note"):
        lines.extend(["", f"note: {runtime_sync.get('note')}"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    editor = QuestLiveEditor(client=client, settings=settings)
    result = editor.edit(
        quest_id=args.quest_id,
        title=args.title,
        reward_money_copper=args.reward_money_copper,
        reward_item_entry=args.reward_item_entry,
        reward_item_count=args.reward_item_count,
        clear_reward_item=args.clear_reward_item,
        reward_xp=args.reward_xp,
        offer_reward_text=args.offer_reward_text,
        runtime_sync_mode=args.runtime_sync,
        apply=args.mode == "apply",
    )
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
    return 0 if result.ok and bool(result.runtime_sync.get("overall_ok", True)) else 2


if __name__ == "__main__":
    sys.exit(main())
