from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient

IMPORTANT_FIELDS = [
    "ID",
    "LogTitle",
    "QuestType",
    "Type",
    "QuestLevel",
    "MinLevel",
    "QuestSortID",
    "ZoneOrSort",
    "QuestInfoID",
    "Flags",
    "QuestFlags",
    "SpecialFlags",
    "Method",
    "QuestMethod",
    "SuggestedPlayers",
    "RequiredNpcOrGo1",
    "RequiredNpcOrGoCount1",
    "ReqCreatureOrGOId1",
    "ReqCreatureOrGOCount1",
    "ObjectiveText1",
    "Objectives",
    "RewardMoney",
    "RewardItem1",
    "RewardAmount1",
]


class QuestInspector:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def inspect_quest(self, quest_id: int) -> dict[str, Any]:
        columns = self._quest_template_columns()
        selected = [column for column in IMPORTANT_FIELDS if column in columns]
        if not selected:
            raise ValueError("No known quest_template fields were found to inspect.")

        template_rows = self._query_world(
            "SELECT " + ", ".join(f"`{column}`" for column in selected) + " "
            "FROM `quest_template` "
            f"WHERE `ID` = {int(quest_id)} LIMIT 1"
        )
        if not template_rows:
            raise ValueError(f"Quest {quest_id} was not found in quest_template.")

        result: dict[str, Any] = {
            "quest_id": quest_id,
            "quest_template": template_rows[0],
            "creature_queststarter": self._query_world(
                "SELECT * FROM `creature_queststarter` "
                f"WHERE `quest` = {int(quest_id)}"
            ),
            "creature_questender": self._query_world(
                "SELECT * FROM `creature_questender` "
                f"WHERE `quest` = {int(quest_id)}"
            ),
        }

        table_presence = self._table_presence({"quest_offer_reward", "quest_request_items"})
        if table_presence.get("quest_offer_reward", False):
            result["quest_offer_reward"] = self._query_world(
                "SELECT * FROM `quest_offer_reward` "
                f"WHERE `ID` = {int(quest_id)}"
            )
        if table_presence.get("quest_request_items", False):
            result["quest_request_items"] = self._query_world(
                "SELECT * FROM `quest_request_items` "
                f"WHERE `ID` = {int(quest_id)}"
            )
        return result

    def first_started_quest_for_npc(self, npc_entry: int) -> int | None:
        rows = self._query_world(
            "SELECT `quest` FROM `creature_queststarter` "
            f"WHERE `id` = {int(npc_entry)} ORDER BY `quest` LIMIT 1"
        )
        if not rows:
            return None
        return int(rows[0]["quest"])

    def compare(self, left_quest_id: int, right_quest_id: int) -> dict[str, Any]:
        left = self.inspect_quest(left_quest_id)
        right = self.inspect_quest(right_quest_id)

        left_template = left["quest_template"]
        right_template = right["quest_template"]
        diff: list[dict[str, Any]] = []
        for field_name in sorted(set(left_template.keys()) | set(right_template.keys())):
            left_value = left_template.get(field_name)
            right_value = right_template.get(field_name)
            if left_value != right_value:
                diff.append(
                    {
                        "field": field_name,
                        "left": left_value,
                        "right": right_value,
                    }
                )

        return {
            "left_quest_id": left_quest_id,
            "right_quest_id": right_quest_id,
            "left_title": left_template.get("LogTitle"),
            "right_title": right_template.get("LogTitle"),
            "template_diff": diff,
            "left_starter_rows": left.get("creature_queststarter", []),
            "right_starter_rows": right.get("creature_queststarter", []),
            "left_ender_rows": left.get("creature_questender", []),
            "right_ender_rows": right.get("creature_questender", []),
            "left_offer_reward": left.get("quest_offer_reward", []),
            "right_offer_reward": right.get("quest_offer_reward", []),
            "left_request_items": left.get("quest_request_items", []),
            "right_request_items": right.get("quest_request_items", []),
        }

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


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_list(values: set[str]) -> str:
    return ", ".join(_sql_string(value) for value in sorted(values))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.inspect")
    parser.add_argument("--quest-id", type=int, required=True, help="Generated / target quest ID to inspect.")
    parser.add_argument("--starter-entry", type=int, help="NPC entry to auto-pick a known-good starter quest for comparison.")
    parser.add_argument("--compare-to-quest-id", type=int, help="Explicit known-good quest ID to compare against.")
    parser.add_argument("--summary", action="store_true", help="Print compact text instead of full JSON.")
    parser.add_argument("--output-json", type=Path, help="Write the full comparison payload to a file.")
    return parser


def _render_summary(payload: dict[str, Any]) -> str:
    lines = [
        f"left_quest_id: {payload.get('left_quest_id')} | {payload.get('left_title')}",
        f"right_quest_id: {payload.get('right_quest_id')} | {payload.get('right_title')}",
        "",
        "template_diff:",
    ]
    diffs = payload.get("template_diff", [])
    if not diffs:
        lines.append("- none")
    else:
        for row in diffs:
            lines.append(f"- {row.get('field')}: left={row.get('left')} | right={row.get('right')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    inspector = QuestInspector(client=client, settings=settings)

    compare_to_quest_id = args.compare_to_quest_id
    if compare_to_quest_id is None:
        if args.starter_entry is None:
            raise SystemExit("Provide --compare-to-quest-id or --starter-entry.")
        compare_to_quest_id = inspector.first_started_quest_for_npc(args.starter_entry)
        if compare_to_quest_id is None:
            raise SystemExit(f"No started quest found for NPC entry {args.starter_entry}.")

    payload = inspector.compare(compare_to_quest_id, args.quest_id)
    raw = json.dumps(payload, indent=2, ensure_ascii=False)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")

    if args.summary or args.output_json is not None:
        print(_render_summary(payload))
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
