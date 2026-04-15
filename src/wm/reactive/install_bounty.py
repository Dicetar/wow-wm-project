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
from wm.runtime_sync import SoapRuntimeClient
from wm.runtime_sync import build_default_quest_reload_commands
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
        draft = self._build_reactive_draft(rule)
        if mode == "apply":
            self.reactive_store.upsert_rule(rule)
            notes.append(f"Upserted reactive quest rule `{rule.rule_key}`.")
        else:
            notes.append(f"Would upsert reactive quest rule `{rule.rule_key}`.")

        quest_state = self._load_quest_shape(draft=draft, expected_turn_in_npc_entry=rule.turn_in_npc_entry)
        quest_exists = quest_state["quest_exists"]
        quest_matches = quest_state["quest_matches_reactive_shape"]
        publish_payload: dict[str, Any] | None = None

        if quest_exists and quest_matches:
            notes.append(
                f"Quest {rule.quest_id} already exists with matching reactive content and ender {rule.turn_in_npc_entry}."
            )
        else:
            if quest_exists and not quest_matches:
                notes.append(
                    f"Quest {rule.quest_id} already exists but does not match the reactive target; refreshing it."
                )
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
                if (
                    not publish_result.applied
                    and quest_exists
                    and not quest_matches
                    and self._active_slot_refresh_needed(publish_payload)
                ):
                    self._apply_sql_plan(publish_payload.get("sql_plan"))
                    self._sync_reserved_slot(rule=rule)
                    self._reload_runtime_for_quest(rule=rule)
                    publish_payload["applied"] = True
                    publish_payload["live_refresh_applied"] = True
                    notes.append(f"Refreshed active reactive quest {rule.quest_id} in place.")
                elif publish_result.applied:
                    self._reload_runtime_for_quest(rule=rule)
                    notes.append(f"Requested runtime reload for reactive quest {rule.quest_id}.")
                notes.append(f"Published reusable reactive quest {rule.quest_id}.")
            else:
                publish_result = self.quest_publisher.publish(
                    draft=draft,
                    mode="dry-run",
                    allow_free_reserved_slot_preview=True,
                )
                publish_payload = publish_result.to_dict()
                notes.append(f"Would stage and publish reusable reactive quest {rule.quest_id} in apply mode.")

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
        target_name = _str_or_none(rule.metadata.get("objective_target_name")) or target_result.name
        quest_title = _str_or_none(rule.metadata.get("quest_title")) or f"Bounty: {target_name}"
        reward_item_entry = _int_or_none(rule.metadata.get("reward_item_entry"))
        reward_item_name = _str_or_none(rule.metadata.get("reward_item_name"))
        reward_item_count = _int_or_none(rule.metadata.get("reward_item_count")) or 1
        reward_xp_difficulty = _int_or_none(rule.metadata.get("reward_xp_difficulty"))
        reward_spell_id = _int_or_none(rule.metadata.get("reward_spell_id"))
        reward_spell_display_id = _int_or_none(rule.metadata.get("reward_spell_display_id"))
        reward_reputations = _reward_reputations_from_value(rule.metadata.get("reward_reputations"))
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
            target_name=target_name,
            title=quest_title,
            kill_count=rule.kill_threshold,
            reward_money_copper=max(0, int(self.settings.event_default_reward_money_copper)),
            reward_item_entry=reward_item_entry,
            reward_item_name=reward_item_name,
            reward_item_count=reward_item_count,
            reward_xp_difficulty=reward_xp_difficulty,
            reward_spell_id=reward_spell_id,
            reward_spell_display_id=reward_spell_display_id,
            reward_reputations=reward_reputations,
            template_defaults=template_defaults,
        )
        draft.quest_description = (
            f"Your recent assault on {target_name} has drawn attention. "
            f"Thin their numbers further, then report to {turn_in_result.name}."
        )
        draft.request_items_text = (
            f"Drive back {draft.objective.kill_count} {target_name}, then report to {turn_in_result.name}."
        )
        draft.offer_reward_text = (
            f"{turn_in_result.name} nods as you report in. "
            f"The pressure from {target_name} eases for now, but stay ready."
        )
        return draft

    def _load_quest_shape(self, *, draft, expected_turn_in_npc_entry: int) -> dict[str, Any]:
        snapshot = self.quest_publisher.capture_snapshot_preview(draft)
        preflight = self.quest_publisher.preflight(draft)
        compatibility = getattr(preflight, "compatibility", {}) or {}
        quest_rows = list(snapshot.get("quest_template", []) or [])
        starter_rows = list(snapshot.get("creature_queststarter", []) or [])
        ender_rows = list(snapshot.get("creature_questender", []) or [])
        addon_rows = list(snapshot.get("quest_template_addon", []) or [])
        offer_reward_rows = list(snapshot.get("quest_offer_reward", []) or [])
        request_items_rows = list(snapshot.get("quest_request_items", []) or [])
        repeatable = False
        if addon_rows:
            try:
                repeatable = (int(addon_rows[0].get("SpecialFlags") or 0) & 1) == 1
            except (TypeError, ValueError):
                repeatable = False
        topology_matches = (
            bool(quest_rows)
            and not starter_rows
            and any(int(row.get("id") or 0) == int(expected_turn_in_npc_entry) for row in ender_rows)
            and repeatable
        )
        content_matches = topology_matches and self._snapshot_matches_draft(
            snapshot=snapshot,
            compatibility=compatibility,
            draft=draft,
        )
        return {
            "quest_exists": bool(quest_rows),
            "quest_rows": quest_rows,
            "starter_rows": starter_rows,
            "ender_rows": ender_rows,
            "quest_template_addon_rows": addon_rows,
            "quest_offer_reward_rows": offer_reward_rows,
            "quest_request_items_rows": request_items_rows,
            "quest_matches_reactive_topology": topology_matches,
            "quest_matches_reactive_content": content_matches,
            "compatibility": compatibility,
            "quest_matches_reactive_shape": (
                topology_matches
                and content_matches
            ),
        }

    def _snapshot_matches_draft(
        self,
        *,
        snapshot: dict[str, Any],
        compatibility: dict[str, Any],
        draft,
    ) -> bool:
        quest_rows = list(snapshot.get("quest_template", []) or [])
        if not quest_rows:
            return False
        row = quest_rows[0]
        if _normalized_text(row.get("LogTitle")) != _normalized_text(draft.title):
            return False
        if "LogDescription" in row and _normalized_text(row.get("LogDescription")) != _normalized_text(draft.request_items_text):
            return False
        if "QuestDescription" in row and _normalized_text(row.get("QuestDescription")) != _normalized_text(draft.quest_description):
            return False
        if "Details" in row and _normalized_text(row.get("Details")) != _normalized_text(draft.quest_description):
            return False
        if "QuestCompletionLog" in row and _normalized_text(row.get("QuestCompletionLog")) != _normalized_text(draft.request_items_text):
            return False
        if "ObjectiveText1" in row and _normalized_text(row.get("ObjectiveText1")) != _normalized_text(draft.objective_text):
            return False
        if "Objectives" in row and _normalized_text(row.get("Objectives")) != _normalized_text(draft.objective_text):
            return False
        if "RequiredNpcOrGo1" in row and _int_or_none(row.get("RequiredNpcOrGo1")) != int(draft.objective.target_entry):
            return False
        if "RequiredNpcOrGoCount1" in row and _int_or_none(row.get("RequiredNpcOrGoCount1")) != int(draft.objective.kill_count):
            return False
        if "RewardMoney" in row and _int_or_none(row.get("RewardMoney")) != int(draft.reward.money_copper):
            return False
        if "RewardItem1" in row and _int_or_none(row.get("RewardItem1")) != int(draft.reward.reward_item_entry or 0):
            return False
        if "RewardAmount1" in row and _int_or_none(row.get("RewardAmount1")) != int(
            draft.reward.reward_item_count if draft.reward.reward_item_entry is not None else 0
        ):
            return False
        if "RewardSpell" in row and _int_or_none(row.get("RewardSpell")) != int(draft.reward.reward_spell_id or 0):
            return False
        if "RewardDisplaySpell" in row and _int_or_none(row.get("RewardDisplaySpell")) != int(
            draft.reward.reward_spell_display_id or 0
        ):
            return False
        if (
            draft.reward.reward_xp_difficulty is not None
            and "RewardXPDifficulty" in row
            and _int_or_none(row.get("RewardXPDifficulty")) != int(draft.reward.reward_xp_difficulty)
        ):
            return False
        for index, reward in enumerate(draft.reward.reward_reputations, start=1):
            faction_column = f"RewardFactionID{index}"
            value_column = "RewardFactionOverride{index}".format(index=index)
            if faction_column in row and _int_or_none(row.get(faction_column)) != int(reward.faction_id):
                return False
            if value_column in row and _int_or_none(row.get(value_column)) != int(reward.value):
                return False

        if compatibility.get("offer_reward_text_supported", False):
            if "OfferRewardText" in row:
                if _normalized_text(row.get("OfferRewardText")) != _normalized_text(draft.offer_reward_text):
                    return False
            else:
                offer_reward_rows = list(snapshot.get("quest_offer_reward", []) or [])
                if not offer_reward_rows:
                    return False
                if _normalized_text(offer_reward_rows[0].get("RewardText")) != _normalized_text(draft.offer_reward_text):
                    return False

        if compatibility.get("request_items_text_supported", False):
            if "RequestItemsText" in row:
                if _normalized_text(row.get("RequestItemsText")) != _normalized_text(draft.request_items_text):
                    return False
            else:
                request_items_rows = list(snapshot.get("quest_request_items", []) or [])
                if not request_items_rows:
                    return False
                if _normalized_text(request_items_rows[0].get("CompletionText")) != _normalized_text(draft.request_items_text):
                    return False

        return True

    def _active_slot_refresh_needed(self, publish_payload: dict[str, Any] | None) -> bool:
        if not isinstance(publish_payload, dict):
            return False
        preflight = publish_payload.get("preflight")
        if not isinstance(preflight, dict):
            return False
        issues = preflight.get("issues")
        if not isinstance(issues, list):
            return False
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            if str(issue.get("path") or "") != "reserved_slot.status":
                continue
            if "already active" in str(issue.get("message") or ""):
                return True
        return False

    def _apply_sql_plan(self, sql_plan: dict[str, Any] | None) -> None:
        if not isinstance(sql_plan, dict):
            raise RuntimeError("Quest publish fallback did not include an SQL plan.")
        statements = sql_plan.get("statements")
        if not isinstance(statements, list):
            raise RuntimeError("Quest publish fallback SQL plan is missing statements.")
        for statement in statements:
            sql = str(statement or "").strip()
            if not sql or sql.startswith("--"):
                continue
            self._execute_world(sql)

    def _sync_reserved_slot(self, *, rule: ReactiveQuestRule) -> None:
        notes_json = json.dumps(
            [
                f"reactive_rule:{rule.rule_key}",
                f"grant_mode:{rule.grant_mode}",
            ],
            ensure_ascii=False,
        ).replace("'", "''")
        rule_key = str(rule.rule_key).replace("'", "''")
        sql = (
            "UPDATE wm_reserved_slot SET "
            "SlotStatus = 'active', "
            f"ArcKey = '{rule_key}', "
            f"CharacterGUID = {int(rule.player_guid_scope or 0)}, "
            f"SourceQuestID = {int(rule.quest_id)}, "
            f"NotesJSON = '{notes_json}' "
            "WHERE EntityType = 'quest' "
            f"AND ReservedID = {int(rule.quest_id)}"
        )
        self._execute_world(sql)

    def _reload_runtime_for_quest(self, *, rule: ReactiveQuestRule) -> None:
        if not self.settings.soap_enabled or not self.settings.soap_user or not self.settings.soap_password:
            return
        client = SoapRuntimeClient(settings=self.settings)
        for command in build_default_quest_reload_commands(questgiver_entry=int(rule.turn_in_npc_entry)):
            client.execute_command(command)

    def _execute_world(self, sql: str) -> None:
        self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=sql,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install or refresh a reusable reactive bounty definition.")
    parser.add_argument("--template", type=Path)
    parser.add_argument("--rule-key")
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--subject-entry", type=int)
    parser.add_argument("--quest-id", type=int)
    parser.add_argument("--turn-in-npc-entry", type=int)
    parser.add_argument("--kill-threshold", type=int)
    parser.add_argument("--window-seconds", type=int)
    parser.add_argument("--post-reward-cooldown-seconds", type=int)
    parser.add_argument("--subject-name-prefix")
    parser.add_argument("--objective-target-name")
    parser.add_argument("--quest-title")
    parser.add_argument("--reward-item-entry", type=int)
    parser.add_argument("--reward-item-name")
    parser.add_argument("--reward-item-count", type=int)
    parser.add_argument("--reward-xp-difficulty", type=int)
    parser.add_argument("--reward-spell-id", type=int)
    parser.add_argument("--reward-spell-display-id", type=int)
    parser.add_argument(
        "--reward-reputation",
        action="append",
        help="Add a reputation reward as FACTION_ID:VALUE. May be repeated.",
    )
    parser.add_argument("--mode", choices=["dry-run", "apply"])
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


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _normalized_text(value: object) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _reward_reputations_from_value(value: object) -> list[dict[str, int]]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        raise ValueError("Reward reputations must be a list of objects or FACTION_ID:VALUE strings.")

    rewards: list[dict[str, int]] = []
    for item in values:
        if isinstance(item, str):
            parts = item.split(":", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid reward reputation `{item}`; expected FACTION_ID:VALUE.")
            rewards.append({"faction_id": int(parts[0]), "value": int(parts[1])})
            continue
        if isinstance(item, dict):
            rewards.append(
                {
                    "faction_id": int(item["faction_id"]),
                    "value": int(item["value"]),
                }
            )
            continue
        raise ValueError("Reward reputation entries must be objects or FACTION_ID:VALUE strings.")
    return rewards


def _load_template(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Reactive bounty template JSON must be an object.")
    return raw


def _coalesce(*values: object) -> object | None:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _resolve_rule_quest_id(
    *,
    slot_allocator: ReservedSlotDbAllocator,
    reactive_store: ReactiveQuestStore,
    rule_key: str,
    player_guid: int,
    explicit_quest_id: int | None,
    mode: str,
) -> tuple[int, list[str], ReactiveQuestRule | None, int | None]:
    existing_rule = reactive_store.get_rule_by_key(rule_key=rule_key)
    if explicit_quest_id is not None:
        return int(explicit_quest_id), [], existing_rule, None

    slot_notes = [
        "No explicit quest_id was provided; using a fresh managed quest slot instead of mutating an older live quest.",
    ]
    source_quest_id = int(existing_rule.quest_id) if existing_rule is not None else None

    if mode == "apply":
        slot = slot_allocator.allocate_next_free_slot(
            entity_type="quest",
            arc_key=rule_key,
            character_guid=player_guid,
            source_quest_id=source_quest_id,
            notes=[
                f"reactive_rule:{rule_key}",
                "grant_mode:direct_quest_add",
                "install_mode:apply",
                "slot_strategy:fresh_reserved_slot",
            ],
        )
        if slot is None:
            raise RuntimeError("No free reserved quest slots remain for reactive bounty install.")
        quest_id = int(slot.reserved_id)
        slot_notes.append(f"Allocated fresh reserved quest slot {quest_id} for `{rule_key}`.")
        return quest_id, slot_notes, existing_rule, quest_id

    preview = slot_allocator.peek_next_free_slot(entity_type="quest")
    if preview is None:
        raise RuntimeError("No free reserved quest slots remain for reactive bounty dry-run.")
    quest_id = int(preview.reserved_id)
    slot_notes.append(f"Previewing fresh reserved quest slot {quest_id} for `{rule_key}`.")
    return quest_id, slot_notes, existing_rule, None


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    template = _load_template(args.template)
    settings = Settings.from_env()
    client = MysqlCliClient()
    installer = ReactiveBountyInstaller(client=client, settings=settings)
    reactive_store = ReactiveQuestStore(client=client, settings=settings)
    slot_allocator = ReservedSlotDbAllocator(client=client, settings=settings)
    rule_key = str(_coalesce(args.rule_key, template.get("rule_key"), "reactive_bounty:kobold_vermin"))
    player_guid = int(_coalesce(args.player_guid, template.get("player_guid"), 5406))
    subject_entry = int(_coalesce(args.subject_entry, template.get("subject_entry"), 6))
    turn_in_npc_entry = int(_coalesce(args.turn_in_npc_entry, template.get("turn_in_npc_entry"), 197))
    kill_threshold = int(_coalesce(args.kill_threshold, template.get("kill_threshold"), 4))
    window_seconds = int(_coalesce(args.window_seconds, template.get("window_seconds"), 120))
    post_reward_cooldown_seconds = int(
        _coalesce(args.post_reward_cooldown_seconds, template.get("post_reward_cooldown_seconds"), 60)
    )
    mode = str(_coalesce(args.mode, template.get("mode"), "dry-run"))
    explicit_quest_id = _int_or_none(_coalesce(args.quest_id, template.get("quest_id")))
    quest_id, slot_notes, existing_rule, allocated_slot_id = _resolve_rule_quest_id(
        slot_allocator=slot_allocator,
        reactive_store=reactive_store,
        rule_key=rule_key,
        player_guid=player_guid,
        explicit_quest_id=explicit_quest_id,
        mode=mode,
    )

    player_name = reactive_store.fetch_character_name(player_guid=player_guid)
    resolver = LiveCreatureResolver(client=client, settings=settings)
    subject = resolver.resolve(entry=subject_entry)
    turn_in = resolver.resolve(entry=turn_in_npc_entry)
    objective_target_name = _str_or_none(_coalesce(args.objective_target_name, template.get("objective_target_name")))
    quest_title = _str_or_none(_coalesce(args.quest_title, template.get("quest_title"))) or f"Bounty: {objective_target_name or subject.name}"
    subject_name_prefix = _str_or_none(_coalesce(args.subject_name_prefix, template.get("subject_name_prefix")))
    reward_item_entry = _int_or_none(_coalesce(args.reward_item_entry, template.get("reward_item_entry")))
    reward_item_name = _str_or_none(_coalesce(args.reward_item_name, template.get("reward_item_name")))
    reward_item_count = _int_or_none(_coalesce(args.reward_item_count, template.get("reward_item_count")))
    reward_xp_difficulty = _int_or_none(_coalesce(args.reward_xp_difficulty, template.get("reward_xp_difficulty")))
    reward_spell_id = _int_or_none(_coalesce(args.reward_spell_id, template.get("reward_spell_id")))
    reward_spell_display_id = _int_or_none(
        _coalesce(args.reward_spell_display_id, template.get("reward_spell_display_id"))
    )
    reward_reputations = _coalesce(args.reward_reputation, template.get("reward_reputations"))
    metadata = {"installer": "wm.reactive.install_bounty"}
    if objective_target_name is not None:
        metadata["objective_target_name"] = objective_target_name
    if quest_title is not None:
        metadata["quest_title"] = quest_title
    if subject_name_prefix is not None:
        metadata["subject_name_prefix"] = subject_name_prefix
    if reward_item_entry is not None:
        metadata["reward_item_entry"] = reward_item_entry
    if reward_item_name is not None:
        metadata["reward_item_name"] = reward_item_name
    if reward_item_count is not None:
        metadata["reward_item_count"] = reward_item_count
    if reward_xp_difficulty is not None:
        metadata["reward_xp_difficulty"] = reward_xp_difficulty
    if reward_spell_id is not None:
        metadata["reward_spell_id"] = reward_spell_id
    if reward_spell_display_id is not None:
        metadata["reward_spell_display_id"] = reward_spell_display_id
    parsed_reputations = _reward_reputations_from_value(reward_reputations)
    if parsed_reputations:
        metadata["reward_reputations"] = [
            {"faction_id": int(item["faction_id"]), "value": int(item["value"])}
            for item in parsed_reputations
        ]
    rule = ReactiveQuestRule(
        rule_key=rule_key,
        is_active=True,
        player_guid_scope=player_guid,
        subject_type="creature",
        subject_entry=subject_entry,
        trigger_event_type="kill",
        kill_threshold=kill_threshold,
        window_seconds=window_seconds,
        quest_id=quest_id,
        turn_in_npc_entry=turn_in_npc_entry,
        grant_mode="direct_quest_add",
        post_reward_cooldown_seconds=post_reward_cooldown_seconds,
        metadata=metadata,
        notes=["reusable_reactive_bounty"],
        player_scope=PlayerRef(guid=player_guid, name=player_name),
        subject=CreatureRef(entry=subject.entry, name=subject.name),
        quest=QuestRef(id=quest_id, title=quest_title),
        turn_in_npc=NpcRef(entry=turn_in.entry, name=turn_in.name),
    )
    try:
        result = installer.install(rule=rule, mode=mode)
    except Exception:
        if allocated_slot_id is not None:
            slot_allocator.release_slot(entity_type="quest", reserved_id=allocated_slot_id)
        raise

    result.notes = [*slot_notes, *result.notes]
    if (
        mode == "apply"
        and explicit_quest_id is None
        and existing_rule is not None
        and int(existing_rule.quest_id) != int(quest_id)
    ):
        slot_allocator.release_slot(entity_type="quest", reserved_id=int(existing_rule.quest_id), archive=True)
        result.notes.append(
            f"Archived previous quest slot {existing_rule.quest_id} after switching `{rule_key}` to quest {quest_id}."
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
