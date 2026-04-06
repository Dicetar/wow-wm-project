from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.quests.bounty import build_bounty_quest_draft
from wm.targets.resolver import (
    TargetProfile,
    decode_creature_type,
    decode_family,
    decode_faction_label,
    decode_npc_flags,
    decode_rank,
    decode_unit_class,
)


@dataclass(slots=True)
class CreatureLookupResult:
    entry: int
    name: str
    subname: str | None
    profile: TargetProfile


class LiveCreatureResolver:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def resolve(self, *, entry: int | None = None, name: str | None = None) -> CreatureLookupResult:
        if entry is None and not name:
            raise ValueError("Provide either an entry or a creature name.")

        if entry is not None:
            rows = self._query_rows(
                "SELECT `entry`, `name`, `subname`, `minlevel`, `maxlevel`, `faction`, `npcflag`, `type`, `family`, `rank`, `unit_class`, `gossip_menu_id` "
                "FROM `creature_template` "
                f"WHERE `entry` = {int(entry)} LIMIT 1"
            )
            if not rows:
                raise ValueError(f"Creature entry {entry} was not found in creature_template.")
            return self._build_result(rows[0])

        assert name is not None
        exact_rows = self._query_rows(
            "SELECT `entry`, `name`, `subname`, `minlevel`, `maxlevel`, `faction`, `npcflag`, `type`, `family`, `rank`, `unit_class`, `gossip_menu_id` "
            "FROM `creature_template` "
            f"WHERE `name` = {_sql_string(name)} ORDER BY `entry` LIMIT 10"
        )
        if len(exact_rows) == 1:
            return self._build_result(exact_rows[0])
        if len(exact_rows) > 1:
            raise ValueError(
                "Multiple exact creature matches found for name "
                f"{name!r}: {self._render_candidates(exact_rows)}"
            )

        like_rows = self._query_rows(
            "SELECT `entry`, `name`, `subname`, `minlevel`, `maxlevel`, `faction`, `npcflag`, `type`, `family`, `rank`, `unit_class`, `gossip_menu_id` "
            "FROM `creature_template` "
            f"WHERE `name` LIKE {_sql_string('%' + name + '%')} ORDER BY `name`, `entry` LIMIT 10"
        )
        if len(like_rows) == 1:
            return self._build_result(like_rows[0])
        if not like_rows:
            raise ValueError(f"No creature name match found for {name!r}.")
        raise ValueError(
            "Multiple partial creature matches found for name "
            f"{name!r}: {self._render_candidates(like_rows)}"
        )

    def _query_rows(self, sql: str) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=sql,
        )

    def _build_result(self, row: dict[str, Any]) -> CreatureLookupResult:
        profile = TargetProfile(
            entry=int(row["entry"]),
            name=str(row.get("name") or ""),
            subname=row.get("subname"),
            level_min=int(row.get("minlevel") or 0),
            level_max=int(row.get("maxlevel") or 0),
            faction_id=int(row.get("faction") or 0),
            faction_label=decode_faction_label(int(row.get("faction") or 0)),
            mechanical_type=decode_creature_type(int(row.get("type") or 0)),
            family=decode_family(int(row.get("family") or 0)),
            rank=decode_rank(int(row.get("rank") or 0)),
            unit_class=decode_unit_class(int(row.get("unit_class") or 0)),
            service_roles=decode_npc_flags(int(row.get("npcflag") or 0)),
            has_gossip_menu=int(row.get("gossip_menu_id") or 0) > 0,
        )
        return CreatureLookupResult(
            entry=profile.entry,
            name=profile.name,
            subname=profile.subname,
            profile=profile,
        )

    @staticmethod
    def _render_candidates(rows: list[dict[str, Any]]) -> str:
        return ", ".join(
            f"{row.get('entry')}:{row.get('name')}" for row in rows
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.generate_bounty")

    questgiver_group = parser.add_mutually_exclusive_group(required=True)
    questgiver_group.add_argument("--questgiver-entry", type=int)
    questgiver_group.add_argument("--questgiver-name")

    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--target-entry", type=int)
    target_group.add_argument("--target-name")

    parser.add_argument("--quest-id", type=int, required=True)
    parser.add_argument("--kill-count", type=int, default=8)
    parser.add_argument("--reward-money-copper", type=int, default=1200)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("artifacts/generated_bounty.json"),
        help="Where to write the generated draft JSON.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print only a compact summary instead of the full draft payload.",
    )
    return parser


def _render_summary(payload: dict[str, Any], output_path: Path) -> str:
    draft = payload.get("draft", {})
    objective = draft.get("objective", {})
    lines = [
        f"quest_id: {draft.get('quest_id')}",
        f"title: {draft.get('title')}",
        f"questgiver_entry: {draft.get('questgiver_entry')} | {draft.get('questgiver_name')}",
        f"target_entry: {objective.get('target_entry')} | {objective.get('target_name')}",
        f"kill_count: {objective.get('kill_count')}",
        f"output_json: {output_path}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    client = MysqlCliClient()
    resolver = LiveCreatureResolver(client=client, settings=settings)

    questgiver = resolver.resolve(entry=args.questgiver_entry, name=args.questgiver_name)
    target = resolver.resolve(entry=args.target_entry, name=args.target_name)

    draft = build_bounty_quest_draft(
        quest_id=args.quest_id,
        questgiver_entry=questgiver.entry,
        questgiver_name=questgiver.name,
        target_profile=target.profile,
        kill_count=args.kill_count,
        reward_money_copper=args.reward_money_copper,
    )

    payload = {
        "draft": draft.to_dict(),
        "generation_context": {
            "questgiver_profile": questgiver.profile.to_dict(),
            "target_profile": target.profile.to_dict(),
        },
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.summary:
        print(_render_summary(payload, args.output_json))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _sql_string(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


if __name__ == "__main__":
    sys.exit(main())
