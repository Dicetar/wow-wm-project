from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import time
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import ReactionCooldownKey, WMEvent
from wm.events.run import _apply_settings_overrides, _emit_output, _validate_run_arguments, execute_event_spine
from wm.events.store import EventStore
from wm.quests.generate_bounty import LiveCreatureResolver
from wm.quests.template_publish import ReputationReward, RichBountyQuestDraft, RichQuestTemplatePublisher
from wm.reserved.db_allocator import ReservedSlotDbAllocator


@dataclass(slots=True)
class SubjectMatchRule:
    entries: list[int] = field(default_factory=list)
    faction_labels: list[str] = field(default_factory=list)
    mechanical_types: list[str] = field(default_factory=list)
    families: list[str] = field(default_factory=list)
    name_prefixes: list[str] = field(default_factory=list)
    name_contains: list[str] = field(default_factory=list)
    zone_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TemplateReward:
    money_copper: int = 0
    experience: int | None = None
    reward_item_entry: int | None = None
    reward_item_name: str | None = None
    reward_item_count: int = 1
    reward_spell_cast_id: int | None = None
    reward_spell_id: int | None = None
    reputations: list[ReputationReward] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reputations"] = [reward.to_dict() for reward in self.reputations]
        return payload


@dataclass(slots=True)
class QuestPublishTemplate:
    turn_in_npc_entry: int
    grant_mode: str = "npc_start"
    followup_kill_count: int = 5
    quest_level: int | None = None
    min_level: int | None = None
    start_npc_entry: int | None = None
    end_npc_entry: int | None = None
    title_template: str = "Bounty: {target_name}"
    quest_description_template: str = (
        "{turn_in_npc_name} wants the recent attack on {target_name} pushed back before it spreads."
    )
    objective_text_template: str = "Slay {followup_kill_count} more {target_name}."
    offer_reward_text_template: str = (
        "{turn_in_npc_name} nods. The pressure from {target_name} should ease for a while."
    )
    request_items_text_template: str = (
        "Drive back {followup_kill_count} more {target_name}, then return to {turn_in_npc_name}."
    )
    tags: list[str] = field(default_factory=list)
    template_defaults: dict[str, Any] = field(default_factory=dict)
    reward: TemplateReward = field(default_factory=TemplateReward)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reward"] = self.reward.to_dict()
        return payload


@dataclass(slots=True)
class EventQuestTemplate:
    template_key: str
    trigger_event_type: str = "kill"
    threshold_count: int = 5
    window_seconds: int = 30
    cooldown_seconds: int = 900
    subject_match: SubjectMatchRule = field(default_factory=SubjectMatchRule)
    publish: QuestPublishTemplate = field(default_factory=lambda: QuestPublishTemplate(turn_in_npc_entry=240))
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_key": self.template_key,
            "trigger_event_type": self.trigger_event_type,
            "threshold_count": self.threshold_count,
            "window_seconds": self.window_seconds,
            "cooldown_seconds": self.cooldown_seconds,
            "subject_match": self.subject_match.to_dict(),
            "publish": self.publish.to_dict(),
            "description": self.description,
        }


