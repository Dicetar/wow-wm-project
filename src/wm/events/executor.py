from __future__ import annotations

from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import ExecutionResult
from wm.events.models import ExecutionStepResult
from wm.events.models import ReactionPlan
from wm.events.models import WMEvent
from wm.events.store import EventStore
from wm.items.models import ItemSpellLine
from wm.items.models import ItemStatLine
from wm.items.models import ManagedItemDraft
from wm.items.publish import ItemPublisher
from wm.quests.models import BountyQuestDraft
from wm.quests.models import BountyQuestObjective
from wm.quests.models import BountyQuestReward
from wm.quests.publish import QuestPublisher
from wm.reserved.db_allocator import ReservedSlotDbAllocator
from wm.spells.models import ManagedSpellDraft
from wm.spells.models import ManagedSpellLink
from wm.spells.models import ManagedSpellProcRule
from wm.spells.publish import SpellPublisher


class ReactionExecutor:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        store: EventStore,
        slot_allocator: ReservedSlotDbAllocator | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.store = store
        self.slot_allocator = slot_allocator or ReservedSlotDbAllocator(client=client, settings=settings)
        self.quest_publisher = QuestPublisher(client=client, settings=settings)
        self.item_publisher = ItemPublisher(client=client, settings=settings)
        self.spell_publisher = SpellPublisher(client=client, settings=settings)

    def execute(self, *, plan: ReactionPlan, mode: str) -> ExecutionResult:
        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported reaction execution mode: {mode}")

        self._emit_action_event(plan=plan, event_type="reaction_planned", event_value=plan.opportunity_type)

        steps: list[ExecutionStepResult] = []
        failed = False
        cooldown_eligible = False

        for action in plan.actions:
            try:
                step = self._execute_action(plan=plan, action_kind=action.kind, payload=action.payload, mode=mode)
                steps.append(step)
                if step.status == "failed":
                    failed = True
                    break
                if mode == "apply" and action.kind != "noop" and step.status == "applied":
                    cooldown_eligible = True
            except Exception as exc:
                steps.append(
                    ExecutionStepResult(
                        kind=action.kind,
                        status="failed",
                        details={"error": str(exc)},
                    )
                )
                failed = True
                break

        if failed:
            status = "failed"
        elif mode == "dry-run":
            status = "dry-run"
        else:
            status = "applied"

        result = ExecutionResult(mode=mode, plan=plan, status=status, steps=steps)
        self.store.log_reaction(plan=plan, status=status, result=result.to_dict())
        if status == "applied" and cooldown_eligible and plan.cooldown_key is not None and plan.cooldown_seconds:
            self.store.set_cooldown(
                key=plan.cooldown_key,
                cooldown_seconds=plan.cooldown_seconds,
                metadata={"plan_key": plan.plan_key, "opportunity_type": plan.opportunity_type},
            )
        return result

    def _execute_action(self, *, plan: ReactionPlan, action_kind: str, payload: dict[str, Any], mode: str) -> ExecutionStepResult:
        if action_kind == "noop":
            return ExecutionStepResult(kind="noop", status="noop", details=payload)

        if action_kind == "announcement":
            if mode == "apply":
                self._emit_action_event(plan=plan, event_type="announcement_sent", event_value=payload.get("text"))
                return ExecutionStepResult(kind="announcement", status="applied", details=payload)
            return ExecutionStepResult(kind="announcement", status="dry-run", details=payload)

        if action_kind == "quest_publish":
            clean_payload = _strip_internal_payload_fields(payload)
            slot_payload = payload.get("_wm_reserved_slot") if isinstance(payload.get("_wm_reserved_slot"), dict) else None
            if mode == "apply":
                self._prepare_reserved_slot(plan=plan, payload=payload, source_quest_id=_int_or_none(clean_payload.get("quest_id")))
            draft = _build_quest_draft(clean_payload)
            publish_result = self.quest_publisher.publish(draft=draft, mode=mode)
            if mode == "apply" and publish_result.applied:
                self._emit_action_event(plan=plan, event_type="quest_published", event_value=str(draft.quest_id))
                return ExecutionStepResult(kind="quest_publish", status="applied", details=publish_result.to_dict())
            if mode == "dry-run":
                return ExecutionStepResult(
                    kind="quest_publish",
                    status="dry-run",
                    details=_annotate_dry_run_publish_details(
                        publish_result.to_dict(),
                        slot_payload=slot_payload,
                    ),
                )
            return ExecutionStepResult(kind="quest_publish", status="failed", details=publish_result.to_dict())

        if action_kind == "item_publish":
            clean_payload = _strip_internal_payload_fields(payload)
            slot_payload = payload.get("_wm_reserved_slot") if isinstance(payload.get("_wm_reserved_slot"), dict) else None
            if mode == "apply":
                self._prepare_reserved_slot(plan=plan, payload=payload, source_quest_id=None)
            draft = _build_item_draft(clean_payload)
            publish_result = self.item_publisher.publish(draft=draft, mode=mode)
            if mode == "apply" and publish_result.applied:
                self._emit_action_event(plan=plan, event_type="item_published", event_value=str(draft.item_entry))
                return ExecutionStepResult(kind="item_publish", status="applied", details=publish_result.to_dict())
            if mode == "dry-run":
                return ExecutionStepResult(
                    kind="item_publish",
                    status="dry-run",
                    details=_annotate_dry_run_publish_details(
                        publish_result.to_dict(),
                        slot_payload=slot_payload,
                    ),
                )
            return ExecutionStepResult(kind="item_publish", status="failed", details=publish_result.to_dict())

        if action_kind == "spell_publish":
            clean_payload = _strip_internal_payload_fields(payload)
            slot_payload = payload.get("_wm_reserved_slot") if isinstance(payload.get("_wm_reserved_slot"), dict) else None
            if mode == "apply":
                self._prepare_reserved_slot(plan=plan, payload=payload, source_quest_id=None)
            draft = _build_spell_draft(clean_payload)
            publish_result = self.spell_publisher.publish(draft=draft, mode=mode)
            if mode == "apply" and publish_result.applied:
                self._emit_action_event(plan=plan, event_type="spell_published", event_value=str(draft.spell_entry))
                return ExecutionStepResult(kind="spell_publish", status="applied", details=publish_result.to_dict())
            if mode == "dry-run":
                return ExecutionStepResult(
                    kind="spell_publish",
                    status="dry-run",
                    details=_annotate_dry_run_publish_details(
                        publish_result.to_dict(),
                        slot_payload=slot_payload,
                    ),
                )
            return ExecutionStepResult(kind="spell_publish", status="failed", details=publish_result.to_dict())

        raise ValueError(f"Unsupported action kind: {action_kind}")

    def _emit_action_event(self, *, plan: ReactionPlan, event_type: str, event_value: str | None = None) -> None:
        self.store.record(
            [
                WMEvent(
                    event_class="action",
                    event_type=event_type,
                    source="wm.executor",
                    source_event_key=f"{plan.plan_key}:{event_type}",
                    player_guid=plan.player_guid,
                    subject_type=plan.subject.subject_type,
                    subject_entry=plan.subject.subject_entry,
                    event_value=event_value,
                    metadata={"plan_key": plan.plan_key, "rule_type": plan.rule_type},
                )
            ]
        )

    def _prepare_reserved_slot(self, *, plan: ReactionPlan, payload: dict[str, Any], source_quest_id: int | None) -> None:
        slot_payload = payload.get("_wm_reserved_slot")
        if not isinstance(slot_payload, dict):
            return
        entity_type = str(slot_payload.get("entity_type") or "")
        reserved_id = _int_or_none(slot_payload.get("reserved_id"))
        if not entity_type or reserved_id is None:
            return
        self.slot_allocator.ensure_slot_prepared(
            entity_type=entity_type,
            reserved_id=reserved_id,
            arc_key=_str_or_none(slot_payload.get("arc_key")) or f"wm_event:{plan.rule_type}",
            character_guid=_int_or_none(slot_payload.get("character_guid")) or plan.player_guid,
            source_quest_id=source_quest_id,
            notes=[str(note) for note in slot_payload.get("notes", [])] if isinstance(slot_payload.get("notes"), list) else None,
        )


