from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


EVENT_CLASSES = {"observed", "derived", "action"}

OBSERVED_EVENT_TYPES = {
    "kill",
    "talk",
    "gossip_select",
    "quest_accept",
    "quest_complete",
    "quest_granted",
    "quest_completed",
    "quest_rewarded",
    "quest_removed",
    "loot_item",
    "item_use",
    "spell_cast",
    "aura_applied",
    "aura_removed",
    "weather_changed",
    "enter_area",
}

DERIVED_EVENT_TYPES = {
    "repeat_hunt_detected",
    "kill_burst_detected",
    "familiar_npc_detected",
    "followup_eligible",
    "area_pressure_detected",
}

ACTION_EVENT_TYPES = {
    "reaction_planned",
    "quest_grant_issued",
    "quest_published",
    "item_published",
    "spell_published",
    "announcement_sent",
    "native_bridge_action_done",
}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(slots=True)
class SubjectRef:
    subject_type: str
    subject_entry: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LocationRef:
    map_id: int | None = None
    zone_id: int | None = None
    area_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WMEvent:
    event_class: str
    event_type: str
    source: str
    source_event_key: str
    occurred_at: str = field(default_factory=utcnow_iso)
    player_guid: int | None = None
    subject_type: str | None = None
    subject_entry: int | None = None
    map_id: int | None = None
    zone_id: int | None = None
    area_id: int | None = None
    event_value: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def subject(self) -> SubjectRef | None:
        if self.subject_type is None or self.subject_entry is None:
            return None
        return SubjectRef(subject_type=self.subject_type, subject_entry=self.subject_entry)

    @property
    def location(self) -> LocationRef:
        return LocationRef(map_id=self.map_id, zone_id=self.zone_id, area_id=self.area_id)


@dataclass(slots=True)
class AdapterCursor:
    adapter_name: str
    cursor_key: str
    cursor_value: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReactionCooldownKey:
    rule_type: str
    player_guid: int
    subject_type: str
    subject_entry: int

    def to_reaction_key(self) -> str:
        return f"{self.rule_type}:{self.player_guid}:{self.subject_type}:{self.subject_entry}"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reaction_key"] = self.to_reaction_key()
        return payload


@dataclass(slots=True)
class ReactionOpportunity:
    opportunity_type: str
    rule_type: str
    player_guid: int
    subject: SubjectRef
    source_event_key: str
    metadata: dict[str, Any] = field(default_factory=dict)
    cooldown_seconds: int | None = None

    @property
    def cooldown_key(self) -> ReactionCooldownKey:
        return ReactionCooldownKey(
            rule_type=self.rule_type,
            player_guid=self.player_guid,
            subject_type=self.subject.subject_type,
            subject_entry=self.subject.subject_entry,
        )

    @property
    def reaction_key(self) -> str:
        return self.cooldown_key.to_reaction_key()

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_type": self.opportunity_type,
            "rule_type": self.rule_type,
            "player_guid": self.player_guid,
            "subject": self.subject.to_dict(),
            "source_event_key": self.source_event_key,
            "metadata": self.metadata,
            "cooldown_seconds": self.cooldown_seconds,
            "reaction_key": self.reaction_key,
        }


@dataclass(slots=True)
class PlannedAction:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReactionPlan:
    plan_key: str
    opportunity_type: str
    rule_type: str
    player_guid: int
    subject: SubjectRef
    actions: list[PlannedAction] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    cooldown_key: ReactionCooldownKey | None = None
    cooldown_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_key": self.plan_key,
            "opportunity_type": self.opportunity_type,
            "rule_type": self.rule_type,
            "player_guid": self.player_guid,
            "subject": self.subject.to_dict(),
            "actions": [action.to_dict() for action in self.actions],
            "metadata": self.metadata,
            "cooldown_key": self.cooldown_key.to_dict() if self.cooldown_key is not None else None,
            "cooldown_seconds": self.cooldown_seconds,
        }


@dataclass(slots=True)
class RecordResult:
    recorded: list[WMEvent] = field(default_factory=list)
    skipped: list[WMEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recorded": [event.to_dict() for event in self.recorded],
            "skipped": [event.to_dict() for event in self.skipped],
            "recorded_count": len(self.recorded),
            "skipped_count": len(self.skipped),
        }


@dataclass(slots=True)
class ProjectionResult:
    event_id: int | None
    status: str
    subject_id: int | None = None
    wrote_raw_history: bool = False
    journal_counter_updates: dict[str, int] = field(default_factory=dict)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuleEvaluationResult:
    derived_events: list[WMEvent] = field(default_factory=list)
    opportunities: list[ReactionOpportunity] = field(default_factory=list)
    suppressed_opportunities: list[ReactionOpportunity] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "derived_events": [event.to_dict() for event in self.derived_events],
            "opportunities": [opportunity.to_dict() for opportunity in self.opportunities],
            "suppressed_opportunities": [opportunity.to_dict() for opportunity in self.suppressed_opportunities],
        }


@dataclass(slots=True)
class ExecutionStepResult:
    kind: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionResult:
    mode: str
    plan: ReactionPlan
    status: str
    steps: list[ExecutionStepResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "plan": self.plan.to_dict(),
            "status": self.status,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(slots=True)
class ReactionLogRecord:
    reaction_id: int
    reaction_key: str
    rule_type: str
    status: str
    player_guid: int
    subject: SubjectRef
    planned_actions: dict[str, Any]
    result: dict[str, Any] | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reaction_id": self.reaction_id,
            "reaction_key": self.reaction_key,
            "rule_type": self.rule_type,
            "status": self.status,
            "player_guid": self.player_guid,
            "subject": self.subject.to_dict(),
            "planned_actions": self.planned_actions,
            "result": self.result,
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class ReactionCooldownRecord:
    reaction_key: str
    rule_type: str
    player_guid: int
    subject: SubjectRef
    cooldown_until: str
    last_triggered_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reaction_key": self.reaction_key,
            "rule_type": self.rule_type,
            "player_guid": self.player_guid,
            "subject": self.subject.to_dict(),
            "cooldown_until": self.cooldown_until,
            "last_triggered_at": self.last_triggered_at,
            "metadata": self.metadata,
        }
