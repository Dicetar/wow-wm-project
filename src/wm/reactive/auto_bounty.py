from __future__ import annotations

from dataclasses import dataclass

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import WMEvent
from wm.reactive.install_bounty import ReactiveBountyInstaller
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.store import ReactiveQuestStore
from wm.refs import CreatureRef
from wm.refs import NpcRef
from wm.refs import PlayerRef
from wm.refs import QuestRef
from wm.quests.generate_bounty import LiveCreatureResolver
from wm.reserved.db_allocator import ReservedSlotDbAllocator


@dataclass(frozen=True, slots=True)
class AutoBountyTarget:
    turn_in_npc_entry: int
    subject_entry: int | None = None
    subject_name_prefix: str | None = None
    quest_id: int | None = None
    objective_target_name: str | None = None
    quest_title: str | None = None
    kill_threshold: int = 4
    window_seconds: int = 120
    post_reward_cooldown_seconds: int = 60
    rule_key: str | None = None

    def resolved_rule_key(self, *, subject_entry: int | None = None) -> str:
        if self.rule_key not in (None, ""):
            return str(self.rule_key)
        if self.subject_entry not in (None, ""):
            return f"reactive_bounty:auto:subject:{int(self.subject_entry)}"
        if self.subject_name_prefix not in (None, "") and subject_entry not in (None, ""):
            normalized = str(self.subject_name_prefix).strip().lower().replace(" ", "_").strip("_")
            return f"reactive_bounty:auto:{normalized}:{int(subject_entry)}"
        raise ValueError("AutoBountyTarget needs either subject_entry or a subject_name_prefix plus subject_entry.")


AUTO_BOUNTY_TARGETS: tuple[AutoBountyTarget, ...] = (
    AutoBountyTarget(subject_entry=6, turn_in_npc_entry=197, rule_key="reactive_bounty:auto:kobold_vermin"),
    AutoBountyTarget(
        subject_name_prefix="Defias ",
        turn_in_npc_entry=261,
        objective_target_name="Defias Bandits",
        quest_title="Bounty: Defias Bandits",
        window_seconds=300,
    ),
)


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
        self.targets = tuple(targets)

    def ensure_rule_for_event(self, event: WMEvent) -> ReactiveQuestRule | None:
        if event.event_class != "observed" or event.event_type != "kill":
            return None
        if event.player_guid is None or event.subject_type != "creature" or event.subject_entry is None:
            return None

        target = self._target_for_event(event)
        if target is None:
            return None

        player_guid = int(event.player_guid)
        resolved_subject_entry = int(target.subject_entry or event.subject_entry)
        rule_key = target.resolved_rule_key(subject_entry=resolved_subject_entry)
        existing_rule = self.reactive_store.get_rule_by_key(rule_key=rule_key)
        if existing_rule is not None and existing_rule.player_guid_scope not in (None, player_guid):
            return None
        if existing_rule is not None and existing_rule.is_active:
            return existing_rule

        quest_id = self._resolve_quest_id(
            target=target,
            player_guid=player_guid,
            existing_rule=existing_rule,
            rule_key=rule_key,
        )
        if quest_id is None:
            return None

        player_name = self.reactive_store.fetch_character_name(player_guid=player_guid)
        subject = self.resolver.resolve(entry=resolved_subject_entry)
        turn_in_npc = self.resolver.resolve(entry=int(target.turn_in_npc_entry))
        rule = ReactiveQuestRule(
            rule_key=rule_key,
            is_active=True,
            player_guid_scope=player_guid,
            subject_type="creature",
            subject_entry=resolved_subject_entry,
            trigger_event_type="kill",
            kill_threshold=int(target.kill_threshold),
            window_seconds=int(target.window_seconds),
            quest_id=int(quest_id),
            turn_in_npc_entry=int(target.turn_in_npc_entry),
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=int(target.post_reward_cooldown_seconds),
            metadata={
                "auto_bounty": True,
                "auto_bounty_subject_entry": resolved_subject_entry,
                "auto_bounty_turn_in_npc_entry": int(target.turn_in_npc_entry),
                "auto_bounty_source_name_prefix": target.subject_name_prefix,
                "objective_target_name": target.objective_target_name,
                "quest_title": target.quest_title,
                "installer": "wm.reactive.auto_bounty",
            },
            notes=["auto_bounty"],
            player_scope=PlayerRef(guid=player_guid, name=player_name),
            subject=CreatureRef(entry=subject.entry, name=subject.name),
            quest=QuestRef(id=int(quest_id), title=str(target.quest_title or f"Bounty: {subject.name}")),
            turn_in_npc=NpcRef(entry=turn_in_npc.entry, name=turn_in_npc.name),
        )
        self.installer.install(rule=rule, mode="apply")
        self.reactive_store.deactivate_player_bounty_rules(
            player_guid=player_guid,
            except_rule_key=rule.rule_key,
        )
        return rule

    def _target_for_event(self, event: WMEvent) -> AutoBountyTarget | None:
        event_subject_name = _event_subject_name(event)
        normalized_subject_name = event_subject_name.lower() if event_subject_name is not None else None
        for target in self.targets:
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
        target: AutoBountyTarget,
        player_guid: int,
        existing_rule: ReactiveQuestRule | None,
        rule_key: str,
    ) -> int | None:
        if existing_rule is not None:
            return int(existing_rule.quest_id)
        if target.quest_id not in (None, ""):
            return int(target.quest_id)
        slot = self.slot_allocator.allocate_next_free_slot(
            entity_type="quest",
            arc_key=rule_key,
            character_guid=player_guid,
            notes=[
                f"reactive_rule:{rule_key}",
                "grant_mode:direct_quest_add",
                "auto_bounty",
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