@dataclass(slots=True)
class TemplateTriggerResult:
    template_key: str
    matched: bool
    trigger_event_key: str | None = None
    quest_id: int | None = None
    subject_entry: int | None = None
    subject_name: str | None = None
    status: str = "idle"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TemplateWatcher:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        store: EventStore | None = None,
        resolver: LiveCreatureResolver | None = None,
        slot_allocator: ReservedSlotDbAllocator | None = None,
        publisher: RichQuestTemplatePublisher | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.store = store or EventStore(client=client, settings=settings)
        self.resolver = resolver or LiveCreatureResolver(client=client, settings=settings)
        self.slot_allocator = slot_allocator or ReservedSlotDbAllocator(client=client, settings=settings)
        self.publisher = publisher or RichQuestTemplatePublisher(client=client, settings=settings)

    def evaluate_templates(
        self,
        *,
        templates: list[EventQuestTemplate],
        player_guid: int,
        mode: str,
        runtime_sync_mode: str,
    ) -> list[TemplateTriggerResult]:
        results: list[TemplateTriggerResult] = []
        for template in templates:
            results.append(
                self._evaluate_template(
                    template=template,
                    player_guid=player_guid,
                    mode=mode,
                    runtime_sync_mode=runtime_sync_mode,
                )
            )
        return results

    def _evaluate_template(
        self,
        *,
        template: EventQuestTemplate,
        player_guid: int,
        mode: str,
        runtime_sync_mode: str,
    ) -> TemplateTriggerResult:
        match = self._find_threshold_crossing(template=template, player_guid=player_guid)
        if match is None:
            return TemplateTriggerResult(template_key=template.template_key, matched=False, status="idle")

        trigger_event, target_result, kill_count_in_window = match
        cooldown_key = ReactionCooldownKey(
            rule_type=f"template_watch:{template.template_key}",
            player_guid=int(player_guid),
            subject_type="creature",
            subject_entry=int(target_result.entry),
        )
        if self.store.is_cooldown_active(cooldown_key, at=trigger_event.occurred_at):
            return TemplateTriggerResult(
                template_key=template.template_key,
                matched=True,
                trigger_event_key=trigger_event.source_event_key,
                subject_entry=target_result.entry,
                subject_name=target_result.name,
                status="cooldown_active",
                details={"kills_in_window": kill_count_in_window},
            )

        rendered = self._render_draft(
            template=template,
            player_guid=player_guid,
            trigger_event=trigger_event,
            target_result=target_result,
            mode=mode,
        )
        if rendered is None:
            return TemplateTriggerResult(
                template_key=template.template_key,
                matched=True,
                trigger_event_key=trigger_event.source_event_key,
                subject_entry=target_result.entry,
                subject_name=target_result.name,
                status="no_free_slot",
                details={"kills_in_window": kill_count_in_window},
            )

        draft, slot_status = rendered
        publish_result = self.publisher.publish(
            draft=draft,
            mode=mode,
            runtime_sync_mode=runtime_sync_mode,
        )

        status = "dry-run" if mode != "apply" else "published" if publish_result.applied else "publish_failed"
        result = TemplateTriggerResult(
            template_key=template.template_key,
            matched=True,
            trigger_event_key=trigger_event.source_event_key,
            quest_id=int(draft.quest_id),
            subject_entry=target_result.entry,
            subject_name=target_result.name,
            status=status,
            details={
                "kills_in_window": kill_count_in_window,
                "slot_status": slot_status,
                "draft": draft.to_dict(),
                "publish": publish_result.to_dict(),
            },
        )

        if mode == "apply" and publish_result.applied:
            self.store.set_cooldown(
                key=cooldown_key,
                cooldown_seconds=int(template.cooldown_seconds),
                triggered_at=trigger_event.occurred_at,
                metadata={
                    "template_key": template.template_key,
                    "quest_id": int(draft.quest_id),
                    "trigger_event_key": trigger_event.source_event_key,
                },
            )
            self.store.record(
                [
                    WMEvent(
                        event_class="action",
                        event_type="quest_published",
                        source="wm.template_watch",
                        source_event_key=f"{template.template_key}:{draft.quest_id}:{trigger_event.source_event_key}",
                        occurred_at=trigger_event.occurred_at,
                        player_guid=int(player_guid),
                        subject_type="creature",
                        subject_entry=int(target_result.entry),
                        event_value=str(draft.quest_id),
                        metadata={
                            "template_key": template.template_key,
                            "kills_in_window": kill_count_in_window,
                            "slot_status": slot_status,
                        },
                    )
                ]
            )
        return result

    def _render_draft(
        self,
        *,
        template: EventQuestTemplate,
        player_guid: int,
        trigger_event: WMEvent,
        target_result: Any,
        mode: str,
    ) -> tuple[RichBountyQuestDraft, str] | None:
        turn_in_result = self.resolver.resolve(entry=int(template.publish.turn_in_npc_entry))
        if mode == "apply":
            slot = self.slot_allocator.allocate_next_free_slot(
                entity_type="quest",
                arc_key=f"template_watch:{template.template_key}",
                character_guid=int(player_guid),
                notes=[
                    f"template_key:{template.template_key}",
                    f"trigger_event:{trigger_event.source_event_key}",
                    f"subject_entry:{int(target_result.entry)}",
                ],
            )
            if slot is None:
                return None
            slot_status = slot.slot_status
            quest_id = int(slot.reserved_id)
        else:
            slot = self.slot_allocator.peek_next_free_slot(entity_type="quest")
            if slot is None:
                return None
            slot_status = slot.slot_status
            quest_id = int(slot.reserved_id)

        template_defaults = dict(self.resolver.fetch_template_defaults_for_questgiver(turn_in_result.entry))
        template_defaults.update({str(k): v for k, v in template.publish.template_defaults.items()})

        quest_level = (
            int(template.publish.quest_level)
            if template.publish.quest_level not in (None, "")
            else max(int(target_result.profile.level_max), 1)
        )
        min_level = (
            int(template.publish.min_level)
            if template.publish.min_level not in (None, "")
            else max(int(quest_level) - 2, 1)
        )

        context = {
            "quest_id": quest_id,
            "target_entry": int(target_result.entry),
            "target_name": str(target_result.name),
            "turn_in_npc_entry": int(turn_in_result.entry),
            "turn_in_npc_name": str(turn_in_result.name),
            "followup_kill_count": int(template.publish.followup_kill_count),
            "threshold_count": int(template.threshold_count),
            "window_seconds": int(template.window_seconds),
            "player_guid": int(player_guid),
            "zone_id": trigger_event.zone_id,
            "area_id": trigger_event.area_id,
            "map_id": trigger_event.map_id,
        }

        start_npc_entry = template.publish.start_npc_entry
        end_npc_entry = template.publish.end_npc_entry
        if start_npc_entry in (None, "") and template.publish.grant_mode != "direct_quest_add":
            start_npc_entry = int(turn_in_result.entry)
        if end_npc_entry in (None, ""):
            end_npc_entry = int(turn_in_result.entry)

        reward = template.publish.reward
        tags = list(dict.fromkeys(
            [str(tag) for tag in template.publish.tags]
            + ["wm_generated", "template_watch", template.template_key, str(target_result.profile.mechanical_type).lower()]
        ))
        if target_result.profile.family not in (None, ""):
            tags.append(str(target_result.profile.family).lower())

        draft = RichBountyQuestDraft(
            quest_id=int(quest_id),
            quest_level=int(quest_level),
            min_level=int(min_level),
            questgiver_entry=int(turn_in_result.entry),
            questgiver_name=str(turn_in_result.name),
            title=_render_template(template.publish.title_template, context),
            quest_description=_render_template(template.publish.quest_description_template, context),
            objective_text=_render_template(template.publish.objective_text_template, context),
            offer_reward_text=_render_template(template.publish.offer_reward_text_template, context),
            request_items_text=_render_template(template.publish.request_items_text_template, context),
            target_entry=int(target_result.entry),
            target_name=str(target_result.name),
            kill_count=int(template.publish.followup_kill_count),
            reward_money_copper=int(reward.money_copper),
            reward_item_entry=(int(reward.reward_item_entry) if reward.reward_item_entry not in (None, "") else None),
            reward_item_name=reward.reward_item_name,
            reward_item_count=int(reward.reward_item_count),
            reward_experience=(int(reward.experience) if reward.experience not in (None, "") else None),
            reward_spell_cast_id=(int(reward.reward_spell_cast_id) if reward.reward_spell_cast_id not in (None, "") else None),
            reward_spell_id=(int(reward.reward_spell_id) if reward.reward_spell_id not in (None, "") else None),
            reward_reputations=[ReputationReward(faction_id=int(rep.faction_id), value=int(rep.value)) for rep in reward.reputations],
            start_npc_entry=(int(start_npc_entry) if start_npc_entry not in (None, "") else None),
            end_npc_entry=(int(end_npc_entry) if end_npc_entry not in (None, "") else None),
            grant_mode=str(template.publish.grant_mode),
            tags=tags,
            template_defaults=template_defaults,
        )
        return draft, slot_status

    def _find_threshold_crossing(
        self,
        *,
        template: EventQuestTemplate,
        player_guid: int,
    ) -> tuple[WMEvent, Any, int] | None:
        recent_events = self.store.list_recent_events(
            event_class="observed",
            player_guid=int(player_guid),
            limit=400,
            newest_first=False,
        )
        matching_events: list[tuple[WMEvent, Any]] = []
        for event in recent_events:
            if event.event_type != template.trigger_event_type:
                continue
            target_result = _resolve_target(self.resolver, event)
            if target_result is None:
                continue
            if not subject_matches_template(template.subject_match, event=event, target_result=target_result):
                continue
            matching_events.append((event, target_result))

        for index, (event, target_result) in enumerate(matching_events):
            count_before, count_in_window = _burst_counts(
                events=[candidate for candidate, _ in matching_events],
                current_index=index,
                window_seconds=int(template.window_seconds),
            )
            if count_before < int(template.threshold_count) <= count_in_window:
                return event, target_result, count_in_window
        return None


