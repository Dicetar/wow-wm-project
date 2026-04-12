from __future__ import annotations

import hashlib
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import ReactionOpportunity
from wm.events.models import ReactionCooldownKey
from wm.events.models import RuleEvaluationResult
from wm.events.models import SubjectRef
from wm.events.models import WMEvent
from wm.events.store import EventStore
from wm.journal.reader import SubjectJournalBundle
from wm.journal.reader import load_subject_journal_for_creature
from wm.reactive.auto_bounty import ReactiveAutoBountyManager
from wm.reactive.models import PlayerQuestRuntimeState
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.store import ReactiveQuestStore


class DeterministicRuleEngine:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        store: EventStore,
        reactive_store: ReactiveQuestStore | None = None,
        repeat_kill_threshold: int = 10,
        familiar_talk_threshold: int = 3,
        area_pressure_threshold: int = 5,
        default_cooldown_seconds: int = 3600,
        auto_bounty: ReactiveAutoBountyManager | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.store = store
        self.repeat_kill_threshold = repeat_kill_threshold
        self.familiar_talk_threshold = familiar_talk_threshold
        self.area_pressure_threshold = area_pressure_threshold
        self.default_cooldown_seconds = default_cooldown_seconds
        self.reactive_store = reactive_store
        if self.reactive_store is None and settings is not None:
            self.reactive_store = ReactiveQuestStore(client=client, settings=settings)
        self.auto_bounty = auto_bounty
        if self.auto_bounty is None and self.reactive_store is not None and settings is not None:
            self.auto_bounty = ReactiveAutoBountyManager(
                client=client,
                settings=settings,
                reactive_store=self.reactive_store,
            )

    def evaluate(self, event: WMEvent, *, preview: bool = False) -> RuleEvaluationResult:
        return self._evaluate(event, preview=preview, mark_evaluated=(not preview))

    def _evaluate(
        self,
        event: WMEvent,
        *,
        preview: bool = False,
        mark_evaluated: bool = True,
    ) -> RuleEvaluationResult:
        result = RuleEvaluationResult()

        if event.event_class != "observed":
            return result
        if not preview and event.event_id is not None and self.store.is_evaluated(event_id=event.event_id):
            return result
        if event.player_guid is None or event.subject_type != "creature" or event.subject_entry is None:
            if mark_evaluated and event.event_id is not None:
                self.store.mark_evaluated(event_id=event.event_id)
            return result

        if event.event_type == "kill":
            reactive_rules_present = self._evaluate_reactive_kill_burst(event=event, result=result, preview=preview)
            if not reactive_rules_present:
                journal = load_subject_journal_for_creature(
                    client=self.client,
                    settings=self.settings,
                    player_guid=event.player_guid,
                    creature_entry=event.subject_entry,
                )
                self._evaluate_kill(event=event, journal=journal, result=result)
        elif event.event_type == "talk":
            journal = load_subject_journal_for_creature(
                client=self.client,
                settings=self.settings,
                player_guid=event.player_guid,
                creature_entry=event.subject_entry,
            )
            self._evaluate_talk(event=event, journal=journal, result=result)

        if mark_evaluated and event.event_id is not None:
            self.store.mark_evaluated(event_id=event.event_id)
        return result

    def _evaluate_reactive_kill_burst(
        self,
        *,
        event: WMEvent,
        result: RuleEvaluationResult,
        preview: bool,
    ) -> bool:
        if self.reactive_store is None:
            return False

        rules = self.reactive_store.list_active_rules(
            subject_type=event.subject_type,
            trigger_event_type=event.event_type,
            player_guid=event.player_guid,
        )
        rules = [rule for rule in rules if _rule_matches_event(rule=rule, event=event)]
        if not rules and not preview and self.auto_bounty is not None:
            auto_rule = self.auto_bounty.ensure_rule_for_event(event)
            if auto_rule is not None:
                rules = self.reactive_store.list_active_rules(
                    subject_type=event.subject_type,
                    trigger_event_type=event.event_type,
                    player_guid=event.player_guid,
                )
                rules = [rule for rule in rules if _rule_matches_event(rule=rule, event=event)]
        if not rules:
            return False

        recent_observed_events = self.store.list_recent_events(
            event_class="observed",
            player_guid=int(event.player_guid or 0),
            limit=400,
            newest_first=False,
        )
        for rule in rules:
            self._evaluate_reactive_rule(
                event=event,
                rule=rule,
                recent_kills=[
                    candidate
                    for candidate in recent_observed_events
                    if candidate.event_type == event.event_type
                    and candidate.subject_type == event.subject_type
                    and _rule_matches_event(rule=rule, event=candidate)
                ],
                result=result,
            )
        return True

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
            else:
                result.suppressed_opportunities.append(
                    _suppressed_opportunity(opportunity=opportunity, reason="cooldown_active")
                )

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
            else:
                result.suppressed_opportunities.append(
                    _suppressed_opportunity(opportunity=opportunity, reason="cooldown_active")
                )

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
        else:
            result.suppressed_opportunities.append(
                _suppressed_opportunity(opportunity=opportunity, reason="cooldown_active")
            )

    def _evaluate_reactive_rule(
        self,
        *,
        event: WMEvent,
        rule: ReactiveQuestRule,
        recent_kills: list[WMEvent],
        result: RuleEvaluationResult,
    ) -> None:
        if rule.player_guid_scope is not None and rule.player_guid_scope != event.player_guid:
            opportunity = _reactive_opportunity(
                event=event,
                rule=rule,
                metadata={"suppression_reason": "player_scope_mismatch"},
            )
            result.suppressed_opportunities.append(
                _suppressed_opportunity(opportunity=opportunity, reason="player_scope_mismatch")
            )
            return

        burst = _kill_burst_window(
            recent_kills=recent_kills,
            current_event=event,
            window_seconds=rule.window_seconds,
            threshold=rule.kill_threshold,
        )
        if not burst["threshold_crossed"]:
            return

        result.derived_events.append(
            _derived_event(
                event=event,
                derived_type="kill_burst_detected",
                metadata={
                    "rule_key": rule.rule_key,
                    "quest_id": rule.quest_id,
                    "window_seconds": rule.window_seconds,
                    "kill_threshold": rule.kill_threshold,
                    "kills_in_window": burst["kills_in_window"],
                },
            )
        )

        current_state = self.reactive_store.fetch_character_quest_status(
            player_guid=int(event.player_guid or 0),
            quest_id=rule.quest_id,
        )
        snapshot = self.reactive_store.get_player_quest_runtime_state(
            player_guid=int(event.player_guid or 0),
            quest_id=rule.quest_id,
        )

        opportunity = _reactive_opportunity(
            event=event,
            rule=rule,
            metadata={
                "subject_name": _subject_name_from_event(event),
                "quest_id": rule.quest_id,
                "turn_in_npc_entry": rule.turn_in_npc_entry,
                "grant_mode": rule.grant_mode,
                "window_seconds": rule.window_seconds,
                "kill_threshold": rule.kill_threshold,
                "kills_in_window": burst["kills_in_window"],
                "trigger_event_id": event.event_id,
                "runtime_state": current_state,
                "reactive_rule": rule.to_dict(),
            },
        )

        if current_state == "incomplete":
            result.suppressed_opportunities.append(
                _suppressed_opportunity(opportunity=opportunity, reason="quest_active")
            )
            return
        if current_state == "complete":
            result.suppressed_opportunities.append(
                _suppressed_opportunity(opportunity=opportunity, reason="quest_complete_pending_turnin")
            )
            return
        if current_state == "rewarded" and _post_reward_cooldown_active(
            store=self.store,
            snapshot=snapshot,
            rule=rule,
            event=event,
            player_guid=int(event.player_guid or 0),
        ):
            result.suppressed_opportunities.append(
                _suppressed_opportunity(opportunity=opportunity, reason="post_reward_cooldown_active")
            )
            return

        result.opportunities.append(opportunity)


