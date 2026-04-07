from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import subprocess
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.quests.bounty import build_bounty_quest_draft
from wm.quests.compiler import compile_bounty_quest_sql_plan
from wm.quests.models import BountyQuestDraft, BountyQuestObjective, BountyQuestReward
from wm.quests.validator import validate_bounty_quest_draft
from wm.targets.resolver import TargetProfile


QUEST_TEMPLATE_BASE_COLUMNS = {
    "ID",
    "QuestType",
    "QuestLevel",
    "MinLevel",
    "LogTitle",
    "RewardMoney",
    "RewardItem1",
    "RewardAmount1",
    "RequiredNpcOrGo1",
    "RequiredNpcOrGoCount1",
}


@dataclass(slots=True)
class PublishIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class QuestPreflightReport:
    quest_id: int
    issues: list[PublishIssue] = field(default_factory=list)
    existing_quest_rows: list[dict[str, Any]] = field(default_factory=list)
    reserved_slot: dict[str, Any] | None = None
    compatibility: dict[str, Any] = field(default_factory=dict)
    duplicate_title_rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "quest_id": self.quest_id,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
            "existing_quest_rows": self.existing_quest_rows,
            "reserved_slot": self.reserved_slot,
            "compatibility": self.compatibility,
            "duplicate_title_rows": self.duplicate_title_rows,
        }