def load_event_quest_templates(paths: list[Path]) -> list[EventQuestTemplate]:
    templates: list[EventQuestTemplate] = []
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"Template file {path} must contain an object or a list of objects.")
            subject_match_raw = item.get("subject_match") or {}
            reward_raw = ((item.get("publish") or {}).get("reward") or {})
            templates.append(
                EventQuestTemplate(
                    template_key=str(item["template_key"]),
                    trigger_event_type=str(item.get("trigger_event_type") or "kill"),
                    threshold_count=int(item.get("threshold_count") or 5),
                    window_seconds=int(item.get("window_seconds") or 30),
                    cooldown_seconds=int(item.get("cooldown_seconds") or 900),
                    description=(str(item["description"]) if item.get("description") not in (None, "") else None),
                    subject_match=SubjectMatchRule(
                        entries=[int(value) for value in subject_match_raw.get("entries", [])],
                        faction_labels=[str(value).strip() for value in subject_match_raw.get("faction_labels", [])],
                        mechanical_types=[str(value).strip() for value in subject_match_raw.get("mechanical_types", [])],
                        families=[str(value).strip() for value in subject_match_raw.get("families", [])],
                        name_prefixes=[str(value) for value in subject_match_raw.get("name_prefixes", [])],
                        name_contains=[str(value) for value in subject_match_raw.get("name_contains", [])],
                        zone_ids=[int(value) for value in subject_match_raw.get("zone_ids", [])],
                    ),
                    publish=QuestPublishTemplate(
                        turn_in_npc_entry=int((item.get("publish") or {})["turn_in_npc_entry"]),
                        grant_mode=str((item.get("publish") or {}).get("grant_mode") or "npc_start"),
                        followup_kill_count=int((item.get("publish") or {}).get("followup_kill_count") or 5),
                        quest_level=(
                            int((item.get("publish") or {})["quest_level"])
                            if (item.get("publish") or {}).get("quest_level") not in (None, "")
                            else None
                        ),
                        min_level=(
                            int((item.get("publish") or {})["min_level"])
                            if (item.get("publish") or {}).get("min_level") not in (None, "")
                            else None
                        ),
                        start_npc_entry=(
                            int((item.get("publish") or {})["start_npc_entry"])
                            if (item.get("publish") or {}).get("start_npc_entry") not in (None, "")
                            else None
                        ),
                        end_npc_entry=(
                            int((item.get("publish") or {})["end_npc_entry"])
                            if (item.get("publish") or {}).get("end_npc_entry") not in (None, "")
                            else None
                        ),
                        title_template=str((item.get("publish") or {}).get("title_template") or "Bounty: {target_name}"),
                        quest_description_template=str(
                            (item.get("publish") or {}).get("quest_description_template")
                            or "{turn_in_npc_name} wants the recent attack on {target_name} pushed back before it spreads."
                        ),
                        objective_text_template=str(
                            (item.get("publish") or {}).get("objective_text_template")
                            or "Slay {followup_kill_count} more {target_name}."
                        ),
                        offer_reward_text_template=str(
                            (item.get("publish") or {}).get("offer_reward_text_template")
                            or "{turn_in_npc_name} nods. The pressure from {target_name} should ease for a while."
                        ),
                        request_items_text_template=str(
                            (item.get("publish") or {}).get("request_items_text_template")
                            or "Drive back {followup_kill_count} more {target_name}, then return to {turn_in_npc_name}."
                        ),
                        tags=[str(value) for value in (item.get("publish") or {}).get("tags", [])],
                        template_defaults={str(k): v for k, v in ((item.get("publish") or {}).get("template_defaults") or {}).items()},
                        reward=TemplateReward(
                            money_copper=int(reward_raw.get("money_copper", 0)),
                            experience=(int(reward_raw["experience"]) if reward_raw.get("experience") not in (None, "") else None),
                            reward_item_entry=(int(reward_raw["reward_item_entry"]) if reward_raw.get("reward_item_entry") not in (None, "") else None),
                            reward_item_name=(str(reward_raw["reward_item_name"]) if reward_raw.get("reward_item_name") not in (None, "") else None),
                            reward_item_count=int(reward_raw.get("reward_item_count", 1)),
                            reward_spell_cast_id=(int(reward_raw["reward_spell_cast_id"]) if reward_raw.get("reward_spell_cast_id") not in (None, "") else None),
                            reward_spell_id=(int(reward_raw["reward_spell_id"]) if reward_raw.get("reward_spell_id") not in (None, "") else None),
                            reputations=[
                                ReputationReward(
                                    faction_id=int(rep["faction_id"]),
                                    value=int(rep["value"]),
                                )
                                for rep in reward_raw.get("reputations", [])
                            ],
                        ),
                    ),
                )
            )
    return templates


