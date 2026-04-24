from __future__ import annotations

from pathlib import Path
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
from wm.reactive.runtime import ReactiveQuestRuntimeManager
from wm.reactive.store import ReactiveQuestStore
from wm.refs import creature_ref_from_value
from wm.refs import item_ref_from_value
from wm.refs import npc_ref_from_value
from wm.refs import player_ref_from_value
from wm.refs import quest_ref_from_value
from wm.reserved.db_allocator import ReservedSlotDbAllocator
from wm.runtime_sync import SoapRuntimeClient
from wm.spells.models import ManagedSpellDraft
from wm.spells.models import ManagedSpellLink
from wm.spells.models import ManagedSpellProcRule
from wm.spells.publish import SpellPublisher
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.actions import NativeBridgeActionClient
from wm.sources.native_bridge.configure import load_bridge_runtime_config


class ReactionExecutor:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        store: EventStore,
        slot_allocator: ReservedSlotDbAllocator | None = None,
        reactive_store: ReactiveQuestStore | None = None,
        reactive_runtime: ReactiveQuestRuntimeManager | None = None,
        native_bridge_actions: NativeBridgeActionClient | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.store = store
        self.slot_allocator = slot_allocator or ReservedSlotDbAllocator(client=client, settings=settings)
        self.reactive_store = reactive_store or ReactiveQuestStore(client=client, settings=settings)
        self.reactive_runtime = reactive_runtime or ReactiveQuestRuntimeManager(
            settings=settings,
            soap_client=SoapRuntimeClient(settings=settings),
        )
        self.quest_publisher = QuestPublisher(client=client, settings=settings)
        self.item_publisher = ItemPublisher(client=client, settings=settings)
        self.spell_publisher = SpellPublisher(client=client, settings=settings)
        self.native_bridge_actions = native_bridge_actions or NativeBridgeActionClient(client=client, settings=settings)

    def execute(self, *, plan: ReactionPlan, mode: str) -> ExecutionResult:
        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported reaction execution mode: {mode}")
        return self._run_plan(plan=plan, publish_mode=mode, result_mode=mode, record_audit=True)

    def preview(self, *, plan: ReactionPlan) -> ExecutionResult:
        return self._run_plan(plan=plan, publish_mode="dry-run", result_mode="preview", record_audit=False)

    def _run_plan(
        self,
        *,
        plan: ReactionPlan,
        publish_mode: str,
        result_mode: str,
        record_audit: bool,
    ) -> ExecutionResult:
        if publish_mode not in {"dry-run", "apply"}:
            raise ValueError(f"Unsupported reaction execution mode: {publish_mode}")
        if record_audit:
            self._emit_action_event(plan=plan, event_type="reaction_planned", event_value=plan.opportunity_type)
        steps: list[ExecutionStepResult] = []
        failed = False
        cooldown_eligible = False

        for action in plan.actions:
            try:
                step = self._execute_action(plan=plan, action_kind=action.kind, payload=action.payload, mode=publish_mode)
                steps.append(step)
                if step.status == "failed":
                    failed = True
                    break
                if publish_mode == "apply" and action.kind != "noop" and step.status == "applied":
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
        elif result_mode == "preview":
            status = "preview"
        elif publish_mode == "dry-run":
            status = "dry-run"
        else:
            status = "applied"

        result = ExecutionResult(mode=result_mode, plan=plan, status=status, steps=steps)
        if record_audit:
            self.store.log_reaction(plan=plan, status=status, result=result.to_dict())
        if (
            record_audit
            and status == "applied"
            and cooldown_eligible
            and plan.cooldown_key is not None
            and plan.cooldown_seconds
        ):
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

        if action_kind == "native_bridge_action":
            native_action_kind = str(payload.get("native_action_kind") or "")
            if native_action_kind not in NATIVE_ACTION_KIND_BY_ID:
                raise ValueError(f"Unsupported native bridge action kind: {native_action_kind}")
            native_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
            details = {
                "native_action_kind": native_action_kind,
                "payload": native_payload,
                "implemented": bool(NATIVE_ACTION_KIND_BY_ID[native_action_kind].implemented),
                "priority": int(payload.get("priority") or 5),
                "sequence_id": payload.get("sequence_id"),
                "sequence_order": int(payload.get("sequence_order") or 0),
                "wait_for_prior": bool(payload.get("wait_for_prior", False)),
                "dry_run_ready": True,
                "dry_run_notes": [
                    "Dry-run validates the native action contract only; the C++ bridge executes queued rows after apply."
                ],
            }
            if mode == "apply":
                request = self.native_bridge_actions.submit(
                    idempotency_key=f"{plan.plan_key}:native:{native_action_kind}",
                    player_guid=int(payload.get("player_guid") or plan.player_guid),
                    action_kind=native_action_kind,
                    payload=native_payload,
                    created_by=str(payload.get("created_by") or "wm.control"),
                    risk_level=str(payload.get("risk_level") or NATIVE_ACTION_KIND_BY_ID[native_action_kind].default_risk),
                    expires_seconds=int(payload.get("expires_seconds") or 60),
                    max_attempts=int(payload.get("max_attempts") or 3),
                    sequence_id=str(payload["sequence_id"]) if payload.get("sequence_id") not in (None, "") else None,
                    sequence_order=int(payload.get("sequence_order") or 0),
                    wait_for_prior=bool(payload.get("wait_for_prior", False)),
                    priority=int(payload.get("priority") or 5),
                    purge_after_seconds=(
                        int(payload["purge_after_seconds"]) if payload.get("purge_after_seconds") not in (None, "") else None
                    ),
                    target_map_id=_int_or_none(payload.get("target_map_id")),
                    target_x=_float_or_none(payload.get("target_x")),
                    target_y=_float_or_none(payload.get("target_y")),
                    target_z=_float_or_none(payload.get("target_z")),
                    target_o=_float_or_none(payload.get("target_o")),
                    target_player_guid=_int_or_none(payload.get("target_player_guid")),
                )
                final_request = self.native_bridge_actions.wait(request_id=request.request_id)
                details["request"] = final_request.to_dict()
                if final_request.status == "done":
                    self._emit_action_event(plan=plan, event_type="native_bridge_action_done", event_value=native_action_kind)
                    return ExecutionStepResult(kind="native_bridge_action", status="applied", details=details)
                return ExecutionStepResult(kind="native_bridge_action", status="failed", details=details)
            return ExecutionStepResult(kind="native_bridge_action", status="dry-run", details=details)

        if action_kind == "quest_grant":
            quest_ref = quest_ref_from_value(payload.get("quest"))
            player_ref = player_ref_from_value(payload.get("player"))
            turn_in_npc = npc_ref_from_value(payload.get("turn_in_npc"))
            quest_id = int(quest_ref.id if quest_ref is not None else payload["quest_id"])
            player_guid = int(player_ref.guid if player_ref is not None else (payload.get("player_guid") or plan.player_guid))
            player_name = self.reactive_store.fetch_character_name(player_guid=player_guid)
            soap_preview = self.reactive_runtime.preview_grant(
                player_guid=player_guid,
                player_name=player_name,
                quest_id=quest_id,
            )
            soap_preview_dict = soap_preview.to_dict()
            native_preview = self._preview_native_quest_grant(player_guid=player_guid, quest_id=quest_id)
            transport_mode = _normalize_quest_grant_transport(self.settings.quest_grant_transport)
            selected_transport = self._select_quest_grant_transport(
                transport_mode=transport_mode,
                native_preview=native_preview,
                soap_preview_ok=bool(soap_preview_dict.get("ok", False)),
            )
            details = {
                "quest_id": quest_id,
                "player_guid": player_guid,
                "player_name": player_name,
                "transport_mode": transport_mode,
                "selected_transport": selected_transport,
                "native_preview": native_preview,
                "soap_preview": soap_preview_dict,
                "dry_run_ready": bool(
                    native_preview.get("ok")
                    if selected_transport == "native_bridge"
                    else soap_preview_dict.get("ok", False)
                    if selected_transport == "soap"
                    else False
                ),
                "dry_run_notes": list(
                    native_preview.get("notes", [])
                    if selected_transport == "native_bridge"
                    else soap_preview_dict.get("notes", [])
                    if selected_transport == "soap"
                    else [
                        "No quest grant transport is currently ready. Enable native bridge scope/policy or configure SOAP fallback."
                    ]
                ),
                "command_preview": soap_preview_dict.get("command_preview") if selected_transport == "soap" else None,
            }
            details["rule_key"] = payload.get("rule_key")
            details["turn_in_npc_entry"] = int(
                turn_in_npc.entry if turn_in_npc is not None else (payload.get("turn_in_npc_entry") or 0)
            )
            details["quest"] = quest_ref.to_dict() if quest_ref is not None else {"id": quest_id}
            details["player"] = player_ref.to_dict() if player_ref is not None else {"guid": player_guid, "name": player_name}
            if turn_in_npc is not None:
                details["turn_in_npc"] = turn_in_npc.to_dict()
            if mode == "apply":
                if selected_transport == "native_bridge":
                    request = self.native_bridge_actions.submit(
                        idempotency_key=_native_quest_grant_idempotency_key(plan=plan, quest_id=quest_id),
                        player_guid=player_guid,
                        action_kind="quest_add",
                        payload={"quest_id": quest_id},
                        created_by="wm.quest_grant",
                        risk_level="medium",
                        expires_seconds=60,
                    )
                    final_request = self.native_bridge_actions.wait(request_id=request.request_id)
                    details["native_request"] = final_request.to_dict()
                    if final_request.status == "done":
                        self._emit_action_event(plan=plan, event_type="quest_grant_issued", event_value=str(quest_id))
                        return ExecutionStepResult(kind="quest_grant", status="applied", details=details)
                    return ExecutionStepResult(kind="quest_grant", status="failed", details=details)
                if selected_transport == "soap":
                    result = self.reactive_runtime.grant_quest(
                        player_guid=player_guid,
                        player_name=player_name,
                        quest_id=quest_id,
                    )
                    details["runtime_result"] = result.to_dict()
                    if result.ok:
                        self._emit_action_event(plan=plan, event_type="quest_grant_issued", event_value=str(quest_id))
                        return ExecutionStepResult(kind="quest_grant", status="applied", details=details)
                    return ExecutionStepResult(kind="quest_grant", status="failed", details=details)
                return ExecutionStepResult(kind="quest_grant", status="failed", details=details)
            return ExecutionStepResult(kind="quest_grant", status="dry-run", details=details)

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

    def _select_quest_grant_transport(
        self,
        *,
        transport_mode: str,
        native_preview: dict[str, Any],
        soap_preview_ok: bool,
    ) -> str | None:
        if transport_mode == "native":
            return "native_bridge"
        if transport_mode == "soap":
            return "soap"
        if bool(native_preview.get("ok")):
            return "native_bridge"
        if soap_preview_ok:
            return "soap"
        return None

    def _preview_native_quest_grant(self, *, player_guid: int, quest_id: int) -> dict[str, Any]:
        issues: list[dict[str, str]] = []
        notes: list[str] = [
            "Native quest grant uses wm_bridge_action_request with action kind quest_add.",
            "Native quest_add requires the player to be online when the action request is processed.",
        ]
        config_snapshot = None
        config_payload: dict[str, Any] | None = None
        try:
            config_snapshot = load_bridge_runtime_config(Path(self.settings.wm_bridge_config_path))
            config_payload = {
                "enabled": config_snapshot.enabled,
                "action_queue_enabled": config_snapshot.action_queue_enabled,
                "db_control_enabled": config_snapshot.db_control_enabled,
                "allow_all_players": config_snapshot.allow_all_players,
                "player_guid_allowlist": list(config_snapshot.player_guid_allowlist),
            }
            if not config_snapshot.enabled:
                issues.append(
                    {
                        "path": "wm_bridge_config.enabled",
                        "message": "mod-wm-bridge is disabled in the bridge config.",
                        "severity": "error",
                    }
                )
            if not config_snapshot.action_queue_enabled:
                issues.append(
                    {
                        "path": "wm_bridge_config.action_queue_enabled",
                        "message": "WmBridge.ActionQueue.Enable is off, so native quest_add cannot execute.",
                        "severity": "error",
                    }
                )
        except Exception as exc:
            issues.append(
                {
                    "path": "wm_bridge_config_path",
                    "message": f"Could not read native bridge config: {exc}",
                    "severity": "error",
                }
            )

        if not NATIVE_ACTION_KIND_BY_ID["quest_add"].implemented:
            issues.append(
                {
                    "path": "native_action_kind.quest_add",
                    "message": "quest_add is not implemented in the native bridge action bus yet.",
                    "severity": "error",
                }
            )

        player_allowed = False
        if config_snapshot is not None:
            player_allowed = config_snapshot.allow_all_players or int(player_guid) in set(config_snapshot.player_guid_allowlist)
            if config_snapshot.db_control_enabled:
                try:
                    player_allowed = player_allowed or self.native_bridge_actions.is_player_scoped(player_guid=player_guid)
                except Exception as exc:
                    issues.append(
                        {
                            "path": "wm_bridge_player_scope",
                            "message": f"Could not read wm_bridge_player_scope: {exc}",
                            "severity": "error",
                        }
                    )
            if not player_allowed:
                issues.append(
                    {
                        "path": "player_guid",
                        "message": f"Player GUID {player_guid} is not currently allowed by mod-wm-bridge scope.",
                        "severity": "error",
                    }
                )

        policy_payload: dict[str, Any] | None = None
        try:
            policy = self.native_bridge_actions.get_action_policy(action_kind="quest_add")
            if policy is None:
                issues.append(
                    {
                        "path": "wm_bridge_action_policy.quest_add",
                        "message": "No wm_bridge_action_policy row exists for quest_add.",
                        "severity": "error",
                    }
                )
            else:
                policy_payload = policy
                if not bool(policy.get("enabled")):
                    issues.append(
                        {
                            "path": "wm_bridge_action_policy.quest_add.enabled",
                            "message": "quest_add is disabled in wm_bridge_action_policy.",
                            "severity": "error",
                        }
                    )
                if _risk_rank("medium") > _risk_rank(str(policy.get("max_risk_level") or "low")):
                    issues.append(
                        {
                            "path": "wm_bridge_action_policy.quest_add.max_risk_level",
                            "message": "quest_add policy max risk is lower than the required medium risk.",
                            "severity": "error",
                        }
                    )
        except Exception as exc:
            issues.append(
                {
                    "path": "wm_bridge_action_policy.quest_add",
                    "message": f"Could not read wm_bridge_action_policy for quest_add: {exc}",
                    "severity": "error",
                }
            )

        ok = not any(issue["severity"] == "error" for issue in issues)
        return {
            "ok": ok,
            "player_guid": int(player_guid),
            "quest_id": int(quest_id),
            "action_kind": "quest_add",
            "bridge_config": config_payload,
            "player_allowed": player_allowed,
            "policy": policy_payload,
            "issues": issues,
            "notes": notes,
        }


