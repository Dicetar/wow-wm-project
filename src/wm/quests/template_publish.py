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
from wm.quests.models import BountyQuestDraft, BountyQuestObjective, BountyQuestReward, ValidationIssue, ValidationResult
from wm.quests.publish import QuestPublisher
from wm.quests.validator import validate_bounty_quest_draft
from wm.runtime_sync import RuntimeSyncResult, SoapRuntimeClient, build_default_quest_reload_commands

XP_REWARD_COLUMNS = ["RewardXPDifficulty", "RewardXPId", "RewardXP"]
REWARD_SPELL_CAST_COLUMNS = ["RewardSpellCast"]
REWARD_SPELL_COLUMNS = ["RewardSpell"]
REPUTATION_SLOT_COUNT = 5


@dataclass(slots=True)
class ReputationReward:
    faction_id: int
    value: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TemplatePublishIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExtraRewardPreflight:
    issues: list[TemplatePublishIssue] = field(default_factory=list)
    compatibility: dict[str, Any] = field(default_factory=dict)
    update_fields: dict[str, Any] = field(default_factory=dict)
    sql_statements: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
            "compatibility": self.compatibility,
            "update_fields": self.update_fields,
            "sql_statements": list(self.sql_statements),
        }


@dataclass(slots=True)
class RichBountyQuestDraft:
    quest_id: int
    quest_level: int
    min_level: int
    questgiver_entry: int
    questgiver_name: str
    title: str
    quest_description: str
    objective_text: str
    offer_reward_text: str
    request_items_text: str
    target_entry: int
    target_name: str
    kill_count: int
    reward_money_copper: int = 0
    reward_item_entry: int | None = None
    reward_item_name: str | None = None
    reward_item_count: int = 1
    reward_experience: int | None = None
    reward_spell_cast_id: int | None = None
    reward_spell_id: int | None = None
    reward_reputations: list[ReputationReward] = field(default_factory=list)
    start_npc_entry: int | None = None
    end_npc_entry: int | None = None
    grant_mode: str = "npc_start"
    tags: list[str] = field(default_factory=list)
    template_defaults: dict[str, Any] = field(default_factory=dict)

    def to_base_draft(self) -> BountyQuestDraft:
        return BountyQuestDraft(
            quest_id=int(self.quest_id),
            quest_level=int(self.quest_level),
            min_level=int(self.min_level),
            questgiver_entry=int(self.questgiver_entry),
            questgiver_name=self.questgiver_name,
            title=self.title,
            quest_description=self.quest_description,
            objective_text=self.objective_text,
            offer_reward_text=self.offer_reward_text,
            request_items_text=self.request_items_text,
            objective=BountyQuestObjective(
                target_entry=int(self.target_entry),
                target_name=self.target_name,
                kill_count=int(self.kill_count),
            ),
            reward=BountyQuestReward(
                money_copper=int(self.reward_money_copper),
                reward_item_entry=(int(self.reward_item_entry) if self.reward_item_entry not in (None, "") else None),
                reward_item_name=self.reward_item_name,
                reward_item_count=int(self.reward_item_count),
            ),
            start_npc_entry=(int(self.start_npc_entry) if self.start_npc_entry not in (None, "") else None),
            end_npc_entry=(int(self.end_npc_entry) if self.end_npc_entry not in (None, "") else None),
            grant_mode=str(self.grant_mode),
            tags=[str(tag) for tag in self.tags],
            template_defaults={str(k): v for k, v in self.template_defaults.items()},
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reward_reputations"] = [reward.to_dict() for reward in self.reward_reputations]
        return payload


@dataclass(slots=True)
class TemplateQuestPublishResult:
    mode: str
    draft: dict[str, Any]
    base_publish: dict[str, Any]
    extra_validation: dict[str, Any]
    extra_preflight: dict[str, Any]
    runtime_sync: dict[str, Any]
    applied: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RichQuestTemplatePublisher:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.base_publisher = QuestPublisher(client=client, settings=settings)

    def validate_extra(self, draft: RichBountyQuestDraft) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if draft.reward_experience is not None and int(draft.reward_experience) < 0:
            issues.append(ValidationIssue(path="reward_experience", message="Reward experience cannot be negative."))
        if draft.reward_spell_cast_id is not None and int(draft.reward_spell_cast_id) <= 0:
            issues.append(ValidationIssue(path="reward_spell_cast_id", message="Reward spell-cast ID must be positive."))
        if draft.reward_spell_id is not None and int(draft.reward_spell_id) <= 0:
            issues.append(ValidationIssue(path="reward_spell_id", message="Reward spell ID must be positive."))
        if len(draft.reward_reputations) > REPUTATION_SLOT_COUNT:
            issues.append(
                ValidationIssue(
                    path="reward_reputations",
                    message=f"No more than {REPUTATION_SLOT_COUNT} reputation rewards are supported by quest_template.",
                )
            )
        for index, reward in enumerate(draft.reward_reputations, start=1):
            if int(reward.faction_id) <= 0:
                issues.append(
                    ValidationIssue(
                        path=f"reward_reputations[{index}].faction_id",
                        message="Reputation faction ID must be positive.",
                    )
                )
            if int(reward.value) == 0:
                issues.append(
                    ValidationIssue(
                        path=f"reward_reputations[{index}].value",
                        message="Reputation value should not be zero.",
                        severity="warning",
                    )
                )
        return ValidationResult(issues=issues)

    def preflight_extra(self, draft: RichBountyQuestDraft) -> ExtraRewardPreflight:
        quest_template_columns = self._quest_template_columns()
        return build_extra_reward_preflight(draft=draft, quest_template_columns=quest_template_columns)

    def publish(
        self,
        *,
        draft: RichBountyQuestDraft,
        mode: str,
        runtime_sync_mode: str = "auto",
    ) -> TemplateQuestPublishResult:
        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported publish mode: {mode}")

        base_draft = draft.to_base_draft()
        base_validation = validate_bounty_quest_draft(base_draft)
        extra_validation = self.validate_extra(draft)
        extra_preflight = self.preflight_extra(draft)

        ready_for_apply = bool(base_validation.ok and extra_validation.ok and extra_preflight.ok)
        base_mode = mode if (mode == "apply" and ready_for_apply) else "dry-run"
        base_publish = self.base_publisher.publish(draft=base_draft, mode=base_mode)

        if mode != "apply" or not ready_for_apply or not bool(base_publish.applied):
            runtime_sync = RuntimeSyncResult(
                protocol="none",
                enabled=False,
                overall_ok=True,
                restart_recommended=False,
                note="Dry-run mode does not touch the live runtime." if mode != "apply" else "Apply mode was not reached because validation or preflight failed.",
            )
            return TemplateQuestPublishResult(
                mode=mode,
                draft=draft.to_dict(),
                base_publish=base_publish.to_dict(),
                extra_validation=extra_validation.to_dict(),
                extra_preflight=extra_preflight.to_dict(),
                runtime_sync=runtime_sync.to_dict(),
                applied=False,
            )

        extra_error: str | None = None
        for statement in extra_preflight.sql_statements:
            try:
                self._execute_world(statement)
            except MysqlCliError as exc:
                extra_error = str(exc)
                extra_preflight.issues.append(
                    TemplatePublishIssue(
                        path="extra_reward_update",
                        message=f"Extra reward update failed after base publish: {exc}",
                    )
                )
                break

        if extra_error is None:
            runtime_sync = _sync_runtime(
                draft=base_draft,
                settings=self.settings,
                mode=mode,
                runtime_sync_mode=runtime_sync_mode,
            )
        else:
            runtime_sync = RuntimeSyncResult(
                protocol="none",
                enabled=False,
                overall_ok=False,
                restart_recommended=True,
                note="Base quest rows were published, but the extra reward update failed. Roll back the slot before testing.",
            )

        applied = bool(base_publish.applied and extra_error is None and runtime_sync.overall_ok)
        return TemplateQuestPublishResult(
            mode=mode,
            draft=draft.to_dict(),
            base_publish=base_publish.to_dict(),
            extra_validation=extra_validation.to_dict(),
            extra_preflight=extra_preflight.to_dict(),
            runtime_sync=runtime_sync.to_dict(),
            applied=applied,
        )

    def _quest_template_columns(self) -> set[str]:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database="information_schema",
            sql=(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.world_db_name)} "
                "AND TABLE_NAME = 'quest_template'"
            ),
        )
        return {str(row["COLUMN_NAME"]) for row in rows}

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