def subject_matches_template(
    matcher: SubjectMatchRule,
    *,
    event: WMEvent,
    target_result: Any,
) -> bool:
    if event.subject_type != "creature" or event.subject_entry in (None, ""):
        return False
    if matcher.entries and int(event.subject_entry) not in {int(value) for value in matcher.entries}:
        return False
    if matcher.zone_ids and int(event.zone_id or 0) not in {int(value) for value in matcher.zone_ids}:
        return False

    profile = target_result.profile
    subject_name = str(target_result.name or "").strip().lower()
    faction_label = str(profile.faction_label or "").strip().lower()
    mechanical_type = str(profile.mechanical_type or "").strip().lower()
    family = str(profile.family or "").strip().lower()

    if matcher.faction_labels and faction_label not in {str(value).strip().lower() for value in matcher.faction_labels}:
        return False
    if matcher.mechanical_types and mechanical_type not in {str(value).strip().lower() for value in matcher.mechanical_types}:
        return False
    if matcher.families and family not in {str(value).strip().lower() for value in matcher.families}:
        return False
    if matcher.name_prefixes and not any(subject_name.startswith(str(value).strip().lower()) for value in matcher.name_prefixes):
        return False
    if matcher.name_contains and not any(str(value).strip().lower() in subject_name for value in matcher.name_contains):
        return False
    return True