def _build_quest_draft(payload: dict[str, Any]) -> BountyQuestDraft:
    objective_payload = payload.get("objective") or {}
    reward_payload = payload.get("reward") or {}
    return BountyQuestDraft(
        quest_id=int(payload["quest_id"]),
        quest_level=int(payload["quest_level"]),
        min_level=int(payload["min_level"]),
        questgiver_entry=int(payload["questgiver_entry"]),
        questgiver_name=str(payload["questgiver_name"]),
        title=str(payload["title"]),
        quest_description=str(payload["quest_description"]),
        objective_text=str(payload["objective_text"]),
        offer_reward_text=str(payload["offer_reward_text"]),
        request_items_text=str(payload["request_items_text"]),
        objective=BountyQuestObjective(
            target_entry=int(objective_payload["target_entry"]),
            target_name=str(objective_payload["target_name"]),
            kill_count=int(objective_payload["kill_count"]),
        ),
        reward=BountyQuestReward(
            money_copper=int(reward_payload.get("money_copper") or 0),
            reward_item_entry=_int_or_none(reward_payload.get("reward_item_entry")),
            reward_item_name=_str_or_none(reward_payload.get("reward_item_name")),
            reward_item_count=int(reward_payload.get("reward_item_count") or 1),
        ),
        tags=[str(tag) for tag in payload.get("tags", [])],
        template_defaults=dict(payload.get("template_defaults", {})),
    )


