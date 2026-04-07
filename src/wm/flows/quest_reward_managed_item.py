from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.items.publish import ItemPublisher, _demo_draft as _demo_item_draft, load_managed_item_draft
from wm.items.rollback import _sync_runtime as _sync_item_runtime
from wm.quests.edit_live import QuestLiveEditor


@dataclass(slots=True)
class QuestRewardManagedItemFlowResult:
    mode: str
    item_publish: dict[str, Any]
    item_runtime_sync: dict[str, Any]
    quest_edit: dict[str, Any]
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.flows.quest_reward_managed_item")
    parser.add_argument("--quest-id", type=int, required=True)
    parser.add_argument("--item-draft-json", type=Path)
    parser.add_argument("--item-demo", action="store_true")
    parser.add_argument("--reward-item-count", type=int, default=1)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--item-runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument("--item-soap-command", action="append", default=[])
    parser.add_argument("--quest-runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument("--output-json", type=Path)
    return parser


def _render_summary(result: QuestRewardManagedItemFlowResult) -> str:
    item_publish = result.item_publish
    quest_edit = result.quest_edit
    return "\n".join(
        [
            f"mode: {result.mode}",
            f"item_publish.applied: {str(bool(item_publish.get('applied', False))).lower()}",
            f"item_publish.validation.ok: {str(bool(item_publish.get('validation', {}).get('ok', False))).lower()}",
            f"item_publish.preflight.ok: {str(bool(item_publish.get('preflight', {}).get('ok', False))).lower()}",
            f"quest_edit.applied: {str(bool(quest_edit.get('applied', False))).lower()}",
            f"quest_edit.ok: {str(bool(quest_edit.get('ok', False))).lower()}",
            f"ok: {str(bool(result.ok)).lower()}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.item_demo and args.item_draft_json is None:
        raise SystemExit("Provide --item-draft-json PATH or use --item-demo.")

    settings = Settings.from_env()
    client = MysqlCliClient()
    item_draft = _demo_item_draft() if args.item_demo else load_managed_item_draft(args.item_draft_json)

    item_publisher = ItemPublisher(client=client, settings=settings)
    item_publish_result = item_publisher.publish(draft=item_draft, mode=args.mode)
    item_runtime_sync = _sync_item_runtime(
        settings=settings,
        mode=args.mode,
        runtime_sync_mode=args.item_runtime_sync,
        soap_commands=[str(command) for command in args.item_soap_command],
    )

    quest_editor = QuestLiveEditor(client=client, settings=settings)
    quest_edit_result = quest_editor.edit(
        quest_id=args.quest_id,
        title=None,
        reward_money_copper=None,
        reward_item_entry=int(item_draft.item_entry),
        reward_item_count=int(args.reward_item_count),
        clear_reward_item=False,
        reward_xp=None,
        offer_reward_text=None,
        runtime_sync_mode=args.quest_runtime_sync,
        apply=args.mode == "apply",
    )

    ok = bool(
        item_publish_result.validation.get("ok", False)
        and item_publish_result.preflight.get("ok", False)
        and item_runtime_sync.overall_ok
        and quest_edit_result.ok
        and bool(quest_edit_result.runtime_sync.get("overall_ok", True))
    )
    result = QuestRewardManagedItemFlowResult(
        mode=args.mode,
        item_publish=item_publish_result.to_dict(),
        item_runtime_sync=item_runtime_sync.to_dict(),
        quest_edit=quest_edit_result.to_dict(),
        ok=ok,
    )
    raw = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    print(_render_summary(result))
    if args.output_json is not None:
        print("")
        print(f"output_json: {args.output_json}")
    return 0 if result.ok else 2


if __name__ == "__main__":
    sys.exit(main())