def _resolve_target(resolver: LiveCreatureResolver, event: WMEvent) -> Any | None:
    if event.subject_type != "creature" or event.subject_entry in (None, ""):
        return None
    try:
        return resolver.resolve(entry=int(event.subject_entry))
    except Exception:
        return None


def _burst_counts(*, events: list[WMEvent], current_index: int, window_seconds: int) -> tuple[int, int]:
    current_event = events[current_index]
    current_at = _parse_timestamp(current_event.occurred_at)
    if current_at is None:
        return (0, 0)
    cutoff = current_at.timestamp() - max(1, int(window_seconds))
    count_before = 0
    count_in_window = 0
    for index, candidate in enumerate(events):
        candidate_at = _parse_timestamp(candidate.occurred_at)
        if candidate_at is None:
            continue
        candidate_ts = candidate_at.timestamp()
        if candidate_ts < cutoff:
            continue
        if _event_after(candidate, current_event, candidate_at=candidate_at, current_at=current_at):
            continue
        count_in_window += 1
        if index < current_index:
            count_before += 1
    return count_before, count_in_window


def _event_after(
    candidate: WMEvent,
    current_event: WMEvent,
    *,
    candidate_at: Any,
    current_at: Any,
) -> bool:
    if candidate_at > current_at:
        return True
    if candidate_at < current_at:
        return False
    candidate_event_id = candidate.event_id or 0
    current_event_db_id = current_event.event_id or 0
    if candidate_event_id and current_event_db_id:
        return candidate_event_id > current_event_db_id
    return candidate.source_event_key > current_event.source_event_key