@dataclass(slots=True)
class QuestPublishResult:
    mode: str
    draft: dict[str, Any]
    validation: dict[str, Any]
    preflight: dict[str, Any]
    snapshot_preview: dict[str, Any]
    sql_plan: dict[str, Any]
    applied: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class QuestPublisher:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def preflight(self, draft: BountyQuestDraft) -> QuestPreflightReport:
        report = QuestPreflightReport(quest_id=draft.quest_id)

        required_tables = {
            "quest_template",
            "creature_queststarter",
            "creature_questender",
            "creature_template",
            "wm_publish_log",
            "wm_rollback_snapshot",
            "wm_reserved_slot",
        }
        all_tables = set(required_tables) | {"quest_offer_reward", "quest_request_items"}
        table_presence = self._table_presence(all_tables)

        for table_name in sorted(required_tables):
            if not table_presence.get(table_name, False):
                report.issues.append(
                    PublishIssue(
                        path=f"table.{table_name}",
                        message=f"Required table `{table_name}` is missing from `{self.settings.world_db_name}`.",
                    )
                )

        quest_template_columns = self._table_columns("quest_template") if table_presence.get("quest_template", False) else set()
        quest_offer_reward_columns = self._table_columns("quest_offer_reward") if table_presence.get("quest_offer_reward", False) else set()
        quest_request_items_columns = self._table_columns("quest_request_items") if table_presence.get("quest_request_items", False) else set()

        compatibility = self._build_compatibility_matrix(
            table_presence=table_presence,
            quest_template_columns=quest_template_columns,
            quest_offer_reward_columns=quest_offer_reward_columns,
            quest_request_items_columns=quest_request_items_columns,
        )
        report.compatibility = compatibility

        for column_name in sorted(QUEST_TEMPLATE_BASE_COLUMNS - quest_template_columns):
            report.issues.append(
                PublishIssue(
                    path=f"quest_template.{column_name}",
                    message=f"Required quest_template column `{column_name}` is missing.",
                )
            )

        if not compatibility["quest_description_supported"]:
            report.issues.append(
                PublishIssue(
                    path="quest_text.description",
                    message="Quest description text is not supported by this schema (expected `QuestDescription` or `Details`).",
                )
            )
        if not compatibility["objective_text_supported"]:
            report.issues.append(
                PublishIssue(
                    path="quest_text.objective",
                    message="Objective text is not supported by this schema (expected `ObjectiveText1` or `Objectives`).",
                )
            )
        if not compatibility["offer_reward_text_supported"]:
            report.issues.append(
                PublishIssue(
                    path="quest_text.offer_reward",
                    message=(
                        "Offer reward text is not supported by this schema "
                        "(expected `quest_template.OfferRewardText` or `quest_offer_reward.RewardText`)."
                    ),
                )
            )
        if not compatibility["request_items_text_supported"]:
            report.issues.append(
                PublishIssue(
                    path="quest_text.request_items",
                    message=(
                        "Request / completion text is not supported by this schema "
                        "(expected `quest_template.RequestItemsText` or `quest_request_items.CompletionText`)."
                    ),
                )
            )

        if table_presence.get("quest_template", False):
            report.existing_quest_rows = self._query_world(
                "SELECT ID, LogTitle FROM quest_template "
                f"WHERE ID = {int(draft.quest_id)}"
            )

        if table_presence.get("creature_queststarter", False) and table_presence.get("quest_template", False):
            report.duplicate_title_rows = self._find_duplicate_title_rows(draft)
            if report.duplicate_title_rows:
                duplicate_ids = ", ".join(str(row.get("ID")) for row in report.duplicate_title_rows)
                report.issues.append(
                    PublishIssue(
                        path="dedupe.title",
                        message=(
                            f"Quest giver {draft.questgiver_entry} already offers WM-visible quest title `{draft.title}` "
                            f"through quest IDs: {duplicate_ids}. Use edit_live or retire/rollback the old quest first."
                        ),
                    )
                )

        if table_presence.get("creature_template", False):
            if not self._creature_exists(draft.questgiver_entry):
                report.issues.append(
                    PublishIssue(
                        path="questgiver_entry",
                        message=f"Quest giver entry {draft.questgiver_entry} does not exist in creature_template.",
                    )
                )
            if not self._creature_exists(draft.objective.target_entry):
                report.issues.append(
                    PublishIssue(
                        path="objective.target_entry",
                        message=f"Target entry {draft.objective.target_entry} does not exist in creature_template.",
                    )
                )

        if table_presence.get("wm_reserved_slot", False):
            slot_rows = self._query_world(
                "SELECT EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON "
                "FROM wm_reserved_slot "
                f"WHERE EntityType = 'quest' AND ReservedID = {int(draft.quest_id)}"
            )
            if slot_rows:
                report.reserved_slot = slot_rows[0]
                slot_status = str(slot_rows[0].get("SlotStatus") or "")
                if slot_status not in {"staged", "active"}:
                    report.issues.append(
                        PublishIssue(
                            path="reserved_slot.status",
                            message=(
                                f"Reserved slot for quest {draft.quest_id} has status `{slot_status}`; "
                                "expected `staged` for fresh publish or `active` for already-published managed content."
                            ),
                        )
                    )
                elif slot_status == "active" and report.existing_quest_rows:
                    report.issues.append(
                        PublishIssue(
                            path="reserved_slot.status",
                            message=(
                                f"Quest slot {draft.quest_id} is already active. Use `wm.quests.edit_live` for in-place changes, "
                                "or rollback / retire the old quest before publishing a new draft into this slot."
                            ),
                        )
                    )
                elif slot_status == "staged" and report.existing_quest_rows:
                    report.issues.append(
                        PublishIssue(
                            path="quest_id",
                            message="Quest ID already exists and will be replaced from a staged reserved slot if apply mode is used.",
                            severity="warning",
                        )
                    )
            else:
                report.issues.append(
                    PublishIssue(
                        path="reserved_slot",
                        message=(
                            f"Quest publishing now requires a managed wm_reserved_slot row for quest {draft.quest_id}. "
                            "Seed a quest slot range and stage a slot before publishing."
                        ),
                    )
                )

        return report

    def capture_snapshot_preview(self, draft: BountyQuestDraft) -> dict[str, Any]:
        snapshot = {
            "quest_template": self._query_world(
                "SELECT * FROM quest_template "
                f"WHERE ID = {int(draft.quest_id)}"
            ),
            "creature_queststarter": self._query_world(
                "SELECT * FROM creature_queststarter "
                f"WHERE quest = {int(draft.quest_id)}"
            ),
            "creature_questender": self._query_world(
                "SELECT * FROM creature_questender "
                f"WHERE quest = {int(draft.quest_id)}"
            ),
        }
        table_presence = self._table_presence({"quest_offer_reward", "quest_request_items"})
        if table_presence.get("quest_offer_reward", False):
            snapshot["quest_offer_reward"] = self._query_world(
                "SELECT * FROM quest_offer_reward "
                f"WHERE ID = {int(draft.quest_id)}"
            )
        if table_presence.get("quest_request_items", False):
            snapshot["quest_request_items"] = self._query_world(
                "SELECT * FROM quest_request_items "
                f"WHERE ID = {int(draft.quest_id)}"
            )
        return snapshot

    def publish(self, *, draft: BountyQuestDraft, mode: str) -> QuestPublishResult:
        validation = validate_bounty_quest_draft(draft)
        preflight = self.preflight(draft)
        snapshot_preview = self.capture_snapshot_preview(draft)
        sql_plan = self._compile_sql_plan(draft)

        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported publish mode: {mode}")

        if mode == "dry-run" or not validation.ok or not preflight.ok:
            return QuestPublishResult(
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
                f"('quest', {int(draft.quest_id)}, 'publish', 'started', 'Quest publish started by wm.quests.publish')"
            )
            self._execute_world(
                "INSERT INTO wm_rollback_snapshot (artifact_type, artifact_entry, snapshot_json) VALUES "
                f"('quest', {int(draft.quest_id)}, '{snapshot_json}')"
            )
            for statement in plan_statements:
                self._execute_world(statement)
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('quest', {int(draft.quest_id)}, 'publish', 'success', 'Quest publish completed successfully')"
            )
            if preflight.reserved_slot is not None:
                self._execute_world(
                    "UPDATE wm_reserved_slot SET SlotStatus = 'active' "
                    "WHERE EntityType = 'quest' "
                    f"AND ReservedID = {int(draft.quest_id)}"
                )
        except MysqlCliError as exc:
            self._execute_publish_failure_log(draft.quest_id, str(exc))
            raise

        return QuestPublishResult(
            mode=mode,
            draft=draft.to_dict(),
            validation=validation.to_dict(),
            preflight=preflight.to_dict(),
            snapshot_preview=snapshot_preview,
            sql_plan=sql_plan.to_dict(),
            applied=True,
        )

    def _compile_sql_plan(self, draft: BountyQuestDraft):
        table_presence = self._table_presence({"quest_offer_reward", "quest_request_items"})
        available_tables = {name for name, present in table_presence.items() if present}
        quest_template_columns = self._table_columns("quest_template")
        quest_offer_reward_columns = self._table_columns("quest_offer_reward") if "quest_offer_reward" in available_tables else set()
        quest_request_items_columns = self._table_columns("quest_request_items") if "quest_request_items" in available_tables else set()

        return compile_bounty_quest_sql_plan(
            draft,
            quest_template_columns=quest_template_columns,
            available_tables=available_tables,
            quest_offer_reward_columns=quest_offer_reward_columns,
            quest_request_items_columns=quest_request_items_columns,
        )

    def _build_compatibility_matrix(
        self,
        *,
        table_presence: dict[str, bool],
        quest_template_columns: set[str],
        quest_offer_reward_columns: set[str],
        quest_request_items_columns: set[str],
    ) -> dict[str, Any]:
        return {
            "quest_description_supported": bool({"QuestDescription", "Details"} & quest_template_columns),
            "objective_text_supported": bool({"ObjectiveText1", "Objectives"} & quest_template_columns),
            "offer_reward_text_supported": (
                "OfferRewardText" in quest_template_columns
                or (
                    table_presence.get("quest_offer_reward", False)
                    and "RewardText" in quest_offer_reward_columns
                )
            ),
            "request_items_text_supported": (
                "RequestItemsText" in quest_template_columns
                or (
                    table_presence.get("quest_request_items", False)
                    and "CompletionText" in quest_request_items_columns
                )
            ),
            "quest_template_columns": sorted(quest_template_columns),
            "quest_offer_reward_columns": sorted(quest_offer_reward_columns),
            "quest_request_items_columns": sorted(quest_request_items_columns),
        }

    def _find_duplicate_title_rows(self, draft: BountyQuestDraft) -> list[dict[str, Any]]:
        return self._query_world(
            "SELECT qt.ID, qt.LogTitle FROM quest_template qt "
            "JOIN creature_queststarter cqs ON cqs.quest = qt.ID "
            f"WHERE cqs.id = {int(draft.questgiver_entry)} "
            f"AND qt.LogTitle = {_sql_string(draft.title)} "
            f"AND qt.ID <> {int(draft.quest_id)}"
        )

    def _execute_publish_failure_log(self, quest_id: int, error_message: str) -> None:
        safe_error = error_message.replace("'", "''")
        try:
            self._execute_world(
                "INSERT INTO wm_publish_log (artifact_type, artifact_entry, action, status, notes) VALUES "
                f"('quest', {int(quest_id)}, 'publish', 'failed', '{safe_error}')"
            )
        except MysqlCliError:
            pass

    def _creature_exists(self, entry: int) -> bool:
        rows = self._query_world(
            "SELECT entry, name FROM creature_template "
            f"WHERE entry = {int(entry)} LIMIT 1"
        )
        return bool(rows)

    def _table_presence(self, table_names: set[str]) -> dict[str, bool]:
        if not table_names:
            return {}
        sql = (
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.world_db_name)} "
            f"AND TABLE_NAME IN ({_sql_list(table_names)})"
        )
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database="information_schema",
            sql=sql,
        )
        present = {str(row["TABLE_NAME"]): True for row in rows}
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
                f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.world_db_name)} "
                f"AND TABLE_NAME = {_sql_string(table_name)}"
            ),
        )
        return {str(row["COLUMN_NAME"]) for row in rows}

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


