from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import WMEvent
from wm.quests.bounty import build_default_bounty_reward
from wm.reactive.install_bounty import ReactiveBountyInstaller
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.store import ReactiveQuestStore
from wm.reactive.turn_in_selector import ZoneQuestTurnInSelector
from wm.quests.reward_picker import BountyEquipmentRewardPicker
from wm.refs import CreatureRef
from wm.refs import NpcRef
from wm.refs import PlayerRef
from wm.refs import QuestRef
from wm.quests.generate_bounty import LiveCreatureResolver
from wm.reserved.db_allocator import ReservedSlotDbAllocator

DEFAULT_AUTO_BOUNTY_KILL_THRESHOLD = 4
DEFAULT_AUTO_BOUNTY_WINDOW_SECONDS = 300
DEFAULT_AUTO_BOUNTY_POST_REWARD_COOLDOWN_SECONDS = 60


@dataclass(frozen=True, slots=True)
class AutoBountyTarget:
    turn_in_npc_entry: int
    subject_entry: int | None = None
    subject_name_prefix: str | None = None
    zone_id: int | None = None
    quest_id: int | None = None
    objective_target_name: str | None = None
    quest_title: str | None = None
    kill_threshold: int = DEFAULT_AUTO_BOUNTY_KILL_THRESHOLD
    window_seconds: int = DEFAULT_AUTO_BOUNTY_WINDOW_SECONDS
    post_reward_cooldown_seconds: int = DEFAULT_AUTO_BOUNTY_POST_REWARD_COOLDOWN_SECONDS
    rule_key: str | None = None

    def resolved_rule_key(self, *, subject_entry: int | None = None, zone_id: int | None = None) -> str:
        if self.rule_key not in (None, ""):
            return str(self.rule_key)
        if zone_id not in (None, "") and subject_entry not in (None, ""):
            return f"reactive_bounty:auto:zone:{int(zone_id)}:subject:{int(subject_entry)}"
        if self.subject_entry not in (None, ""):
            return f"reactive_bounty:auto:subject:{int(self.subject_entry)}"
        if self.subject_name_prefix not in (None, "") and subject_entry not in (None, ""):
            normalized = str(self.subject_name_prefix).strip().lower().replace(" ", "_").strip("_")
            if zone_id not in (None, ""):
                return f"reactive_bounty:auto:{normalized}:zone:{int(zone_id)}:subject:{int(subject_entry)}"
            return f"reactive_bounty:auto:{normalized}:{int(subject_entry)}"
        raise ValueError("AutoBountyTarget needs either subject_entry or a subject_name_prefix plus subject_entry.")