def _derived_event(*, event: WMEvent, derived_type: str, metadata: dict[str, object]) -> WMEvent:
    source_event_key = _derived_source_event_key(event=event, derived_type=derived_type)
    return WMEvent(
        event_class="derived",
        event_type=derived_type,
        source="wm.rules",
        source_event_key=source_event_key,
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


def _suppressed_opportunity(*, opportunity: ReactionOpportunity, reason: str) -> ReactionOpportunity:
    metadata = dict(opportunity.metadata)
    metadata["suppression_reason"] = reason
    return ReactionOpportunity(
        opportunity_type=opportunity.opportunity_type,
        rule_type=opportunity.rule_type,
        player_guid=opportunity.player_guid,
        subject=opportunity.subject,
        source_event_key=opportunity.source_event_key,
        metadata=metadata,
        cooldown_seconds=opportunity.cooldown_seconds,
    )


def _reactive_opportunity(
    *,
    event: WMEvent,
    rule: ReactiveQuestRule,
    metadata: dict[str, object],
) -> ReactionOpportunity:
    return ReactionOpportunity(
        opportunity_type="reactive_bounty_grant",
        rule_type=rule.rule_key,
        player_guid=int(event.player_guid or 0),
        subject=SubjectRef(subject_type=rule.subject_type, subject_entry=rule.subject_entry),
        source_event_key=event.source_event_key,
        metadata=metadata,
        cooldown_seconds=None,
    )


def _derived_source_event_key(*, event: WMEvent, derived_type: str) -> str:
    raw = f"{event.source}:{event.source_event_key}:{derived_type}"
    if len(raw) <= 120:
        return raw
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"{event.source}:{derived_type}:{digest}"


def _subject_name_from_event(event: WMEvent) -> str | None:
    for key in ("subject_name", "journal_subject_name"):
        raw_value = event.metadata.get(key)
        if isinstance(raw_value, str) and raw_value.strip():
            return raw_value.strip()
    payload = event.metadata.get("payload")
    if isinstance(payload, dict):
        raw_value = payload.get("subject_name")
        if isinstance(raw_value, str) and raw_value.strip():
            return raw_value.strip()
    return None


def _rule_matches_event(*, rule: ReactiveQuestRule, event: WMEvent) -> bool:
    if rule.subject_type != (event.subject_type or ""):
        return False
    name_prefix = rule.metadata.get("auto_bounty_name_prefix")
    if isinstance(name_prefix, str) and name_prefix.strip():
        subject_name = _subject_name_from_event(event)
        return isinstance(subject_name, str) and subject_name.lower().startswith(name_prefix.strip().lower())
    return int(rule.subject_entry) == int(event.subject_entry or 0)


def _kill_burst_window(
    *,
    recent_kills: list[WMEvent],
    current_event: WMEvent,
    window_seconds: int,
    threshold: int,
) -> dict[str, int | bool]:
    current_at = _parse_timestamp(current_event.occurred_at)
    if current_at is None:
        return {"kills_in_window": 0, "count_before_current": 0, "threshold_crossed": False}

    cutoff = current_at - timedelta(seconds=max(1, int(window_seconds)))
    kills_in_window = 0
    count_before_current = 0
    for candidate in recent_kills:
        candidate_at = _parse_timestamp(candidate.occurred_at)
        if candidate_at is None or candidate_at < cutoff:
            continue
        if _event_after(candidate, current_event, candidate_at=candidate_at, current_at=current_at):
            continue
        kills_in_window += 1
        if _event_before(candidate, current_event, candidate_at=candidate_at, current_at=current_at):
            count_before_current += 1

    threshold_crossed = count_before_current < int(threshold) <= kills_in_window
    return {
        "kills_in_window": kills_in_window,
        "count_before_current": count_before_current,
        "threshold_crossed": threshold_crossed,
    }


def _event_before(
    candidate: WMEvent,
    current_event: WMEvent,
    *,
    candidate_at: datetime,
    current_at: datetime,
) -> bool:
    if candidate_at < current_at:
        return True
    if candidate_at > current_at:
        return False
    candidate_event_id = candidate.event_id or 0
    current_event_id = current_event.event_id or 0
    if candidate_event_id and current_event_id:
        return candidate_event_id < current_event_id
    return candidate.source_event_key < current_event.source_event_key


def _event_after(
    candidate: WMEvent,
    current_event: WMEvent,
    *,
    candidate_at: datetime,
    current_at: datetime,
) -> bool:
    if candidate_at > current_at:
        return True
    if candidate_at < current_at:
        return False
    candidate_event_id = candidate.event_id or 0
    current_event_id = current_event.event_id or 0
    if candidate_event_id and current_event_id:
        return candidate_event_id > current_event_id
    return candidate.source_event_key > current_event.source_event_key


def _post_reward_cooldown_active(
    *,
    store: EventStore,
    snapshot: PlayerQuestRuntimeState | None,
    rule: ReactiveQuestRule,
    event: WMEvent,
    player_guid: int,
) -> bool:
    key = ReactionCooldownKey(
        rule_type=rule.rule_key,
        player_guid=player_guid,
        subject_type=rule.subject_type,
        subject_entry=rule.subject_entry,
    )
    if store.is_cooldown_active(key, at=event.occurred_at):
        return True
    if snapshot is None or snapshot.last_transition_at in (None, ""):
        return True
    transition_at = _parse_timestamp(snapshot.last_transition_at)
    event_at = _parse_timestamp(event.occurred_at)
    if transition_at is None or event_at is None:
        return True
    return (event_at - transition_at).total_seconds() < int(rule.post_reward_cooldown_seconds)


def _parse_timestamp(value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