def _build_quest_draft(payload: dict[str, Any]) -> BountyQuestDraft:
    objective_payload = payload.get("objective") or {}
    reward_payload = payload.get("reward") or {}
    quest_ref = quest_ref_from_value(payload.get("quest"))
    questgiver_ref = npc_ref_from_value(payload.get("questgiver"))
    starter_ref = npc_ref_from_value(payload.get("starter_npc"))
    ender_ref = npc_ref_from_value(payload.get("ender_npc"))
    target_ref = creature_ref_from_value(objective_payload.get("target") if isinstance(objective_payload, dict) else None)
    reward_item_ref = item_ref_from_value(
        reward_payload.get("reward_item") if isinstance(reward_payload, dict) else None
    )
    quest_id = int(quest_ref.id if quest_ref is not None else payload["quest_id"])
    quest_title = str(quest_ref.title) if quest_ref is not None and quest_ref.title not in (None, "") else str(payload["title"])
    questgiver_entry = int(questgiver_ref.entry if questgiver_ref is not None else payload["questgiver_entry"])
    questgiver_name = (
        str(questgiver_ref.name)
        if questgiver_ref is not None and questgiver_ref.name not in (None, "")
        else str(payload["questgiver_name"])
    )
    target_entry = int(target_ref.entry if target_ref is not None else objective_payload["target_entry"])
    target_name = (
        str(target_ref.name)
        if target_ref is not None and target_ref.name not in (None, "")
        else str(objective_payload["target_name"])
    )
    reward_item_entry = (
        int(reward_item_ref.entry)
        if reward_item_ref is not None
        else _int_or_none(reward_payload.get("reward_item_entry"))
    )
    reward_item_name = (
        str(reward_item_ref.name)
        if reward_item_ref is not None and reward_item_ref.name not in (None, "")
        else _str_or_none(reward_payload.get("reward_item_name"))
    )
    return BountyQuestDraft(
        quest_id=quest_id,
        quest_level=int(payload["quest_level"]),
        min_level=int(payload["min_level"]),
        questgiver_entry=questgiver_entry,
        questgiver_name=questgiver_name,
        start_npc_entry=int(starter_ref.entry) if starter_ref is not None else _int_or_none(payload.get("start_npc_entry")),
        end_npc_entry=int(ender_ref.entry) if ender_ref is not None else _int_or_none(payload.get("end_npc_entry")),
        grant_mode=str(payload.get("grant_mode") or "npc_start"),
        title=quest_title,
        quest_description=str(payload["quest_description"]),
        objective_text=str(payload["objective_text"]),
        offer_reward_text=str(payload["offer_reward_text"]),
        request_items_text=str(payload["request_items_text"]),
        objective=BountyQuestObjective(
            target_entry=target_entry,
            target_name=target_name,
            kill_count=int(objective_payload["kill_count"]),
            target=target_ref,
        ),
        reward=BountyQuestReward(
            money_copper=int(reward_payload.get("money_copper") or 0),
            reward_item_entry=reward_item_entry,
            reward_item_name=reward_item_name,
            reward_item_count=int(reward_payload.get("reward_item_count") or 1),
            reward_xp_difficulty=_int_or_none(reward_payload.get("reward_xp_difficulty")),
            reward_spell_id=_int_or_none(reward_payload.get("reward_spell_id")),
            reward_spell_display_id=_int_or_none(reward_payload.get("reward_spell_display_id")),
            reward_reputations=[
                {
                    "faction_id": int(reward["faction_id"]),
                    "value": int(reward["value"]),
                }
                for reward in reward_payload.get("reward_reputations", [])
            ],
            reward_item=reward_item_ref,
        ),
        tags=[str(tag) for tag in payload.get("tags", [])],
        template_defaults=dict(payload.get("template_defaults", {})),
        quest=quest_ref,
        questgiver=questgiver_ref,
        starter_npc=starter_ref,
        ender_npc=ender_ref,
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


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _normalize_quest_grant_transport(value: Any) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized in {"native", "native_bridge"}:
        return "native"
    if normalized == "soap":
        return "soap"
    return "auto"


def _risk_rank(value: str) -> int:
    normalized = str(value or "").strip().lower()
    if normalized == "low":
        return 0
    if normalized == "medium":
        return 1
    if normalized == "high":
        return 2
    return 99


def _native_quest_grant_idempotency_key(*, plan: ReactionPlan, quest_id: int) -> str:
    source_event_key = _str_or_none(plan.metadata.get("source_event_key"))
    opportunity_metadata = plan.metadata.get("opportunity_metadata")
    if source_event_key is None and isinstance(opportunity_metadata, dict):
        source_event_key = _str_or_none(opportunity_metadata.get("source_event_key"))
        if source_event_key is None:
            trigger_event_id = _int_or_none(opportunity_metadata.get("trigger_event_id"))
            if trigger_event_id is not None:
                source_event_key = f"trigger_event:{trigger_event_id}"
    trigger_scope = source_event_key or "no_source_event"
    return f"{plan.plan_key}:{trigger_scope}:native:quest_add:{int(quest_id)}"


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