def load_bounty_quest_draft(path: str | Path) -> BountyQuestDraft:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("draft"), dict):
        raw = raw["draft"]
    if not isinstance(raw, dict):
        raise ValueError("Quest draft JSON must be an object.")

    objective = raw.get("objective") or {}
    reward = raw.get("reward") or {}

    return BountyQuestDraft(
        quest_id=int(raw["quest_id"]),
        quest_level=int(raw["quest_level"]),
        min_level=int(raw["min_level"]),
        questgiver_entry=int(raw["questgiver_entry"]),
        questgiver_name=str(raw["questgiver_name"]),
        title=str(raw["title"]),
        quest_description=str(raw["quest_description"]),
        objective_text=str(raw["objective_text"]),
        offer_reward_text=str(raw["offer_reward_text"]),
        request_items_text=str(raw["request_items_text"]),
        objective=BountyQuestObjective(
            target_entry=int(objective["target_entry"]),
            target_name=str(objective["target_name"]),
            kill_count=int(objective["kill_count"]),
        ),
        reward=BountyQuestReward(
            money_copper=int(reward.get("money_copper", 0)),
            reward_item_entry=(
                int(reward["reward_item_entry"])
                if reward.get("reward_item_entry") not in (None, "")
                else None
            ),
            reward_item_name=(
                str(reward["reward_item_name"])
                if reward.get("reward_item_name") not in (None, "")
                else None
            ),
            reward_item_count=int(reward.get("reward_item_count", 1)),
        ),
        tags=[str(x) for x in raw.get("tags", [])],
        template_defaults={str(k): v for k, v in (raw.get("template_defaults") or {}).items()},
    )


