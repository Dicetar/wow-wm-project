from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.quests.bounty import build_bounty_quest_draft
from wm.quests.generate_bounty import LiveCreatureResolver
from wm.quests.publish import QuestPublisher
from wm.refs import CreatureRef
from wm.refs import NpcRef
from wm.refs import PlayerRef
from wm.refs import QuestRef
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.store import ReactiveQuestStore
from wm.reserved.db_allocator import ReservedSlotDbAllocator


@dataclass(slots=True)
class ReactiveInstallResult:
    mode: str
    rule: dict[str, Any]
    quest_exists: bool
    quest_matches_reactive_shape: bool
    quest_publish: dict[str, Any] | None
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReactiveBountyInstaller:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        reactive_store: ReactiveQuestStore | None = None,
        slot_allocator: ReservedSlotDbAllocator | None = None,
        quest_publisher: QuestPublisher | None = None,
        resolver: LiveCreatureResolver | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.reactive_store = reactive_store or ReactiveQuestStore(client=client, settings=settings)
        self.slot_allocator = slot_allocator or ReservedSlotDbAllocator(client=client, settings=settings)
        self.quest_publisher = quest_publisher or QuestPublisher(client=client, settings=settings)
        self.resolver = resolver or LiveCreatureResolver(client=client, settings=settings)

    def install(self, *, rule: ReactiveQuestRule, mode: str) -> ReactiveInstallResult:
        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported install mode: {mode}")

        notes: list[str] = []
        if mode == "apply":
            self.reactive_store.upsert_rule(rule)
            notes.append(f"Upserted reactive quest rule `{rule.rule_key}`.")
        else:
            notes.append(f"Would upsert reactive quest rule `{rule.rule_key}`.")

        quest_state = self._load_quest_shape(rule.quest_id, expected_turn_in_npc_entry=rule.turn_in_npc_entry)
        quest_exists = quest_state["quest_exists"]
        quest_matches = quest_state["quest_matches_reactive_shape"]
        publish_payload: dict[str, Any] | None = None

        if quest_exists and quest_matches:
            notes.append(f"Quest {rule.quest_id} already exists with no starter row and ender {rule.turn_in_npc_entry}.")
        elif quest_exists and not quest_matches:
            notes.append(
                f"Quest {rule.quest_id} already exists but does not match the reactive direct-grant shape; leaving it unchanged."
            )
        else:
            draft = self._build_reactive_draft(rule)
            if mode == "apply":
                prepared = self.slot_allocator.ensure_slot_prepared(
                    entity_type="quest",
                    reserved_id=rule.quest_id,
                    arc_key=rule.rule_key,
                    character_guid=rule.player_guid_scope,
                    source_quest_id=rule.quest_id,
                    notes=[
                        f"reactive_rule:{rule.rule_key}",
                        "grant_mode:direct_quest_add",
                    ],
                )
                if prepared is None:
                    raise RuntimeError(
                        f"Reserved quest slot {rule.quest_id} was not found. Seed the range before installing the reactive quest."
                    )
                publish_result = self.quest_publisher.publish(draft=draft, mode="apply")
                publish_payload = publish_result.to_dict()
                notes.append(f"Published reusable reactive quest {rule.quest_id}.")
            else:
                publish_result = self.quest_publisher.publish(draft=draft, mode="dry-run")
                publish_payload = publish_result.to_dict()
                notes.append(f"Would publish reusable reactive quest {rule.quest_id} if the slot is staged.")

        return ReactiveInstallResult(
            mode=mode,
            rule=rule.to_dict(),
            quest_exists=quest_exists,
            quest_matches_reactive_shape=quest_matches,
            quest_publish=publish_payload,
            notes=notes,
        )

    def _build_reactive_draft(self, rule: ReactiveQuestRule):
        target_result = self.resolver.resolve(entry=rule.subject_entry)
        turn_in_result = self.resolver.resolve(entry=rule.turn_in_npc_entry)
        template_defaults = dict(
            self.resolver.fetch_template_defaults_for_questgiver(turn_in_result.entry)
        )
        template_defaults["SpecialFlags"] = int(template_defaults.get("SpecialFlags") or 0) | 1
        draft = build_bounty_quest_draft(
            quest_id=rule.quest_id,
            questgiver_entry=turn_in_result.entry,
            questgiver_name=turn_in_result.name,
            start_npc_entry=None,
            end_npc_entry=turn_in_result.entry,
            grant_mode="direct_quest_add",
            target_profile=target_result.profile,
            kill_count=rule.kill_threshold,
            reward_money_copper=max(0, int(self.settings.event_default_reward_money_copper)),
            template_defaults=template_defaults,
        )
        draft.quest_description = (
            f"Your recent assault on {target_result.name} has drawn attention. "
            f"Thin their numbers further, then report to {turn_in_result.name}."
        )
        draft.request_items_text = (
            f"Drive back {draft.objective.kill_count} {target_result.name}, then report to {turn_in_result.name}."
        )
        draft.offer_reward_text = (
            f"{turn_in_result.name} nods as you report in. "
            f"The kobold pressure eases for now, but stay ready."
        )
        return draft

    def _load_quest_shape(self, quest_id: int, *, expected_turn_in_npc_entry: int) -> dict[str, Any]:
        quest_rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=f"SELECT ID, LogTitle FROM quest_template WHERE ID = {int(quest_id)}",
        )
        starter_rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=f"SELECT id FROM creature_queststarter WHERE quest = {int(quest_id)} ORDER BY id",
        )
        ender_rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=f"SELECT id FROM creature_questender WHERE quest = {int(quest_id)} ORDER BY id",
        )
        addon_rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=f"SELECT ID, SpecialFlags FROM quest_template_addon WHERE ID = {int(quest_id)}",
        )
        repeatable = False
        if addon_rows:
            try:
                repeatable = (int(addon_rows[0].get("SpecialFlags") or 0) & 1) == 1
            except (TypeError, ValueError):
                repeatable = False
        return {
            "quest_exists": bool(quest_rows),
            "quest_rows": quest_rows,
            "starter_rows": starter_rows,
            "ender_rows": ender_rows,
            "quest_template_addon_rows": addon_rows,
            "quest_matches_reactive_shape": (
                bool(quest_rows)
                and not starter_rows
                and any(int(row.get("id") or 0) == int(expected_turn_in_npc_entry) for row in ender_rows)
                and repeatable
            ),
        }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install or refresh a reusable reactive bounty definition.")
    parser.add_argument("--rule-key", default="reactive_bounty:kobold_vermin")
    parser.add_argument("--player-guid", type=int, default=5406)
    parser.add_argument("--subject-entry", type=int, default=6)
    parser.add_argument("--quest-id", type=int, default=910000)
    parser.add_argument("--turn-in-npc-entry", type=int, default=197)
    parser.add_argument("--kill-threshold", type=int, default=4)
    parser.add_argument("--window-seconds", type=int, default=120)
    parser.add_argument("--post-reward-cooldown-seconds", type=int, default=60)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _render_summary(result: ReactiveInstallResult) -> str:
    lines = [
        f"mode: {result.mode}",
        f"rule_key: {result.rule.get('rule_key')}",
        f"quest_id: {result.rule.get('quest_id')}",
        f"quest_exists: {str(result.quest_exists).lower()}",
        f"quest_matches_reactive_shape: {str(result.quest_matches_reactive_shape).lower()}",
        "notes:",
    ]
    for note in result.notes:
        lines.append(f"- {note}")
    if result.quest_publish is not None:
        preflight = result.quest_publish.get("preflight", {})
        lines.extend(
            [
                "",
                f"quest_publish.preflight_ok: {str(bool(preflight.get('ok', False))).lower()}",
                f"quest_publish.applied: {str(bool(result.quest_publish.get('applied', False))).lower()}",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    installer = ReactiveBountyInstaller(client=client, settings=settings)
    reactive_store = ReactiveQuestStore(client=client, settings=settings)
    player_name = reactive_store.fetch_character_name(player_guid=int(args.player_guid))
    resolver = LiveCreatureResolver(client=client, settings=settings)
    subject = resolver.resolve(entry=int(args.subject_entry))
    turn_in = resolver.resolve(entry=int(args.turn_in_npc_entry))
    rule = ReactiveQuestRule(
        rule_key=str(args.rule_key),
        is_active=True,
        player_guid_scope=int(args.player_guid),
        subject_type="creature",
        subject_entry=int(args.subject_entry),
        trigger_event_type="kill",
        kill_threshold=int(args.kill_threshold),
        window_seconds=int(args.window_seconds),
        quest_id=int(args.quest_id),
        turn_in_npc_entry=int(args.turn_in_npc_entry),
        grant_mode="direct_quest_add",
        post_reward_cooldown_seconds=int(args.post_reward_cooldown_seconds),
        metadata={"installer": "wm.reactive.install_bounty"},
        notes=["reusable_reactive_bounty"],
        player_scope=PlayerRef(guid=int(args.player_guid), name=player_name),
        subject=CreatureRef(entry=subject.entry, name=subject.name),
        quest=QuestRef(id=int(args.quest_id), title=f"Bounty: {subject.name}"),
        turn_in_npc=NpcRef(entry=turn_in.entry, name=turn_in.name),
    )
    result = installer.install(rule=rule, mode=args.mode)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
