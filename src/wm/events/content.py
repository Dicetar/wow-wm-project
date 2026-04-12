from __future__ import annotations

from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import PlannedAction
from wm.events.models import ReactionOpportunity
from wm.refs import CreatureRef
from wm.refs import NpcRef
from wm.refs import PlayerRef
from wm.refs import QuestRef
from wm.quests.bounty import build_bounty_quest_draft
from wm.quests.generate_bounty import LiveCreatureResolver
from wm.reserved.db_allocator import ReservedSlotDbAllocator


class DeterministicContentFactory:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        slot_allocator: ReservedSlotDbAllocator | None = None,
        resolver: LiveCreatureResolver | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.slot_allocator = slot_allocator or ReservedSlotDbAllocator(client=client, settings=settings)
        self.resolver = resolver or LiveCreatureResolver(client=client, settings=settings)

    def build_actions(self, opportunity: ReactionOpportunity) -> tuple[list[PlannedAction], dict[str, Any]]:
        if opportunity.opportunity_type == "reactive_bounty_grant":
            return self._build_reactive_bounty_grant_actions(opportunity)
        if opportunity.rule_type == "repeat_hunt_followup":
            return self._build_repeat_hunt_actions(opportunity)
        if opportunity.rule_type == "area_pressure_refresh":
            return self._build_area_pressure_actions(opportunity)
        if opportunity.rule_type == "familiar_npc_followup":
            return self._build_familiar_npc_actions(opportunity)
        return ([], {})

    def _build_repeat_hunt_actions(self, opportunity: ReactionOpportunity) -> tuple[list[PlannedAction], dict[str, Any]]:
        subject_name = _subject_name(opportunity)
        notes: dict[str, Any] = {
            "subject_name": subject_name,
            "content_factory": "deterministic_repeat_hunt",
        }
        actions: list[PlannedAction] = []

        questgiver_entry = self.settings.event_default_questgiver_entry
        if questgiver_entry is None:
            actions.append(
                PlannedAction(
                    kind="announcement",
                    payload={"text": f"Hunting pressure around {subject_name} is rising, but no default questgiver is configured."},
                    description="Emit a deterministic operator-facing announcement when no questgiver is configured.",
                )
            )
            notes["quest_generation"] = "skipped_missing_default_questgiver"
            return actions, notes

        try:
            target = self.resolver.resolve(entry=opportunity.subject.subject_entry)
            questgiver = self.resolver.resolve(entry=questgiver_entry)
            template_defaults = self.resolver.fetch_template_defaults_for_questgiver(questgiver.entry)
            slot = self.slot_allocator.peek_next_free_slot(entity_type="quest")
        except Exception as exc:
            actions.append(
                PlannedAction(
                    kind="announcement",
                    payload={"text": f"Hunting pressure around {subject_name} is rising, but deterministic quest setup failed."},
                    description="Announce that repeat-hunt content setup failed and requires operator attention.",
                )
            )
            notes["quest_generation"] = "skipped_lookup_failure"
            notes["error"] = str(exc)
            return actions, notes

        notes["questgiver_entry"] = questgiver.entry
        notes["questgiver_name"] = questgiver.name
        notes["target_entry"] = target.entry
        notes["target_name"] = target.name

        if slot is not None:
            kill_count = max(1, int(self.settings.event_followup_kill_count))
            reward_money = max(0, int(self.settings.event_default_reward_money_copper))
            draft = build_bounty_quest_draft(
                quest_id=slot.reserved_id,
                questgiver_entry=questgiver.entry,
                questgiver_name=questgiver.name,
                target_profile=target.profile,
                kill_count=kill_count,
                reward_money_copper=reward_money,
                template_defaults=template_defaults,
            )
            payload = draft.to_dict()
            payload["_wm_reserved_slot"] = {
                "entity_type": "quest",
                "reserved_id": int(slot.reserved_id),
                "arc_key": f"wm_event:{opportunity.rule_type}",
                "character_guid": int(opportunity.player_guid),
                "notes": [
                    f"rule:{opportunity.rule_type}",
                    f"source_event:{opportunity.source_event_key}",
                ],
            }
            actions.append(
                PlannedAction(
                    kind="quest_publish",
                    payload=payload,
                    description="Publish a deterministic bounty follow-up through the canonical quest publisher.",
                )
            )
            actions.append(
                PlannedAction(
                    kind="announcement",
                    payload={"text": f"{questgiver.name} prepares a fresh bounty against {target.name}."},
                    description="Announce that a new repeat-hunt bounty has been prepared.",
                )
            )
            notes["quest_generation"] = "ready"
            notes["reserved_quest_id"] = slot.reserved_id
            return actions, notes

        actions.append(
            PlannedAction(
                kind="announcement",
                payload={"text": f"Hunting pressure around {target.name} is rising, but no free managed quest slot is available."},
                description="Announce that a repeat-hunt follow-up is blocked on quest slot capacity.",
            )
        )
        notes["quest_generation"] = "skipped_no_free_quest_slot"
        return actions, notes

    def _build_area_pressure_actions(self, opportunity: ReactionOpportunity) -> tuple[list[PlannedAction], dict[str, Any]]:
        subject_name = _subject_name(opportunity)
        zone_id = opportunity.metadata.get("zone_id")
        return (
            [
                PlannedAction(
                    kind="announcement",
                    payload={"text": f"Area pressure around {subject_name} is rising in zone {zone_id}."},
                    description="Announce that the area pressure rule has crossed its threshold.",
                )
            ],
            {"subject_name": subject_name, "zone_id": zone_id, "content_factory": "deterministic_area_pressure"},
        )

    def _build_familiar_npc_actions(self, opportunity: ReactionOpportunity) -> tuple[list[PlannedAction], dict[str, Any]]:
        subject_name = _subject_name(opportunity)
        talk_count = opportunity.metadata.get("talk_count")
        return (
            [
                PlannedAction(
                    kind="announcement",
                    payload={"text": f"{subject_name} has become familiar enough to justify a follow-up."},
                    description="Announce that an NPC relationship threshold has been reached.",
                )
            ],
            {"subject_name": subject_name, "talk_count": talk_count, "content_factory": "deterministic_familiar_npc"},
        )

    def _build_reactive_bounty_grant_actions(self, opportunity: ReactionOpportunity) -> tuple[list[PlannedAction], dict[str, Any]]:
        reactive_rule = opportunity.metadata.get("reactive_rule")
        if not isinstance(reactive_rule, dict):
            return (
                [
                    PlannedAction(
                        kind="noop",
                        payload={"reason": "Reactive bounty opportunity is missing rule metadata."},
                        description="Reactive bounty grant requires attached rule metadata.",
                    )
                ],
                {"content_factory": "reactive_bounty_grant", "grant_generation": "missing_rule_metadata"},
            )

        quest_id = reactive_rule.get("quest_id")
        if quest_id in (None, ""):
            return (
                [
                    PlannedAction(
                        kind="noop",
                        payload={"reason": "Reactive bounty opportunity is missing quest_id."},
                        description="Reactive bounty grant requires a reusable quest ID.",
                    )
                ],
                {"content_factory": "reactive_bounty_grant", "grant_generation": "missing_quest_id"},
            )

        action = PlannedAction(
            kind="quest_grant",
            payload={
                "quest": QuestRef(
                    id=int(quest_id),
                    title=_str_or_none(reactive_rule.get("quest", {}).get("title"))
                    if isinstance(reactive_rule.get("quest"), dict)
                    else None,
                ).to_dict(),
                "player": PlayerRef(
                    guid=int(opportunity.player_guid),
                    name=_str_or_none(reactive_rule.get("player_scope", {}).get("name"))
                    if isinstance(reactive_rule.get("player_scope"), dict)
                    else None,
                ).to_dict(),
                "subject": CreatureRef(
                    entry=int(opportunity.subject.subject_entry),
                    name=_subject_name(opportunity),
                ).to_dict(),
                "turn_in_npc": NpcRef(
                    entry=int(reactive_rule.get("turn_in_npc_entry") or 0),
                    name=_str_or_none(reactive_rule.get("turn_in_npc", {}).get("name"))
                    if isinstance(reactive_rule.get("turn_in_npc"), dict)
                    else None,
                ).to_dict(),
                "quest_id": int(quest_id),
                "player_guid": int(opportunity.player_guid),
                "rule_key": str(reactive_rule.get("rule_key") or opportunity.rule_type),
                "turn_in_npc_entry": int(reactive_rule.get("turn_in_npc_entry") or 0),
                "grant_mode": str(reactive_rule.get("grant_mode") or "direct_quest_add"),
                "subject_name": _subject_name(opportunity),
                "kill_threshold": int(reactive_rule.get("kill_threshold") or 0),
                "window_seconds": int(reactive_rule.get("window_seconds") or 0),
            },
            description="Grant a reusable reactive bounty directly to the player through the preferred live quest-grant transport.",
        )
        return (
            [action],
            {
                "content_factory": "reactive_bounty_grant",
                "grant_generation": "ready",
                "quest_id": int(quest_id),
            },
        )


def _subject_name(opportunity: ReactionOpportunity) -> str:
    name = opportunity.metadata.get("subject_name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return f"{opportunity.subject.subject_type}:{opportunity.subject.subject_entry}"


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
