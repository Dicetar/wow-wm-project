from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
import subprocess
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.reactive.store import ReactiveQuestStore


@dataclass(slots=True)
class QuestPurgeEntry:
    quest_id: int
    status: str
    protected_by_rule: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class QuestPurgeRangeResult:
    mode: str
    start_id: int
    end_id: int
    include_reactive: bool
    entries: list[QuestPurgeEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "start_id": self.start_id,
            "end_id": self.end_id,
            "include_reactive": self.include_reactive,
            "entries": [entry.to_dict() for entry in self.entries],
        }


class QuestPurgeRangeManager:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        reactive_store: ReactiveQuestStore | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.reactive_store = reactive_store or ReactiveQuestStore(client=client, settings=settings)

    def purge_range(
        self,
        *,
        start_id: int,
        end_id: int,
        mode: str,
        include_reactive: bool,
    ) -> QuestPurgeRangeResult:
        if start_id > end_id:
            raise ValueError("start_id must be less than or equal to end_id")

        protected_rules = {
            rule.quest_id: rule.rule_key
            for rule in self.reactive_store.list_active_rules()
        }
        result = QuestPurgeRangeResult(
            mode=mode,
            start_id=int(start_id),
            end_id=int(end_id),
            include_reactive=bool(include_reactive),
        )

        for quest_id in range(int(start_id), int(end_id) + 1):
            protected_rule = protected_rules.get(quest_id)
            if protected_rule is not None and not include_reactive:
                result.entries.append(
                    QuestPurgeEntry(
                        quest_id=quest_id,
                        status="skipped_protected",
                        protected_by_rule=protected_rule,
                        notes=["Reactive reusable quest IDs are skipped by default."],
                    )
                )
                continue

            entry = QuestPurgeEntry(quest_id=quest_id, status="planned")
            if mode == "apply":
                self._purge_quest(quest_id=quest_id)
                entry.status = "purged"
                entry.notes.append("Quest rows were removed and any reserved slot was retired.")
            else:
                entry.notes.append("Dry-run only; no quest rows were removed.")
            result.entries.append(entry)

        return result

    def _purge_quest(self, *, quest_id: int) -> None:
        statements = [
            f"DELETE FROM creature_queststarter WHERE quest = {int(quest_id)};",
            f"DELETE FROM creature_questender WHERE quest = {int(quest_id)};",
            f"DELETE FROM quest_offer_reward WHERE ID = {int(quest_id)};",
            f"DELETE FROM quest_request_items WHERE ID = {int(quest_id)};",
            f"DELETE FROM quest_template_addon WHERE ID = {int(quest_id)};",
            f"DELETE FROM quest_template WHERE ID = {int(quest_id)};",
            (
                "UPDATE wm_reserved_slot SET "
                "SlotStatus = 'retired', ArcKey = NULL, CharacterGUID = NULL, SourceQuestID = NULL, NotesJSON = NULL "
                "WHERE EntityType = 'quest' "
                f"AND ReservedID = {int(quest_id)};"
            ),
        ]
        for statement in statements:
            try:
                self._execute_world(statement)
            except MysqlCliError as exc:
                if "doesn't exist" in str(exc):
                    continue
                raise

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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.purge_range")
    parser.add_argument("--start-id", type=int, required=True)
    parser.add_argument("--end-id", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--include-reactive", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _render_summary(result: QuestPurgeRangeResult) -> str:
    lines = [
        f"mode: {result.mode}",
        f"range: {result.start_id}-{result.end_id}",
        f"include_reactive: {str(result.include_reactive).lower()}",
        "entries:",
    ]
    if not result.entries:
        lines.append("- none")
    else:
        for entry in result.entries:
            if entry.protected_by_rule:
                lines.append(
                    f"- quest_id={entry.quest_id} status={entry.status} protected_by_rule={entry.protected_by_rule}"
                )
            else:
                lines.append(f"- quest_id={entry.quest_id} status={entry.status}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    manager = QuestPurgeRangeManager(client=client, settings=settings)
    result = manager.purge_range(
        start_id=args.start_id,
        end_id=args.end_id,
        mode=args.mode,
        include_reactive=args.include_reactive,
    )
    payload = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload, encoding="utf-8")
    if args.summary or args.output_json is not None:
        print(_render_summary(result))
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