def _demo_draft() -> BountyQuestDraft:
    return build_bounty_quest_draft(
        quest_id=910001,
        questgiver_entry=1498,
        questgiver_name="Bethor Iceshard",
        target_profile=TargetProfile(
            entry=46,
            name="Murloc Forager",
            subname=None,
            level_min=9,
            level_max=10,
            faction_id=18,
            faction_label="Murloc",
            mechanical_type="HUMANOID",
            family=None,
            rank="NORMAL",
            unit_class="WARRIOR",
            service_roles=[],
            has_gossip_menu=False,
        ),
        kill_count=8,
        reward_money_copper=1200,
    )


def _sql_string(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _sql_list(values: set[str]) -> str:
    return ", ".join(_sql_string(value) for value in sorted(values))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.publish")
    parser.add_argument("--draft-json", type=Path, help="Path to a quest draft JSON file.")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--output-json", type=Path, help="Write the full JSON result to this file.")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a compact human-readable summary instead of the full JSON result.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use the built-in Bethor -> Murloc bounty draft instead of loading from a file.",
    )
    return parser


def _render_compact_summary(result: QuestPublishResult) -> str:
    lines = [
        f"mode: {result.mode}",
        f"applied: {str(result.applied).lower()}",
        f"validation.ok: {str(result.validation.get('ok', False)).lower()}",
        f"preflight.ok: {str(result.preflight.get('ok', False)).lower()}",
        "",
        "issues:",
    ]
    issues = result.preflight.get("issues", [])
    if not issues:
        lines.append("- none")
    else:
        for issue in issues:
            lines.append(
                f"- {issue.get('path')} | {issue.get('severity')} | {issue.get('message')}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.demo and args.draft_json is None:
        parser.error("Provide --draft-json PATH or use --demo.")

    draft = _demo_draft() if args.demo else load_bounty_quest_draft(args.draft_json)
    settings = Settings.from_env()
    client = MysqlCliClient()
    publisher = QuestPublisher(client=client, settings=settings)
    result = publisher.publish(draft=draft, mode=args.mode)
    payload = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload, encoding="utf-8")

    if args.summary or args.output_json is not None:
        print(_render_compact_summary(result))
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(payload)

    return 0 if (result.preflight.get("ok", False) and result.validation.get("ok", False)) else 2


__all__ = [
    "PublishIssue",
    "QuestPreflightReport",
    "QuestPublishResult",
    "QuestPublisher",
    "load_bounty_quest_draft",
    "main",
]