def _build_item_draft(payload: dict[str, Any]) -> ManagedItemDraft:
    return ManagedItemDraft(
        item_entry=int(payload["item_entry"]),
        base_item_entry=int(payload["base_item_entry"]),
        name=str(payload["name"]),
        display_id=_int_or_none(payload.get("display_id")),
        description=_str_or_none(payload.get("description")),
        item_class=_int_or_none(payload.get("item_class")),
        item_subclass=_int_or_none(payload.get("item_subclass")),
        inventory_type=_int_or_none(payload.get("inventory_type")),
        quality=_int_or_none(payload.get("quality")),
        item_level=_int_or_none(payload.get("item_level")),
        required_level=_int_or_none(payload.get("required_level")),
        bonding=_int_or_none(payload.get("bonding")),
        buy_price=_int_or_none(payload.get("buy_price")),
        sell_price=_int_or_none(payload.get("sell_price")),
        max_count=_int_or_none(payload.get("max_count")),
        stackable=_int_or_none(payload.get("stackable")),
        allowable_class=_int_or_none(payload.get("allowable_class")),
        allowable_race=_int_or_none(payload.get("allowable_race")),
        clear_stats=bool(payload.get("clear_stats", False)),
        clear_spells=bool(payload.get("clear_spells", False)),
        stats=[
            ItemStatLine(
                stat_type=int(stat["stat_type"]),
                stat_value=int(stat["stat_value"]),
            )
            for stat in payload.get("stats", [])
        ],
        spells=[
            ItemSpellLine(
                spell_id=int(spell["spell_id"]),
                trigger=int(spell.get("trigger") or 0),
                charges=int(spell.get("charges") or 0),
                ppm_rate=float(spell.get("ppm_rate") or 0.0),
                cooldown_ms=int(spell.get("cooldown_ms") or -1),
                category=int(spell.get("category") or 0),
                category_cooldown_ms=int(spell.get("category_cooldown_ms") or -1),
            )
            for spell in payload.get("spells", [])
        ],
        tags=[str(tag) for tag in payload.get("tags", [])],
        template_defaults=dict(payload.get("template_defaults", {})),
    )


