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

    def resolve(self, entry: int) -> CreatureLookupResult:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT entry, name, subname, minlevel, maxlevel, faction, npcflag, type, family, rank, unit_class, gossip_menu_id "
                "FROM creature_template "
                f"WHERE entry = {int(entry)} LIMIT 1"
            ),
        )
        if not rows:
            raise ValueError(f"Creature entry {entry} was not found in creature_template.")

        row = rows[0]
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.generate_bounty")
    parser.add_argument("--questgiver-entry", type=int, required=True)
    parser.add_argument("--target-entry", type=int, required=True)
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

    questgiver = resolver.resolve(args.questgiver_entry)
    target = resolver.resolve(args.target_entry)

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


if __name__ == "__main__":
    sys.exit(main())
