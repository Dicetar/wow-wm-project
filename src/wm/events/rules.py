from __future__ import annotations

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import ReactionOpportunity
from wm.events.models import RuleEvaluationResult
from wm.events.models import SubjectRef
from wm.events.models import WMEvent
from wm.events.store import EventStore
from wm.journal.reader import SubjectJournalBundle
from wm.journal.reader import load_subject_journal_for_creature


class DeterministicRuleEngine:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        store: EventStore,
        repeat_kill_threshold: int = 10,
        familiar_talk_threshold: int = 3,
        area_pressure_threshold: int = 5,
        default_cooldown_seconds: int = 3600,
    ) -> None:
        self.client = client
        self.settings = settings
        self.store = store
        self.repeat_kill_threshold = repeat_kill_threshold
        self.familiar_talk_threshold = familiar_talk_threshold
        self.area_pressure_threshold = area_pressure_threshold
        self.default_cooldown_seconds = default_cooldown_seconds

    def evaluate(self, event: WMEvent) -> RuleEvaluationResult:
        result = RuleEvaluationResult()

        if event.event_class != "observed":
            return result
        if event.event_id is not None and self.store.is_evaluated(event_id=event.event_id):
            return result
        if event.player_guid is None or event.subject_type != "creature" or event.subject_entry is None:
            if event.event_id is not None:
                self.store.mark_evaluated(event_id=event.event_id)
            return result

        journal = load_subject_journal_for_creature(
            client=self.client,
            settings=self.settings,
            player_guid=event.player_guid,
            creature_entry=event.subject_entry,
        )

        if event.event_type == "kill":
            self._evaluate_kill(event=event, journal=journal, result=result)
        elif event.event_type == "talk":
            self._evaluate_talk(event=event, journal=journal, result=result)

        if event.event_id is not None:
            self.store.mark_evaluated(event_id=event.event_id)
        return result

    def _evaluate_kill(self, *, event: WMEvent, journal: SubjectJournalBundle, result: RuleEvaluationResult) -> None:
        kill_count = journal.counters.kill_count if journal.counters is not None else 0
        summary_payload = journal.summary.raw if journal.summary is not None else {}
        if kill_count >= self.repeat_kill_threshold:
            result.derived_events.append(
                _derived_event(
                    event=event,
                    derived_type="repeat_hunt_detected",
                    metadata={"kill_count": kill_count, "journal_summary": summary_payload},
                )
            )
            result.derived_events.append(
                _derived_event(
                    event=event,
                    derived_type="followup_eligible",
                    metadata={"reason": "repeat_hunt", "kill_count": kill_count},
                )
            )
            opportunity = ReactionOpportunity(
                opportunity_type="repeat_hunt_followup",
                rule_type="repeat_hunt_followup",
                player_guid=event.player_guid,
                subject=SubjectRef(subject_type=event.subject_type or "creature", subject_entry=event.subject_entry),
                source_event_key=event.source_event_key,
                cooldown_seconds=self.default_cooldown_seconds,
                metadata={
                    "kill_count": kill_count,
                    "trigger_event_type": event.event_type,
                    "subject_name": journal.subject_card.subject_name if journal.subject_card is not None else None,
                    "journal_summary": summary_payload,
                },
            )
            if not self.store.is_cooldown_active(opportunity.cooldown_key, at=event.occurred_at):
                result.opportunities.append(opportunity)

        if event.zone_id is not None and kill_count >= self.area_pressure_threshold:
            result.derived_events.append(
                _derived_event(
                    event=event,
                    derived_type="area_pressure_detected",
                    metadata={"kill_count": kill_count, "zone_id": event.zone_id},
                )
            )
            opportunity = ReactionOpportunity(
                opportunity_type="area_pressure_refresh",
                rule_type="area_pressure_refresh",
                player_guid=event.player_guid,
                subject=SubjectRef(subject_type=event.subject_type or "creature", subject_entry=event.subject_entry),
                source_event_key=event.source_event_key,
                cooldown_seconds=self.default_cooldown_seconds,
                metadata={
                    "kill_count": kill_count,
                    "zone_id": event.zone_id,
                    "subject_name": journal.subject_card.subject_name if journal.subject_card is not None else None,
                },
            )
            if not self.store.is_cooldown_active(opportunity.cooldown_key, at=event.occurred_at):
                result.opportunities.append(opportunity)

    def _evaluate_talk(self, *, event: WMEvent, journal: SubjectJournalBundle, result: RuleEvaluationResult) -> None:
        talk_count = journal.counters.talk_count if journal.counters is not None else 0
        if talk_count < self.familiar_talk_threshold:
            return

        summary_payload = journal.summary.raw if journal.summary is not None else {}
        result.derived_events.append(
            _derived_event(
                event=event,
                derived_type="familiar_npc_detected",
                metadata={"talk_count": talk_count, "journal_summary": summary_payload},
            )
        )
        result.derived_events.append(
            _derived_event(
                event=event,
                derived_type="followup_eligible",
                metadata={"reason": "familiar_npc", "talk_count": talk_count},
            )
        )

        opportunity = ReactionOpportunity(
            opportunity_type="familiar_npc_followup",
            rule_type="familiar_npc_followup",
            player_guid=event.player_guid,
            subject=SubjectRef(subject_type=event.subject_type or "creature", subject_entry=event.subject_entry),
            source_event_key=event.source_event_key,
            cooldown_seconds=self.default_cooldown_seconds,
            metadata={
                "talk_count": talk_count,
                "trigger_event_type": event.event_type,
                "subject_name": journal.subject_card.subject_name if journal.subject_card is not None else None,
                "journal_summary": summary_payload,
            },
        )
        if not self.store.is_cooldown_active(opportunity.cooldown_key, at=event.occurred_at):
            result.opportunities.append(opportunity)


def _derived_event(*, event: WMEvent, derived_type: str, metadata: dict[str, object]) -> WMEvent:
    return WMEvent(
        event_class="derived",
        event_type=derived_type,
        source="wm.rules",
        source_event_key=f"{event.source}:{event.source_event_key}:{derived_type}",
        occurred_at=event.occurred_at,
        player_guid=event.player_guid,
        subject_type=event.subject_type,
        subject_entry=event.subject_entry,
        map_id=event.map_id,
        zone_id=event.zone_id,
        area_id=event.area_id,
        event_value=event.event_value,
        metadata=metadata,
    )
