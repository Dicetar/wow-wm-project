from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from wm.refs import CreatureRef
from wm.refs import ItemRef
from wm.refs import NpcRef
from wm.refs import QuestRef
from wm.refs import creature_ref_from_value
from wm.refs import item_ref_from_value
from wm.refs import npc_ref_from_value
from wm.refs import quest_ref_from_value


@dataclass(slots=True)
class BountyQuestObjective:
    target_entry: int
    target_name: str
    kill_count: int
    target: CreatureRef | None = None

    def __post_init__(self) -> None:
        self.target = self.target or CreatureRef(entry=int(self.target_entry), name=self.target_name)
        self.target_entry = int(self.target.entry)
        self.target_name = self.target.name or self.target_name

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["target"] = self.target.to_dict() if self.target is not None else None
        return payload


@dataclass(slots=True)
class BountyQuestReward:
    money_copper: int = 0
    reward_item_entry: int | None = None
    reward_item_name: str | None = None
    reward_item_count: int = 1
    reward_item: ItemRef | None = None

    def __post_init__(self) -> None:
        self.reward_item = self.reward_item or item_ref_from_value(
            {"entry": self.reward_item_entry, "name": self.reward_item_name}
            if self.reward_item_entry is not None
            else None
        )
        if self.reward_item is not None:
            self.reward_item_entry = int(self.reward_item.entry)
            if self.reward_item.name not in (None, ""):
                self.reward_item_name = self.reward_item.name

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reward_item"] = self.reward_item.to_dict() if self.reward_item is not None else None
        return payload


@dataclass(slots=True)
class BountyQuestDraft:
    quest_id: int
    quest_level: int
    min_level: int
    questgiver_entry: int
    questgiver_name: str
    title: str
    quest_description: str
    objective_text: str
    offer_reward_text: str
    request_items_text: str
    objective: BountyQuestObjective
    reward: BountyQuestReward
    start_npc_entry: int | None = None
    end_npc_entry: int | None = None
    grant_mode: str = "npc_start"
    tags: list[str] = field(default_factory=list)
    template_defaults: dict[str, Any] = field(default_factory=dict)
    quest: QuestRef | None = None
    questgiver: NpcRef | None = None
    starter_npc: NpcRef | None = None
    ender_npc: NpcRef | None = None

    def __post_init__(self) -> None:
        self.quest = self.quest or quest_ref_from_value({"id": self.quest_id, "title": self.title})
        if self.quest is not None:
            self.quest_id = int(self.quest.id)

        self.questgiver = self.questgiver or npc_ref_from_value(
            {"entry": self.questgiver_entry, "name": self.questgiver_name}
        )
        if self.questgiver is not None:
            self.questgiver_entry = int(self.questgiver.entry)
            if self.questgiver.name not in (None, ""):
                self.questgiver_name = self.questgiver.name

        self.starter_npc = self.starter_npc or npc_ref_from_value(
            {"entry": self.start_npc_entry, "name": self.questgiver_name}
            if self.start_npc_entry is not None
            else None
        )
        if self.starter_npc is not None:
            self.start_npc_entry = int(self.starter_npc.entry)

        self.ender_npc = self.ender_npc or npc_ref_from_value(
            {"entry": self.end_npc_entry, "name": self.questgiver_name}
            if self.end_npc_entry is not None
            else None
        )
        if self.ender_npc is not None:
            self.end_npc_entry = int(self.ender_npc.entry)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["quest"] = self.quest.to_dict() if self.quest is not None else None
        payload["questgiver"] = self.questgiver.to_dict() if self.questgiver is not None else None
        payload["starter_npc"] = self.starter_npc.to_dict() if self.starter_npc is not None else None
        payload["ender_npc"] = self.ender_npc.to_dict() if self.ender_npc is not None else None
        payload["objective"] = self.objective.to_dict()
        payload["reward"] = self.reward.to_dict()
        return payload


@dataclass(slots=True)
class ValidationIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }
