from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from wm.refs import CreatureRef
from wm.refs import NpcRef
from wm.refs import PlayerRef
from wm.refs import QuestRef
from wm.refs import creature_ref_from_value
from wm.refs import npc_ref_from_value
from wm.refs import player_ref_from_value
from wm.refs import quest_ref_from_value


@dataclass(slots=True)
class ReactiveQuestRule:
    rule_key: str
    is_active: bool
    player_guid_scope: int | None
    subject_type: str
    subject_entry: int
    trigger_event_type: str
    kill_threshold: int
    window_seconds: int
    quest_id: int
    turn_in_npc_entry: int
    grant_mode: str
    post_reward_cooldown_seconds: int
    metadata: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    player_scope: PlayerRef | None = None
    subject: CreatureRef | None = None
    quest: QuestRef | None = None
    turn_in_npc: NpcRef | None = None

    def __post_init__(self) -> None:
        self.player_scope = self.player_scope or player_ref_from_value(self.metadata.get("player_scope"))
        if self.player_scope is None and self.player_guid_scope is not None:
            self.player_scope = PlayerRef(guid=int(self.player_guid_scope))
        if self.player_guid_scope is None and self.player_scope is not None:
            self.player_guid_scope = int(self.player_scope.guid)

        self.subject = self.subject or creature_ref_from_value(self.metadata.get("subject"))
        if self.subject is None:
            self.subject = CreatureRef(entry=int(self.subject_entry))
        if self.subject_entry in (None, 0):
            self.subject_entry = int(self.subject.entry)

        self.quest = self.quest or quest_ref_from_value(self.metadata.get("quest"))
        if self.quest is None:
            self.quest = QuestRef(id=int(self.quest_id))
        if self.quest_id in (None, 0):
            self.quest_id = int(self.quest.id)

        self.turn_in_npc = self.turn_in_npc or npc_ref_from_value(self.metadata.get("turn_in_npc"))
        if self.turn_in_npc is None:
            self.turn_in_npc = NpcRef(entry=int(self.turn_in_npc_entry))
        if self.turn_in_npc_entry in (None, 0):
            self.turn_in_npc_entry = int(self.turn_in_npc.entry)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["player_scope"] = self.player_scope.to_dict() if self.player_scope is not None else None
        payload["subject"] = self.subject.to_dict() if self.subject is not None else None
        payload["quest"] = self.quest.to_dict() if self.quest is not None else None
        payload["turn_in_npc"] = self.turn_in_npc.to_dict() if self.turn_in_npc is not None else None
        return payload


@dataclass(slots=True)
class PlayerQuestRuntimeState:
    player_guid: int
    quest_id: int
    current_state: str
    last_transition_at: str | None = None
    last_observed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