def build_extra_reward_preflight(
    *,
    draft: RichBountyQuestDraft,
    quest_template_columns: set[str],
) -> ExtraRewardPreflight:
    preflight = ExtraRewardPreflight(
        compatibility={
            "quest_template_columns": sorted(quest_template_columns),
            "xp_column": None,
            "reward_spell_cast_column": None,
            "reward_spell_column": None,
            "reputation_slots": {},
        }
    )

    update_fields: dict[str, Any] = {}

    if draft.reward_experience is not None:
        xp_column = next((column for column in XP_REWARD_COLUMNS if column in quest_template_columns), None)
        preflight.compatibility["xp_column"] = xp_column
        if xp_column is None:
            preflight.issues.append(
                TemplatePublishIssue(
                    path="reward_experience",
                    message="No supported XP reward column was found in quest_template.",
                )
            )
        else:
            update_fields[xp_column] = int(draft.reward_experience)

    if draft.reward_spell_cast_id is not None:
        spell_cast_column = next(
            (column for column in REWARD_SPELL_CAST_COLUMNS if column in quest_template_columns),
            None,
        )
        preflight.compatibility["reward_spell_cast_column"] = spell_cast_column
        if spell_cast_column is None:
            preflight.issues.append(
                TemplatePublishIssue(
                    path="reward_spell_cast_id",
                    message="No supported RewardSpellCast column was found in quest_template.",
                )
            )
        else:
            update_fields[spell_cast_column] = int(draft.reward_spell_cast_id)

    if draft.reward_spell_id is not None:
        spell_column = next((column for column in REWARD_SPELL_COLUMNS if column in quest_template_columns), None)
        preflight.compatibility["reward_spell_column"] = spell_column
        if spell_column is None:
            preflight.issues.append(
                TemplatePublishIssue(
                    path="reward_spell_id",
                    message="No supported RewardSpell column was found in quest_template.",
                )
            )
        else:
            update_fields[spell_column] = int(draft.reward_spell_id)

    for index, reward in enumerate(draft.reward_reputations, start=1):
        slot_key = f"slot_{index}"
        faction_column = f"RewardFactionId{index}" if f"RewardFactionId{index}" in quest_template_columns else None
        value_column = next(
            (
                column
                for column in (
                    f"RewardFactionValueIdOverride{index}",
                    f"RewardFactionValueId{index}",
                    f"RewardFactionValue{index}",
                )
                if column in quest_template_columns
            ),
            None,
        )
        preflight.compatibility["reputation_slots"][slot_key] = {
            "faction_column": faction_column,
            "value_column": value_column,
        }
        if faction_column is None or value_column is None:
            preflight.issues.append(
                TemplatePublishIssue(
                    path=f"reward_reputations[{index}]",
                    message=(
                        f"Quest schema does not expose compatible reputation reward columns for slot {index}. "
                        "Expected RewardFactionIdN and RewardFactionValueN / RewardFactionValueIdN / RewardFactionValueIdOverrideN."
                    ),
                )
            )
            continue
        update_fields[faction_column] = int(reward.faction_id)
        update_fields[value_column] = int(reward.value)

    preflight.update_fields = update_fields
    if update_fields:
        set_clause = ", ".join(f"`{column}` = {_sql_literal(value)}" for column, value in update_fields.items())
        preflight.sql_statements = [
            f"UPDATE `quest_template` SET {set_clause} WHERE `ID` = {int(draft.quest_id)};"
        ]
    return preflight