def _build_spell_draft(payload: dict[str, Any]) -> ManagedSpellDraft:
    return ManagedSpellDraft(
        spell_entry=int(payload["spell_entry"]),
        slot_kind=str(payload["slot_kind"]),
        name=str(payload["name"]),
        base_visible_spell_id=_int_or_none(payload.get("base_visible_spell_id")),
        helper_spell_id=_int_or_none(payload.get("helper_spell_id")),
        trigger_item_entry=_int_or_none(payload.get("trigger_item_entry")),
        aura_description=_str_or_none(payload.get("aura_description")),
        proc_rules=[
            ManagedSpellProcRule(
                spell_id=int(rule["spell_id"]),
                school_mask=int(rule.get("school_mask") or 0),
                spell_family_name=int(rule.get("spell_family_name") or 0),
                spell_family_mask_0=int(rule.get("spell_family_mask_0") or 0),
                spell_family_mask_1=int(rule.get("spell_family_mask_1") or 0),
                spell_family_mask_2=int(rule.get("spell_family_mask_2") or 0),
                proc_flags=int(rule.get("proc_flags") or 0),
                spell_type_mask=int(rule.get("spell_type_mask") or 0),
                spell_phase_mask=int(rule.get("spell_phase_mask") or 0),
                hit_mask=int(rule.get("hit_mask") or 0),
                attributes_mask=int(rule.get("attributes_mask") or 0),
                disable_effect_mask=int(rule.get("disable_effect_mask") or 0),
                procs_per_minute=float(rule.get("procs_per_minute") or 0.0),
                chance=float(rule.get("chance") or 0.0),
                cooldown=int(rule.get("cooldown") or 0),
                charges=int(rule.get("charges") or 0),
            )
            for rule in payload.get("proc_rules", [])
        ],
        linked_spells=[
            ManagedSpellLink(
                trigger_spell_id=int(link["trigger_spell_id"]),
                effect_spell_id=int(link["effect_spell_id"]),
                link_type=int(link.get("link_type") or 0),
                comment=_str_or_none(link.get("comment")),
            )
            for link in payload.get("linked_spells", [])
        ],
        tags=[str(tag) for tag in payload.get("tags", [])],
    )


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _strip_internal_payload_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not str(key).startswith("_wm_")}


def _annotate_dry_run_publish_details(
    details: dict[str, Any],
    *,
    slot_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    annotated = dict(details)
    annotated["dry_run_ready"] = bool(annotated.get("validation", {}).get("ok", False)) and bool(annotated.get("preflight", {}).get("ok", False))
    annotated["dry_run_notes"] = []
    if slot_payload is None:
        return annotated

    preflight = annotated.get("preflight")
    if not isinstance(preflight, dict):
        return annotated
    reserved_slot = preflight.get("reserved_slot")
    if not isinstance(reserved_slot, dict):
        return annotated

    current_status = str(reserved_slot.get("SlotStatus") or "")
    slot_preview = {
        "entity_type": slot_payload.get("entity_type"),
        "reserved_id": slot_payload.get("reserved_id"),
        "current_status": current_status,
        "will_stage_on_apply": current_status == "free",
        "arc_key": slot_payload.get("arc_key"),
        "character_guid": slot_payload.get("character_guid"),
    }
    annotated["slot_preparation"] = slot_preview

    issues = preflight.get("issues")
    if not isinstance(issues, list):
        return annotated
    remaining_errors = []
    absorbed_issue = False
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        path = str(issue.get("path") or "")
        message = str(issue.get("message") or "")
        severity = str(issue.get("severity") or "error")
        if (
            path == "reserved_slot.status"
            and severity == "error"
            and current_status == "free"
            and "expected `staged`" in message
        ):
            absorbed_issue = True
            continue
        remaining_errors.append(issue)

    if absorbed_issue:
        annotated["dry_run_ready"] = bool(annotated.get("validation", {}).get("ok", False)) and not any(
            str(issue.get("severity") or "error") == "error"
            for issue in remaining_errors
            if isinstance(issue, dict)
        )
        preflight_copy = dict(preflight)
        preflight_copy["issues"] = list(issues)
        preflight_copy["dry_run_effective_ok"] = annotated["dry_run_ready"]
        preflight_copy["dry_run_effective_issues"] = remaining_errors
        annotated["preflight"] = preflight_copy
        annotated["dry_run_notes"] = [
            "Reserved slot is still `free` during dry-run and would be staged automatically immediately before apply.",
        ]
    return annotated
