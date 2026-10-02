from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.quests.models import BountyQuestDraft, BountyQuestReward, DeliveryQuestObjective
from wm.quests.validator import validate_bounty_quest_draft


def build_delivery_quest_draft(
    *, quest_id: int, quest_level: int, min_level: int, questgiver_entry: int,
    questgiver_name: str, item_entry: int, item_name: str, item_count: int,
    location: str, reward_money_copper: int,
) -> BountyQuestDraft:
    if not location.strip():
        raise ValueError("Provide a concrete turn-in location.")
    directions = (
        f"Bring {item_count} {item_name} to {questgiver_name} at {location.strip()}. "
        "Items you already own count. The requested items are consumed at turn-in."
    )
    draft = BountyQuestDraft(
        quest_id=quest_id, quest_level=quest_level, min_level=min_level,
        questgiver_entry=questgiver_entry, questgiver_name=questgiver_name,
        start_npc_entry=questgiver_entry, end_npc_entry=questgiver_entry,
        title=f"A Request for {item_name}",
        quest_description=(
            f"{questgiver_name} has work waiting, but needs a fresh supply of {item_name}. "
            "A reliable supplier will be paid for the delivery."
        ),
        objective_text=f"Deliver {item_count} {item_name}.",
        request_items_text=directions,
        offer_reward_text="These will do nicely. Here is your payment.",
        objective=DeliveryQuestObjective(item_entry=item_entry, item_name=item_name, item_count=item_count),
        reward=BountyQuestReward(money_copper=reward_money_copper),
        template_defaults={"QuestType": 2},
        tags=["wm", "delivery"],
    )
    validation = validate_bounty_quest_draft(draft)
    if not validation.ok:
        raise ValueError("; ".join(f"{issue.path}: {issue.message}" for issue in validation.errors))
    return draft


def generate_delivery(*, args: argparse.Namespace, client: MysqlCliClient, settings: Settings) -> dict[str, Any]:
    def query(sql: str) -> list[dict[str, Any]]:
        return client.query(
            host=settings.world_db_host, port=settings.world_db_port,
            user=settings.world_db_user, password=settings.world_db_password,
            database=settings.world_db_name, sql=sql,
        )

    items = query(f"SELECT entry, name, maxcount, bonding FROM item_template WHERE entry = {int(args.item_entry)}")
    if not items:
        raise ValueError(f"Item {args.item_entry} does not exist in item_template.")
    item = items[0]
    if int(item.get("bonding") or 0) == 4:
        raise ValueError("Use ordinary materials, not quest-bound items; the core may remove all copies of quest-bound items at turn-in.")
    maxcount = int(item.get("maxcount") or 0)
    if maxcount > 0 and args.item_count > maxcount:
        raise ValueError(f"Requested count exceeds the item's unique ownership limit ({maxcount}).")
    npcs = query(f"SELECT entry, name, npcflag FROM creature_template WHERE entry = {int(args.questgiver_entry)}")
    if not npcs or not int(npcs[0].get("npcflag") or 0) & 2:
        raise ValueError("Choose an existing NPC with the questgiver flag.")
    npc = npcs[0]
    spawns = query(
        "SELECT guid, map, position_x, position_y, position_z, phaseMask FROM creature "
        f"WHERE id1 = {int(args.questgiver_entry)} OR id2 = {int(args.questgiver_entry)} "
        f"OR id3 = {int(args.questgiver_entry)} ORDER BY guid LIMIT 5"
    )
    if not spawns:
        raise ValueError("Questgiver has no persistent spawn; place it before authoring this NPC-start delivery.")
    draft = build_delivery_quest_draft(
        quest_id=args.quest_id, quest_level=args.quest_level, min_level=args.min_level,
        questgiver_entry=int(npc["entry"]), questgiver_name=str(npc["name"]),
        item_entry=int(item["entry"]), item_name=str(item["name"]), item_count=args.item_count,
        location=args.location, reward_money_copper=args.reward_money_copper,
    )
    return {
        "draft": draft.to_dict(),
        "generation_context": {
            "item": item, "questgiver": npc, "questgiver_spawn_candidates": spawns,
            "turn_in_location": args.location,
            "location_source": "operator", "runtime_verified": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.generate_delivery")
    parser.add_argument("--quest-id", type=int, required=True)
    parser.add_argument("--questgiver-entry", type=int, required=True)
    parser.add_argument("--item-entry", type=int, required=True)
    parser.add_argument("--item-count", type=int, required=True)
    parser.add_argument("--quest-level", type=int, required=True)
    parser.add_argument("--min-level", type=int, default=1)
    parser.add_argument("--location", required=True)
    parser.add_argument("--reward-money-copper", type=int, default=1000)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = generate_delivery(args=args, client=MysqlCliClient(), settings=Settings.from_env())
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Delivery draft failed: {exc}\n")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.summary:
        draft = payload["draft"]
        print(f"quest_id: {draft['quest_id']}\nobjective_kind: deliver\ndirections: {draft['request_items_text']}\noutput_json: {args.output_json}")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
