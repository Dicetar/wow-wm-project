from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from wm.events.models import ReactionCooldownKey
from wm.events.models import WMEvent
from wm.events.models import utcnow_iso
from wm.events.store import EventStore
from wm.reactive.models import PlayerQuestRuntimeState
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.store import ReactiveQuestStore


_QUEST_STATE_EVENT_TYPES = {
    "incomplete": "quest_granted",
    "complete": "quest_completed",
    "rewarded": "quest_rewarded",
}


@dataclass(slots=True)
class QuestRuntimeSyncResult:
    checked_rules: int = 0
    observed_transitions: list[WMEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "checked_rules": self.checked_rules,
            "observed_transitions": [event.to_dict() for event in self.observed_transitions],
        }


class ReactiveQuestRuntimeSynchronizer:
    def __init__(
        self,
        *,
        store: EventStore,
        reactive_store: ReactiveQuestStore,
    ) -> None:
        self.store = store
        self.reactive_store = reactive_store

    def poll(self, *, player_guid: int | None = None, preview: bool = False) -> QuestRuntimeSyncResult:
        result = QuestRuntimeSyncResult()
        rules = self.reactive_store.list_active_rules(player_guid=player_guid)
        for rule in rules:
            target_player_guids = _target_player_guids(rule=rule, requested_player_guid=player_guid)
            for guid in target_player_guids:
                result.checked_rules += 1
                transition = self._sync_rule_state(rule=rule, player_guid=guid, preview=preview)
                if transition is not None:
                    result.observed_transitions.append(transition)
        return result

    def _sync_rule_state(
        self,
        *,
        rule: ReactiveQuestRule,
        player_guid: int,
        preview: bool,
    ) -> WMEvent | None:
        current_state = self.reactive_store.fetch_character_quest_status(
            player_guid=player_guid,
            quest_id=rule.quest_id,
        )
        previous_state = self.reactive_store.get_player_quest_runtime_state(
            player_guid=player_guid,
            quest_id=rule.quest_id,
        )
        observed_at = utcnow_iso()

        if not preview:
            self.reactive_store.set_player_quest_runtime_state(
                PlayerQuestRuntimeState(
                    player_guid=player_guid,
                    quest_id=rule.quest_id,
                    current_state=current_state,
                    last_transition_at=(
                        observed_at
                        if previous_state is None or previous_state.current_state != current_state
                        else previous_state.last_transition_at
                    ),
                    last_observed_at=observed_at,
                    metadata={
                        "rule_key": rule.rule_key,
                        "subject_type": rule.subject_type,
                        "subject_entry": rule.subject_entry,
                        "turn_in_npc_entry": rule.turn_in_npc_entry,
                    },
                )
            )

        if previous_state is not None and previous_state.current_state == current_state:
            return None

        event_type = _QUEST_STATE_EVENT_TYPES.get(current_state)
        if event_type is None:
            return None

        if not preview and current_state == "rewarded" and rule.post_reward_cooldown_seconds > 0:
            self.store.set_cooldown(
                key=ReactionCooldownKey(
                    rule_type=rule.rule_key,
                    player_guid=player_guid,
                    subject_type=rule.subject_type,
                    subject_entry=rule.subject_entry,
                ),
                cooldown_seconds=rule.post_reward_cooldown_seconds,
                triggered_at=observed_at,
                metadata={
                    "rule_key": rule.rule_key,
                    "quest_id": rule.quest_id,
                    "state": current_state,
                },
            )

        previous_value = previous_state.current_state if previous_state is not None else "none"
        return WMEvent(
            event_class="observed",
            event_type=event_type,
            source="quest_state_poll",
            source_event_key=f"{player_guid}:{rule.quest_id}:{event_type}:{observed_at}",
            occurred_at=observed_at,
            player_guid=player_guid,
            subject_type=rule.subject_type,
            subject_entry=rule.subject_entry,
            event_value=str(rule.quest_id),
            metadata={
                "quest_id": rule.quest_id,
                "rule_key": rule.rule_key,
                "turn_in_npc_entry": rule.turn_in_npc_entry,
                "previous_state": previous_value,
                "current_state": current_state,
            },
        )


def _target_player_guids(*, rule: ReactiveQuestRule, requested_player_guid: int | None) -> list[int]:
    if requested_player_guid is not None:
        if rule.player_guid_scope is not None and rule.player_guid_scope != requested_player_guid:
            return []
        return [int(requested_player_guid)]
    if rule.player_guid_scope is not None:
        return [int(rule.player_guid_scope)]
    return []