AUTO_BOUNTY_TARGETS: tuple[AutoBountyTarget, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedAutoBountyPlan:
    rule_key: str
    subject_entry: int
    subject_name: str
    objective_target_name: str
    quest_title: str
    quest_id: int | None
    turn_in_npc_entry: int
    turn_in_npc_name: str
    zone_id: int | None
    kill_threshold: int
    window_seconds: int
    post_reward_cooldown_seconds: int
    metadata: dict[str, object]


class ReactiveAutoBountyManager:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        reactive_store: ReactiveQuestStore | None = None,
        installer: ReactiveBountyInstaller | None = None,
        resolver: LiveCreatureResolver | None = None,
        slot_allocator: ReservedSlotDbAllocator | None = None,
        turn_in_selector: ZoneQuestTurnInSelector | None = None,
        reward_picker: BountyEquipmentRewardPicker | None = None,
        targets: tuple[AutoBountyTarget, ...] = AUTO_BOUNTY_TARGETS,
    ) -> None:
        self.client = client
        self.settings = settings
        self.reactive_store = reactive_store or ReactiveQuestStore(client=client, settings=settings)
        self.installer = installer or ReactiveBountyInstaller(
            client=client,
            settings=settings,
            reactive_store=self.reactive_store,
        )
        self.resolver = resolver or LiveCreatureResolver(client=client, settings=settings)
        self.slot_allocator = slot_allocator or ReservedSlotDbAllocator(client=client, settings=settings)
        self.turn_in_selector = turn_in_selector or ZoneQuestTurnInSelector(client=client, settings=settings)
        self.reward_picker = reward_picker or BountyEquipmentRewardPicker(client=client, settings=settings)
        self.targets = tuple(targets)

    def ensure_rule_for_event(self, event: WMEvent) -> ReactiveQuestRule | None:
        if event.event_class != "observed" or event.event_type != "kill":
            return None
        if event.player_guid is None or event.subject_type != "creature" or event.subject_entry is None:
            return None

        player_guid = int(event.player_guid)
        if (
            bool(getattr(self.settings, "reactive_auto_bounty_single_open_per_player", True))
            and self._has_open_auto_bounty_for_player(player_guid=player_guid)
        ):
            return None

        plan = self._resolve_plan_for_event(event)
        if plan is None:
            return None

        existing_rule = self.reactive_store.get_rule_by_key(rule_key=plan.rule_key)
        if existing_rule is not None and existing_rule.player_guid_scope not in (None, player_guid):
            return None
        if existing_rule is not None and existing_rule.is_active:
            return existing_rule

        quest_id = self._resolve_quest_id(
            plan=plan,
            player_guid=player_guid,
            existing_rule=existing_rule,
            rule_key=plan.rule_key,
        )
        if quest_id is None:
            return None

        player_name = self.reactive_store.fetch_character_name(player_guid=player_guid)
        subject = self.resolver.resolve(entry=plan.subject_entry)
        rule = ReactiveQuestRule(
            rule_key=plan.rule_key,
            is_active=True,
            player_guid_scope=player_guid,
            subject_type="creature",
            subject_entry=plan.subject_entry,
            trigger_event_type="kill",
            kill_threshold=int(plan.kill_threshold),
            window_seconds=int(plan.window_seconds),
            quest_id=int(quest_id),
            turn_in_npc_entry=int(plan.turn_in_npc_entry),
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=int(plan.post_reward_cooldown_seconds),
            metadata=dict(plan.metadata),
            notes=["auto_bounty", "dynamic_auto_bounty", "consecutive_kill_streak"],
            player_scope=PlayerRef(guid=player_guid, name=player_name),
            subject=CreatureRef(entry=subject.entry, name=subject.name),
            quest=QuestRef(id=int(quest_id), title=plan.quest_title),
            turn_in_npc=NpcRef(entry=int(plan.turn_in_npc_entry), name=plan.turn_in_npc_name),
        )
        self.installer.install(rule=rule, mode="apply")
        self.reactive_store.deactivate_player_auto_bounty_rules(
            player_guid=player_guid,
            except_rule_key=rule.rule_key,
        )
        return rule

    def _has_open_auto_bounty_for_player(self, *, player_guid: int) -> bool:
        for quest_id in self._player_auto_bounty_quest_ids(player_guid=player_guid):
            character_state = self.reactive_store.fetch_character_quest_status(
                player_guid=int(player_guid),
                quest_id=int(quest_id),
            )
            if character_state in {"incomplete", "complete"}:
                return True
            event_state = self._latest_quest_event_state(player_guid=player_guid, quest_id=int(quest_id))
            if event_state in {"incomplete", "complete"}:
                return True
        return False

    def _player_auto_bounty_quest_ids(self, *, player_guid: int) -> list[int]:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT QuestID FROM wm_reactive_quest_rule "
                f"WHERE PlayerGUIDScope = {int(player_guid)} "
                "AND RuleKey LIKE 'reactive_bounty:auto:%' "
                "ORDER BY UpdatedAt DESC, QuestID DESC "
                "LIMIT 50"
            ),
        )
        result: list[int] = []
        for row in rows:
            raw_value = row.get("QuestID")
            if raw_value in (None, ""):
                continue
            result.append(int(raw_value))
        return result

    def _latest_quest_event_state(self, *, player_guid: int, quest_id: int) -> str | None:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT EventType FROM wm_event_log "
                "WHERE EventClass = 'observed' "
                f"AND PlayerGUID = {int(player_guid)} "
                "AND EventType IN ('quest_accept', 'quest_granted', 'quest_completed', 'quest_rewarded') "
                "AND ("
                f"SubjectEntry = {int(quest_id)} "
                f"OR JSON_UNQUOTE(JSON_EXTRACT(MetadataJSON, '$.quest_id')) = '{int(quest_id)}' "
                f"OR JSON_UNQUOTE(JSON_EXTRACT(MetadataJSON, '$.object_entry')) = '{int(quest_id)}' "
                f"OR JSON_UNQUOTE(JSON_EXTRACT(MetadataJSON, '$.payload.quest_id')) = '{int(quest_id)}' "
                f"OR JSON_UNQUOTE(JSON_EXTRACT(MetadataJSON, '$.payload.object_entry')) = '{int(quest_id)}'"
                ") "
                "ORDER BY EventID DESC LIMIT 1"
            ),
        )
        if not rows:
            return None
        event_type = str(rows[0].get("EventType") or "")
        if event_type in {"quest_accept", "quest_granted"}:
            return "incomplete"
        if event_type == "quest_completed":
            return "complete"
        if event_type == "quest_rewarded":
            return "rewarded"
        return None

    def _resolve_plan_for_event(self, event: WMEvent) -> ResolvedAutoBountyPlan | None:
        target = self._target_for_event(event)
        if target is not None:
            return self._plan_from_override(event=event, target=target)
        return self._plan_from_zone_selector(event=event)

    def _plan_from_override(self, *, event: WMEvent, target: AutoBountyTarget) -> ResolvedAutoBountyPlan | None:
        resolved_subject_entry = int(target.subject_entry or event.subject_entry or 0)
        if resolved_subject_entry <= 0:
            return None
        subject = self.resolver.resolve(entry=resolved_subject_entry)
        turn_in_npc = self.resolver.resolve(entry=int(target.turn_in_npc_entry))
        zone_id = _resolved_zone_id(event)
        objective_target_name = _resolved_objective_target_name(
            explicit_name=target.objective_target_name,
            event=event,
            fallback_name=subject.name,
        )
        quest_title = _resolved_quest_title(explicit_title=target.quest_title, target_name=objective_target_name)
        reward_preview, reward_metadata = self._resolve_reward_metadata(
            player_guid=int(event.player_guid or 0),
            quest_level=max(int(subject.profile.level_max), 1),
        )
        return ResolvedAutoBountyPlan(
            rule_key=target.resolved_rule_key(subject_entry=resolved_subject_entry, zone_id=zone_id),
            subject_entry=resolved_subject_entry,
            subject_name=subject.name,
            objective_target_name=objective_target_name,
            quest_title=quest_title,
            quest_id=(int(target.quest_id) if target.quest_id not in (None, "") else None),
            turn_in_npc_entry=int(target.turn_in_npc_entry),
            turn_in_npc_name=turn_in_npc.name,
            zone_id=zone_id,
            kill_threshold=int(target.kill_threshold),
            window_seconds=int(target.window_seconds),
            post_reward_cooldown_seconds=int(target.post_reward_cooldown_seconds),
            metadata={
                "auto_bounty": True,
                "auto_bounty_subject_entry": resolved_subject_entry,
                "auto_bounty_zone_id": zone_id,
                "auto_bounty_turn_in_npc_entry": int(target.turn_in_npc_entry),
                "auto_bounty_source_name_prefix": target.subject_name_prefix,
                "auto_bounty_turn_in_strategy": "override",
                "require_consecutive_kills": True,
                "objective_target_name": objective_target_name,
                "quest_title": quest_title,
                "projected_reward": reward_preview,
                "installer": "wm.reactive.auto_bounty",
                **reward_metadata,
            },
        )

    def _plan_from_zone_selector(self, *, event: WMEvent) -> ResolvedAutoBountyPlan | None:
        resolved_subject_entry = int(event.subject_entry or 0)
        if resolved_subject_entry <= 0:
            return None
        zone_id = _resolved_zone_id(event)
        turn_in_choice = self.turn_in_selector.select(
            player_guid=int(event.player_guid or 0),
            zone_id=zone_id,
        )
        if turn_in_choice is None:
            return None
        subject = self.resolver.resolve(entry=resolved_subject_entry)
        objective_target_name = _resolved_objective_target_name(
            explicit_name=None,
            event=event,
            fallback_name=subject.name,
        )
        quest_title = _resolved_quest_title(explicit_title=None, target_name=objective_target_name)
        reward_preview, reward_metadata = self._resolve_reward_metadata(
            player_guid=int(event.player_guid or 0),
            quest_level=max(int(subject.profile.level_max), 1),
        )
        return ResolvedAutoBountyPlan(
            rule_key=f"reactive_bounty:auto:zone:{int(zone_id or 0)}:subject:{resolved_subject_entry}",
            subject_entry=resolved_subject_entry,
            subject_name=subject.name,
            objective_target_name=objective_target_name,
            quest_title=quest_title,
            quest_id=None,
            turn_in_npc_entry=int(turn_in_choice.entry),
            turn_in_npc_name=turn_in_choice.name,
            zone_id=zone_id,
            kill_threshold=DEFAULT_AUTO_BOUNTY_KILL_THRESHOLD,
            window_seconds=DEFAULT_AUTO_BOUNTY_WINDOW_SECONDS,
            post_reward_cooldown_seconds=DEFAULT_AUTO_BOUNTY_POST_REWARD_COOLDOWN_SECONDS,
            metadata={
                "auto_bounty": True,
                "auto_bounty_subject_entry": resolved_subject_entry,
                "auto_bounty_zone_id": zone_id,
                "auto_bounty_turn_in_npc_entry": int(turn_in_choice.entry),
                "auto_bounty_turn_in_strategy": "zone_quest_ties",
                "auto_bounty_turn_in_candidate": {
                    "entry": int(turn_in_choice.entry),
                    "name": turn_in_choice.name,
                    "faction_id": int(turn_in_choice.faction_id),
                    "faction_label": turn_in_choice.faction_label,
                    "quest_tie_count": int(turn_in_choice.quest_tie_count),
                    "starter_count": int(turn_in_choice.starter_count),
                    "ender_count": int(turn_in_choice.ender_count),
                    "spawn_count": int(turn_in_choice.spawn_count),
                },
                "require_consecutive_kills": True,
                "objective_target_name": objective_target_name,
                "quest_title": quest_title,
                "projected_reward": reward_preview,
                "installer": "wm.reactive.auto_bounty",
                **reward_metadata,
            },
        )

    def _resolve_reward_metadata(
        self,
        *,
        player_guid: int,
        quest_level: int,
    ) -> tuple[dict[str, object], dict[str, object]]:
        selection = self.reward_picker.select_for_player(player_guid=int(player_guid))
        if selection is None:
            return (
                build_default_bounty_reward(quest_level=int(quest_level)).to_dict(),
                {"reward_policy": "default_supply_bundle_v1"},
            )

        return (
            build_default_bounty_reward(
                quest_level=int(quest_level),
                reward_item_entry=int(selection.item_entry),
                reward_item_name=selection.item_name,
            ).to_dict(),
            {
                "reward_policy": selection.policy_key,
                "reward_item_entry": int(selection.item_entry),
                "reward_item_name": selection.item_name,
                "reward_item_count": 1,
                "reward_selection": selection.to_dict(),
            },
        )

    def _target_for_event(self, event: WMEvent) -> AutoBountyTarget | None:
        event_subject_name = _event_subject_name(event)
        normalized_subject_name = event_subject_name.lower() if event_subject_name is not None else None
        resolved_zone_id = _resolved_zone_id(event)
        for target in self.targets:
            if target.zone_id not in (None, "") and int(target.zone_id) != int(resolved_zone_id or 0):
                continue
            if target.subject_entry not in (None, "") and int(target.subject_entry) == int(event.subject_entry or 0):
                return target
            if (
                target.subject_name_prefix not in (None, "")
                and normalized_subject_name is not None
                and normalized_subject_name.startswith(str(target.subject_name_prefix).strip().lower())
            ):
                return target
        return None

    def _resolve_quest_id(
        self,
        *,
        plan: ResolvedAutoBountyPlan,
        player_guid: int,
        existing_rule: ReactiveQuestRule | None,
        rule_key: str,
    ) -> int | None:
        if existing_rule is not None:
            return int(existing_rule.quest_id)
        if plan.quest_id not in (None, ""):
            return int(plan.quest_id)
        slot = self.slot_allocator.allocate_next_free_slot(
            entity_type="quest",
            arc_key=rule_key,
            character_guid=player_guid,
            notes=[
                f"reactive_rule:{rule_key}",
                "grant_mode:direct_quest_add",
                "auto_bounty",
                f"turn_in_npc:{int(plan.turn_in_npc_entry)}",
                f"zone_id:{int(plan.zone_id or 0)}",
            ],
        )
        if slot is None:
            return None
        return int(slot.reserved_id)