def load_rich_bounty_quest_draft(path: str | Path) -> RichBountyQuestDraft:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("draft"), dict):
        raw = raw["draft"]
    if not isinstance(raw, dict):
        raise ValueError("Quest template draft JSON must be an object.")

    reward = raw.get("reward") or {}
    reward_reputations = [
        ReputationReward(
            faction_id=int(item["faction_id"]),
            value=int(item["value"]),
        )
        for item in reward.get("reputations", [])
    ]

    return RichBountyQuestDraft(
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
        target_entry=int((raw.get("objective") or {})["target_entry"]),
        target_name=str((raw.get("objective") or {})["target_name"]),
        kill_count=int((raw.get("objective") or {})["kill_count"]),
        reward_money_copper=int(reward.get("money_copper", 0)),
        reward_item_entry=(int(reward["reward_item_entry"]) if reward.get("reward_item_entry") not in (None, "") else None),
        reward_item_name=(str(reward["reward_item_name"]) if reward.get("reward_item_name") not in (None, "") else None),
        reward_item_count=int(reward.get("reward_item_count", 1)),
        reward_experience=(int(reward["experience"]) if reward.get("experience") not in (None, "") else None),
        reward_spell_cast_id=(int(reward["reward_spell_cast_id"]) if reward.get("reward_spell_cast_id") not in (None, "") else None),
        reward_spell_id=(int(reward["reward_spell_id"]) if reward.get("reward_spell_id") not in (None, "") else None),
        reward_reputations=reward_reputations,
        start_npc_entry=(int(raw["start_npc_entry"]) if raw.get("start_npc_entry") not in (None, "") else None),
        end_npc_entry=(int(raw["end_npc_entry"]) if raw.get("end_npc_entry") not in (None, "") else None),
        grant_mode=str(raw.get("grant_mode") or "npc_start"),
        tags=[str(tag) for tag in raw.get("tags", [])],
        template_defaults={str(k): v for k, v in (raw.get("template_defaults") or {}).items()},
    )