def _parse_timestamp(value: str | None) -> Any | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    from datetime import datetime, timezone

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


def _render_template(template: str, context: dict[str, Any]) -> str:
    return str(template).format_map(_SafeFormatDict({key: "" if value is None else value for key, value in context.items()}))


class _SafeFormatDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Watch WM events and publish quests from JSON templates.")
    parser.add_argument("--template-json", type=Path, nargs="+", required=True)
    parser.add_argument("--adapter", choices=["db", "addon_log", "combat_log", "native_bridge"], default="db")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--questgiver-entry", type=int)
    parser.add_argument("--confirm-live-apply", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    _apply_settings_overrides(args=args, settings=settings)
    _validate_run_arguments(args=args, settings=settings)

    templates = load_event_quest_templates(args.template_json)
    client = MysqlCliClient()
    store = EventStore(client=client, settings=settings)
    watcher = TemplateWatcher(client=client, settings=settings, store=store)

    iteration = 0
    payloads: list[dict[str, Any]] = []
    try:
        while True:
            iteration += 1
            spine_payload = execute_event_spine(
                settings=settings,
                adapter_name=args.adapter,
                mode=args.mode,
                player_guid=args.player_guid,
                batch_size=args.batch_size,
            )
            trigger_results = watcher.evaluate_templates(
                templates=templates,
                player_guid=int(args.player_guid),
                mode=args.mode,
                runtime_sync_mode=args.runtime_sync,
            )
            payload = {
                **spine_payload,
                "iteration": iteration,
                "template_result_count": len(trigger_results),
                "template_results": [result.to_dict() for result in trigger_results],
            }
            payloads.append(payload)

            if args.summary:
                print(
                    f"iteration={iteration} adapter={args.adapter} mode={args.mode} "
                    f"polled={payload.get('polled_count', 0)} opportunities={payload.get('opportunity_count', 0)} "
                    f"template_matches={sum(1 for result in trigger_results if result.matched)}"
                )
                for result in trigger_results:
                    if result.matched or result.status != "idle":
                        print(
                            f"- {result.template_key} | {result.status} | subject={result.subject_entry}:{result.subject_name} | "
                            f"quest_id={result.quest_id}"
                        )

            if args.max_iterations is not None and iteration >= int(args.max_iterations):
                break
            time.sleep(max(float(args.interval_seconds), 0.1))
    except KeyboardInterrupt:
        if args.summary:
            print("template_watch_stopped=true")
        return 130

    final_payload = payloads[-1] if payloads else {"template_results": []}
    raw = json.dumps(final_payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if not args.summary:
        _emit_output(payload=final_payload, summary=False, output_json=None)
    return 0


__all__ = [
    "EventQuestTemplate",
    "QuestPublishTemplate",
    "SubjectMatchRule",
    "TemplateReward",
    "TemplateTriggerResult",
    "TemplateWatcher",
    "load_event_quest_templates",
    "main",
    "subject_matches_template",
]


if __name__ == "__main__":
    raise SystemExit(main())