def _event_subject_name(event: WMEvent) -> str | None:
    raw_value = event.metadata.get("subject_name")
    if isinstance(raw_value, str) and raw_value.strip():
        return raw_value.strip()
    payload = event.metadata.get("payload")
    if isinstance(payload, dict):
        nested_name = payload.get("subject_name")
        if isinstance(nested_name, str) and nested_name.strip():
            return nested_name.strip()
    return None


def _resolved_zone_id(event: WMEvent) -> int | None:
    if event.zone_id not in (None, ""):
        return int(event.zone_id)
    payload = event.metadata.get("payload")
    if isinstance(payload, dict) and payload.get("zone_id") not in (None, ""):
        try:
            return int(payload["zone_id"])
        except (TypeError, ValueError):
            return None
    return None


def _resolved_objective_target_name(*, explicit_name: str | None, event: WMEvent, fallback_name: str) -> str:
    if explicit_name not in (None, ""):
        return str(explicit_name).strip()
    event_name = _event_subject_name(event)
    if event_name not in (None, ""):
        return str(event_name).strip()
    return str(fallback_name).strip()


def _resolved_quest_title(*, explicit_title: str | None, target_name: str) -> str:
    if explicit_title not in (None, ""):
        return str(explicit_title).strip()
    return f"Bounty: {target_name}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or reset dynamic auto-bounty rules for one player.")
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--deactivate-existing", action="store_true")
    parser.add_argument("--deactivate-existing-bounty-rules", action="store_true")
    parser.add_argument("--summary", action="store_true")
    return parser