def _sync_runtime(*, draft: BountyQuestDraft, settings: Settings, mode: str, runtime_sync_mode: str) -> RuntimeSyncResult:
    if mode != "apply":
        return RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=False,
            note="Dry-run mode does not touch the live runtime.",
        )

    enabled = runtime_sync_mode == "soap" or (runtime_sync_mode == "auto" and settings.soap_enabled)
    if not enabled:
        return RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=True,
            note="Runtime sync is disabled. Restart worldserver before testing the quest.",
        )

    if not settings.soap_user or not settings.soap_password:
        return RuntimeSyncResult(
            protocol="soap",
            enabled=True,
            overall_ok=False,
            restart_recommended=True,
            note="SOAP runtime sync was requested but WM_SOAP_USER / WM_SOAP_PASSWORD are not configured.",
        )

    client = SoapRuntimeClient(settings=settings)
    commands = build_default_quest_reload_commands(questgiver_entry=draft.questgiver_entry)
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
        restart_recommended=True,
        note=(
            "Quest rows were published and reload commands were sent. "
            "For new quests or objective-behavior changes, restart worldserver before serious testing."
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.template_publish")
    parser.add_argument("--draft-json", type=Path, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _render_summary(result: TemplateQuestPublishResult) -> str:
    lines = [
        f"mode: {result.mode}",
        f"applied: {str(result.applied).lower()}",
        f"base_preflight_ok: {str(bool(result.base_publish.get('preflight', {}).get('ok', False))).lower()}",
        f"base_validation_ok: {str(bool(result.base_publish.get('validation', {}).get('ok', False))).lower()}",
        f"extra_validation_ok: {str(bool(result.extra_validation.get('ok', False))).lower()}",
        f"extra_preflight_ok: {str(bool(result.extra_preflight.get('ok', False))).lower()}",
        f"runtime_sync.enabled: {str(bool(result.runtime_sync.get('enabled', False))).lower()}",
        f"runtime_sync.overall_ok: {str(bool(result.runtime_sync.get('overall_ok', False))).lower()}",
        "",
        "extra_reward_updates:",
    ]
    update_fields = result.extra_preflight.get("update_fields", {})
    if not update_fields:
        lines.append("- none")
    else:
        for key, value in update_fields.items():
            lines.append(f"- {key} = {value}")
    lines.extend(["", "extra_issues:"])
    issues = result.extra_preflight.get("issues", [])
    if not issues:
        lines.append("- none")
    else:
        for issue in issues:
            lines.append(f"- {issue.get('path')} | {issue.get('severity')} | {issue.get('message')}")
    if result.runtime_sync.get("note"):
        lines.extend(["", f"note: {result.runtime_sync.get('note')}"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    publisher = RichQuestTemplatePublisher(client=client, settings=settings)
    draft = load_rich_bounty_quest_draft(args.draft_json)
    result = publisher.publish(draft=draft, mode=args.mode, runtime_sync_mode=args.runtime_sync)
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
    return 0 if result.applied or (args.mode == "dry-run" and bool(result.base_publish.get("preflight", {}).get("ok", False)) and bool(result.extra_preflight.get("ok", False))) else 2


def _sql_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return _sql_string(str(value))


__all__ = [
    "ExtraRewardPreflight",
    "ReputationReward",
    "RichBountyQuestDraft",
    "RichQuestTemplatePublisher",
    "TemplatePublishIssue",
    "TemplateQuestPublishResult",
    "build_extra_reward_preflight",
    "load_rich_bounty_quest_draft",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