def _rule_rows_for_player(
    store: ReactiveQuestStore,
    *,
    player_guid: int,
    rule_prefix: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rule in store.list_active_rules(player_guid=int(player_guid)):
        if not str(rule.rule_key).startswith(str(rule_prefix)):
            continue
        rows.append(
            {
                "rule_key": rule.rule_key,
                "quest_id": int(rule.quest_id),
                "subject_entry": int(rule.subject_entry),
                "turn_in_npc_entry": int(rule.turn_in_npc_entry),
                "objective_target_name": rule.metadata.get("objective_target_name"),
                "quest_title": rule.metadata.get("quest_title"),
                "reward_policy": rule.metadata.get("reward_policy"),
                "projected_reward": rule.metadata.get("projected_reward"),
            }
        )
    return rows


def _render_summary(
    *,
    player_guid: int,
    deactivated_existing_auto_rules: bool,
    deactivated_existing_bounty_rules: bool,
    active_auto_rules: list[dict[str, object]],
    active_bounty_rules: list[dict[str, object]],
) -> str:
    lines = [
        f"player_guid: {int(player_guid)}",
        f"deactivated_existing_auto_rules: {str(bool(deactivated_existing_auto_rules)).lower()}",
        f"deactivated_existing_bounty_rules: {str(bool(deactivated_existing_bounty_rules)).lower()}",
        f"active_auto_rules: {len(active_auto_rules)}",
        f"active_bounty_rules: {len(active_bounty_rules)}",
    ]
    if not active_bounty_rules:
        lines.append("rules: none")
        return "\n".join(lines)

    lines.append("rules:")
    for rule in active_bounty_rules:
        lines.append(
            f"- {rule['rule_key']} | quest_id={rule['quest_id']} | subject_entry={rule['subject_entry']} | turn_in_npc_entry={rule['turn_in_npc_entry']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    store = ReactiveQuestStore(client=client, settings=settings)

    if args.deactivate_existing:
        store.deactivate_player_auto_bounty_rules(player_guid=int(args.player_guid))
    if args.deactivate_existing_bounty_rules:
        store.deactivate_player_bounty_rules(player_guid=int(args.player_guid))

    payload = {
        "player_guid": int(args.player_guid),
        "deactivated_existing_auto_rules": bool(args.deactivate_existing),
        "deactivated_existing_bounty_rules": bool(args.deactivate_existing_bounty_rules),
        "active_auto_rules": _rule_rows_for_player(
            store,
            player_guid=int(args.player_guid),
            rule_prefix="reactive_bounty:auto:",
        ),
        "active_bounty_rules": _rule_rows_for_player(
            store,
            player_guid=int(args.player_guid),
            rule_prefix="reactive_bounty:",
        ),
    }
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.summary:
        print(
            _render_summary(
                player_guid=int(args.player_guid),
                deactivated_existing_auto_rules=bool(args.deactivate_existing),
                deactivated_existing_bounty_rules=bool(args.deactivate_existing_bounty_rules),
                active_auto_rules=payload["active_auto_rules"],
                active_bounty_rules=payload["active_bounty_rules"],
            )
        )
    else:
        print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
