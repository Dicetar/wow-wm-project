from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import sys
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.items.publish import ItemPublisher, load_managed_item_draft
from wm.items.rollback import ItemRollback
from wm.reactive.install_bounty import ReactiveBountyInstaller
from wm.reactive.install_bounty import _reward_reputations_from_value
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.store import ReactiveQuestStore
from wm.reactive.templates import resolve_reactive_bounty_template_path
from wm.refs import CreatureRef
from wm.refs import NpcRef
from wm.refs import PlayerRef
from wm.refs import QuestRef
from wm.reserved.db_allocator import ReservedSlotDbAllocator
from wm.runtime_sync import RuntimeSyncResult
from wm.runtime_sync import sync_runtime_after_publish
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.actions import NativeBridgeActionClient


SCENARIO_VERSION = "wm.content_playcycle.item_effect.v1"

_TOP_LEVEL_KEYS = {
    "schema_version",
    "cycle_key",
    "player_guid",
    "item_draft_path",
    "item_entry",
    "effect_label",
    "runtime_sync",
    "direct_grant",
    "promotion_bounty_template",
    "verify_expectations",
    "notes",
}

_RUNTIME_SYNC_KEYS = {"mode", "item_commands", "rollback_commands", "notes"}
_DIRECT_GRANT_KEYS = {
    "enabled",
    "count",
    "soulbound",
    "wait",
    "risk_level",
    "max_attempts",
    "expires_seconds",
    "purge_after_seconds",
    "cleanup_on_rollback",
    "remove_count",
}
_PROMOTION_KEYS = {
    "template_path",
    "template_key",
    "rule_key",
    "player_guid",
    "subject_entry",
    "turn_in_npc_entry",
    "kill_threshold",
    "window_seconds",
    "post_reward_cooldown_seconds",
    "objective_target_name",
    "quest_title",
    "subject_name_prefix",
    "reward_item_entry",
    "reward_item_name",
    "reward_item_count",
    "reward_xp_difficulty",
    "reward_spell_id",
    "reward_spell_display_id",
    "reward_reputations",
}
_VERIFY_KEYS = {
    "inventory_receipt",
    "require_inventory_receipt",
    "require_publish_log",
    "require_rollback_snapshot",
    "require_reserved_slot",
    "visible_wearer_aura",
    "visible_target_debuff",
}
_FORBIDDEN_KEY_PARTS = ("freeform", "sql", "gm", "llm", "shell_command", "mutation")


@dataclass(slots=True)
class PlaycycleIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ItemEffectScenario:
    schema_version: str
    cycle_key: str
    player_guid: int
    item_draft_path: Path
    item_entry: int
    effect_label: str
    runtime_sync: dict[str, Any] = field(default_factory=dict)
    direct_grant: dict[str, Any] = field(default_factory=dict)
    promotion_bounty_template: dict[str, Any] = field(default_factory=dict)
    verify_expectations: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "cycle_key": self.cycle_key,
            "player_guid": self.player_guid,
            "item_draft_path": str(self.item_draft_path),
            "item_entry": self.item_entry,
            "effect_label": self.effect_label,
            "runtime_sync": self.runtime_sync,
            "direct_grant": self.direct_grant,
            "promotion_bounty_template": self.promotion_bounty_template,
            "verify_expectations": self.verify_expectations,
            "notes": self.notes,
        }


@dataclass(slots=True)
class ItemEffectPlaycycleResult:
    mode: str
    cycle_key: str
    player_guid: int
    item_entry: int
    effect_label: str
    outcome: str
    ok: bool
    applied: bool = False
    restart_recommended: bool = False
    scenario: dict[str, Any] = field(default_factory=dict)
    publish: dict[str, Any] | None = None
    runtime_sync: dict[str, Any] | None = None
    direct_grant: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    promotion: dict[str, Any] | None = None
    rollback: dict[str, Any] | None = None
    cleanup: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)
    issues: list[PlaycycleIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "cycle_key": self.cycle_key,
            "player_guid": self.player_guid,
            "item_entry": self.item_entry,
            "effect_label": self.effect_label,
            "outcome": self.outcome,
            "ok": self.ok,
            "applied": self.applied,
            "restart_recommended": self.restart_recommended,
            "scenario": self.scenario,
            "publish": self.publish,
            "runtime_sync": self.runtime_sync,
            "direct_grant": self.direct_grant,
            "verification": self.verification,
            "promotion": self.promotion,
            "rollback": self.rollback,
            "cleanup": self.cleanup,
            "notes": self.notes,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class ItemEffectPlaycycle:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        item_publisher: Any | None = None,
        native_bridge: Any | None = None,
        item_rollback: Any | None = None,
        slot_allocator: Any | None = None,
        reactive_store: Any | None = None,
        resolver: Any | None = None,
        bounty_installer: Any | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.item_publisher = item_publisher or ItemPublisher(client=client, settings=settings)
        self.native_bridge = native_bridge or NativeBridgeActionClient(client=client, settings=settings)
        self.item_rollback = item_rollback or ItemRollback(client=client, settings=settings)
        self.slot_allocator = slot_allocator or ReservedSlotDbAllocator(client=client, settings=settings)
        self.reactive_store = reactive_store or ReactiveQuestStore(client=client, settings=settings)
        if resolver is None:
            from wm.quests.generate_bounty import LiveCreatureResolver

            resolver = LiveCreatureResolver(client=client, settings=settings)
        self.resolver = resolver
        self.bounty_installer = bounty_installer or ReactiveBountyInstaller(
            client=client,
            settings=settings,
            reactive_store=self.reactive_store,
            slot_allocator=self.slot_allocator,
            resolver=self.resolver,
        )

    def run(
        self,
        *,
        scenario: ItemEffectScenario,
        mode: str,
        runtime_sync_mode: str = "scenario",
        cleanup_player_item: bool = False,
        admin_override_remove_item: bool = False,
    ) -> ItemEffectPlaycycleResult:
        if mode == "dry-run":
            return self.dry_run(scenario=scenario, runtime_sync_mode=runtime_sync_mode)
        if mode == "apply":
            return self.apply(scenario=scenario, runtime_sync_mode=runtime_sync_mode)
        if mode == "verify":
            return self.verify(scenario=scenario)
        if mode == "promote-quest":
            return self.promote_quest(scenario=scenario)
        if mode == "rollback":
            return self.rollback(
                scenario=scenario,
                runtime_sync_mode=runtime_sync_mode,
                cleanup_player_item=cleanup_player_item,
                admin_override_remove_item=admin_override_remove_item,
            )
        raise ValueError(f"Unsupported playcycle mode: {mode}")

    def dry_run(self, *, scenario: ItemEffectScenario, runtime_sync_mode: str) -> ItemEffectPlaycycleResult:
        issues: list[PlaycycleIssue] = []
        draft = load_managed_item_draft(scenario.item_draft_path)
        issues.extend(_draft_consistency_issues(scenario=scenario, draft=draft))
        publish_result = self.item_publisher.publish(draft=draft, mode="dry-run")
        publish = publish_result.to_dict()
        issues.extend(_issues_from_publish(publish))
        direct_grant = self._direct_grant_preflight(scenario=scenario)
        issues.extend(direct_grant.get("issues", []))
        runtime_sync = self._item_runtime_sync(
            scenario=scenario,
            mode="dry-run",
            runtime_sync_mode=runtime_sync_mode,
        ).to_dict()
        notes = [
            "Dry-run validates DB, slot, snapshot, native scope/policy, and runtime-sync intent without mutating live state.",
            "Visible item effect behavior remains UNKNOWN until the item is equipped/used in-game and the configured aura/debuff is observed.",
            *_bridge_lab_notes(settings=self.settings, player_guid=scenario.player_guid),
            *scenario.notes,
        ]
        ok = _publish_preflight_ok(publish) and not _has_error(issues)
        return ItemEffectPlaycycleResult(
            mode="dry-run",
            cycle_key=scenario.cycle_key,
            player_guid=scenario.player_guid,
            item_entry=scenario.item_entry,
            effect_label=scenario.effect_label,
            outcome="WORKING" if ok else "BROKEN",
            ok=ok,
            applied=False,
            restart_recommended=bool(runtime_sync.get("restart_recommended", False)),
            scenario=scenario.to_dict(),
            publish=publish,
            runtime_sync=runtime_sync,
            direct_grant=_serializable_action_block(direct_grant),
            notes=notes,
            issues=issues,
        )

    def apply(self, *, scenario: ItemEffectScenario, runtime_sync_mode: str) -> ItemEffectPlaycycleResult:
        issues: list[PlaycycleIssue] = []
        draft = load_managed_item_draft(scenario.item_draft_path)
        issues.extend(_draft_consistency_issues(scenario=scenario, draft=draft))
        if _has_error(issues):
            return _base_result(scenario=scenario, mode="apply", outcome="BROKEN", issues=issues)
        publish_result = self.item_publisher.publish(draft=draft, mode="apply")
        publish = publish_result.to_dict()
        issues.extend(_issues_from_publish(publish))
        publish_ok = bool(publish.get("applied", False)) and _publish_preflight_ok(publish)
        if publish_ok:
            runtime_sync = self._item_runtime_sync(
                scenario=scenario,
                mode="apply",
                runtime_sync_mode=runtime_sync_mode,
            ).to_dict()
            direct_grant = self._submit_direct_grant(scenario=scenario) if _direct_grant_enabled(scenario) else {
                "enabled": False,
                "status": "skipped",
                "ok": True,
                "message": "direct_grant.enabled is false.",
            }
            issues.extend(direct_grant.get("issues", []))
        else:
            runtime_sync = RuntimeSyncResult(
                protocol="none",
                enabled=False,
                overall_ok=True,
                restart_recommended=False,
                note="Item publish did not apply; runtime sync and direct grant were skipped.",
            ).to_dict()
            direct_grant = {
                "enabled": _direct_grant_enabled(scenario),
                "status": "skipped",
                "ok": not _direct_grant_enabled(scenario),
                "message": "Item publish did not apply; direct grant was skipped.",
            }
        runtime_ok = bool(runtime_sync.get("overall_ok", False))
        grant_ok = (not _direct_grant_enabled(scenario)) or direct_grant.get("ok") is True
        ok = publish_ok and runtime_ok and grant_ok and not _has_error(issues)
        outcome = "PARTIAL" if ok else ("PARTIAL" if publish_ok else "BROKEN")
        notes = [
            "Apply publishes the managed item and grants it through the typed native action bus when policy/scope are ready.",
            "Effect behavior is PARTIAL until an operator confirms the visible wearer aura and target debuff in-game.",
            *scenario.notes,
        ]
        return ItemEffectPlaycycleResult(
            mode="apply",
            cycle_key=scenario.cycle_key,
            player_guid=scenario.player_guid,
            item_entry=scenario.item_entry,
            effect_label=scenario.effect_label,
            outcome=outcome,
            ok=ok,
            applied=bool(publish.get("applied", False)),
            restart_recommended=bool(runtime_sync.get("restart_recommended", False)),
            scenario=scenario.to_dict(),
            publish=publish,
            runtime_sync=runtime_sync,
            direct_grant=_serializable_action_block(direct_grant),
            notes=notes,
            issues=issues,
        )

    def verify(self, *, scenario: ItemEffectScenario) -> ItemEffectPlaycycleResult:
        verification = self._verify_state(scenario=scenario)
        issues = list(verification.pop("issues", []))
        ok = not _has_error(issues)
        notes = [
            "Verify checks DB/publish/snapshot/slot evidence and best-effort player inventory evidence.",
            "In-game visible aura/debuff proof is still operator-observed unless recorded separately.",
        ]
        return ItemEffectPlaycycleResult(
            mode="verify",
            cycle_key=scenario.cycle_key,
            player_guid=scenario.player_guid,
            item_entry=scenario.item_entry,
            effect_label=scenario.effect_label,
            outcome="WORKING" if ok else "PARTIAL",
            ok=ok,
            applied=False,
            restart_recommended=False,
            scenario=scenario.to_dict(),
            verification=verification,
            notes=notes,
            issues=issues,
        )

    def promote_quest(self, *, scenario: ItemEffectScenario) -> ItemEffectPlaycycleResult:
        issues: list[PlaycycleIssue] = []
        promotion_config = dict(scenario.promotion_bounty_template or {})
        if not promotion_config:
            issues.append(
                PlaycycleIssue(
                    path="promotion_bounty_template",
                    message="promote-quest requires promotion_bounty_template in the scenario.",
                )
            )
            return _base_result(scenario=scenario, mode="promote-quest", outcome="BROKEN", issues=issues)

        template = self._load_promotion_template(config=promotion_config)
        merged = {**template, **promotion_config}
        if "quest_id" in merged:
            issues.append(
                PlaycycleIssue(
                    path="promotion_bounty_template.quest_id",
                    message="Visible reward iteration must allocate a fresh reserved quest slot; explicit quest_id is not accepted.",
                )
            )
        required = ["subject_entry", "turn_in_npc_entry"]
        for key in required:
            if merged.get(key) in (None, ""):
                issues.append(PlaycycleIssue(path=f"promotion_bounty_template.{key}", message=f"{key} is required."))
        item_exists = self._world_rows(
            "SELECT entry, name FROM item_template "
            f"WHERE entry = {int(scenario.item_entry)} LIMIT 1",
            issue_path="promotion.item_template",
            issues=issues,
        )
        if not item_exists:
            issues.append(
                PlaycycleIssue(
                    path="promotion.item_template",
                    message=f"Item {scenario.item_entry} is not present in item_template; publish/apply it before quest promotion.",
                )
            )
        if _has_error(issues):
            return _base_result(scenario=scenario, mode="promote-quest", outcome="BROKEN", issues=issues)

        rule_key = str(merged.get("rule_key") or f"content_playcycle:{scenario.cycle_key}:bounty_reward")
        player_guid = int(merged.get("player_guid") or scenario.player_guid)
        slot = self.slot_allocator.allocate_next_free_slot(
            entity_type="quest",
            arc_key=rule_key,
            character_guid=player_guid,
            source_quest_id=None,
            notes=[
                f"content_playcycle:{scenario.cycle_key}",
                "slot_strategy:fresh_reserved_slot",
                f"reward_item_entry:{scenario.item_entry}",
            ],
        )
        if slot is None:
            issues.append(PlaycycleIssue(path="reserved_slot.quest", message="No free reserved quest slot is available."))
            return _base_result(scenario=scenario, mode="promote-quest", outcome="BROKEN", issues=issues)

        allocated_quest_id = int(slot.reserved_id)
        try:
            rule = self._build_promotion_rule(
                config=merged,
                scenario=scenario,
                player_guid=player_guid,
                rule_key=rule_key,
                quest_id=allocated_quest_id,
            )
            install_result = self.bounty_installer.install(rule=rule, mode="apply")
        except Exception as exc:
            try:
                self.slot_allocator.release_slot(entity_type="quest", reserved_id=allocated_quest_id)
            except Exception:
                pass
            issues.append(PlaycycleIssue(path="promotion", message=str(exc)))
            return _base_result(scenario=scenario, mode="promote-quest", outcome="BROKEN", issues=issues)

        promotion = install_result.to_dict()
        promotion["allocated_quest_id"] = allocated_quest_id
        publish = promotion.get("quest_publish") or {}
        publish_ok = bool(publish.get("applied", False)) and bool((publish.get("preflight") or {}).get("ok", True))
        ok = publish_ok and not _has_error(issues)
        return ItemEffectPlaycycleResult(
            mode="promote-quest",
            cycle_key=scenario.cycle_key,
            player_guid=scenario.player_guid,
            item_entry=scenario.item_entry,
            effect_label=scenario.effect_label,
            outcome="WORKING" if ok else "PARTIAL",
            ok=ok,
            applied=publish_ok,
            restart_recommended=True,
            scenario=scenario.to_dict(),
            promotion=promotion,
            notes=[
                f"Allocated fresh reserved quest slot {allocated_quest_id}; no accepted/rewarded quest ID was reused.",
                "Reward visibility still needs the client-side quest reward panel checked in-game before claiming player-facing proof.",
            ],
            issues=issues,
        )

    def rollback(
        self,
        *,
        scenario: ItemEffectScenario,
        runtime_sync_mode: str,
        cleanup_player_item: bool,
        admin_override_remove_item: bool,
    ) -> ItemEffectPlaycycleResult:
        issues: list[PlaycycleIssue] = []
        runtime_mode = _effective_runtime_sync_mode(scenario=scenario, runtime_sync_mode=runtime_sync_mode)
        rollback_result = self.item_rollback.rollback(
            item_entry=scenario.item_entry,
            mode="apply",
            runtime_sync_mode=runtime_mode,
            soap_commands=_runtime_sync_commands(scenario, key="rollback_commands"),
        )
        rollback = rollback_result.to_dict()
        for issue in rollback.get("issues", []):
            if isinstance(issue, dict):
                issues.append(
                    PlaycycleIssue(
                        path=f"rollback.{issue.get('path')}",
                        message=str(issue.get("message") or ""),
                        severity=str(issue.get("severity") or "error"),
                    )
                )
        cleanup = self._cleanup_player_item(
            scenario=scenario,
            enabled=cleanup_player_item,
            admin_override=admin_override_remove_item,
        )
        issues.extend(cleanup.get("issues", []))
        ok = bool(rollback.get("ok", False)) and not _has_error(issues)
        outcome = "WORKING" if ok and cleanup.get("status") == "done" else ("PARTIAL" if rollback.get("ok", False) else "BROKEN")
        return ItemEffectPlaycycleResult(
            mode="rollback",
            cycle_key=scenario.cycle_key,
            player_guid=scenario.player_guid,
            item_entry=scenario.item_entry,
            effect_label=scenario.effect_label,
            outcome=outcome,
            ok=ok,
            applied=bool(rollback.get("applied", False)),
            restart_recommended=bool(rollback.get("restart_recommended", False)),
            scenario=scenario.to_dict(),
            rollback=rollback,
            cleanup=_serializable_action_block(cleanup),
            notes=[
                "Rollback restores managed item DB state from the latest snapshot.",
                "Inventory cleanup is PARTIAL unless --cleanup-player-item reaches native player_remove_item=done in BridgeLab.",
            ],
            issues=issues,
        )

    def _item_runtime_sync(
        self,
        *,
        scenario: ItemEffectScenario,
        mode: str,
        runtime_sync_mode: str,
    ) -> RuntimeSyncResult:
        return sync_runtime_after_publish(
            settings=self.settings,
            mode=mode,
            runtime_sync_mode=_effective_runtime_sync_mode(scenario=scenario, runtime_sync_mode=runtime_sync_mode),
            soap_commands=_runtime_sync_commands(scenario, key="item_commands"),
            no_sync_note=(
                "Managed item rows changed in the live DB. "
                "No runtime reload command was sent; restart worldserver if item state or client cache stays stale."
            ),
            synced_note=(
                "Managed item rows changed in the live DB and configured runtime command(s) were sent. "
                "Restart worldserver if the live item state remains stale."
            ),
        )

    def _direct_grant_preflight(self, *, scenario: ItemEffectScenario) -> dict[str, Any]:
        if not _direct_grant_enabled(scenario):
            return {"enabled": False, "ready": True, "status": "disabled", "issues": []}
        readiness = self._native_action_readiness(
            action_kind="player_add_item",
            player_guid=scenario.player_guid,
            issue_prefix="direct_grant",
        )
        return {
            "enabled": True,
            "action_kind": "player_add_item",
            **readiness,
            "status": "ready" if readiness.get("ready", False) else "not_ready",
        }

    def _submit_direct_grant(self, *, scenario: ItemEffectScenario) -> dict[str, Any]:
        readiness = self._direct_grant_preflight(scenario=scenario)
        if not readiness.get("ready", False):
            return {
                **readiness,
                "ok": False,
                "status": "skipped",
                "message": "Native player_add_item policy/scope is not ready.",
            }
        config = scenario.direct_grant or {}
        count = max(1, int(config.get("count") or 1))
        payload = {
            "item_id": int(scenario.item_entry),
            "count": count,
            "soulbound": bool(config.get("soulbound", True)),
        }
        publish_attempt_id = self._latest_publish_log_id(item_entry=scenario.item_entry)
        attempt_token = f"publish:{publish_attempt_id}" if publish_attempt_id is not None else "publish:unknown"
        idempotency_key = (
            f"content_playcycle:{scenario.cycle_key}:player:{scenario.player_guid}:"
            f"item:{scenario.item_entry}:direct_grant:{attempt_token}"
        )
        try:
            request = self.native_bridge.submit(
                idempotency_key=idempotency_key,
                player_guid=scenario.player_guid,
                action_kind="player_add_item",
                payload=payload,
                created_by="wm.content.playcycle",
                risk_level=str(config.get("risk_level") or "medium"),
                expires_seconds=_int_or_default(config.get("expires_seconds"), 60),
                max_attempts=_int_or_default(config.get("max_attempts"), 3),
                purge_after_seconds=_int_or_none(config.get("purge_after_seconds")),
            )
            if bool(config.get("wait", True)):
                request = self.native_bridge.wait(request_id=int(request.request_id))
        except Exception as exc:
            return {
                **readiness,
                "ok": False,
                "status": "failed",
                "payload": payload,
                "issues": [PlaycycleIssue(path="direct_grant.native_bridge", message=str(exc))],
            }
        request_payload = request.to_dict()
        return {
            **readiness,
            "ok": request.status == "done",
            "status": request.status,
            "payload": payload,
            "idempotency_key": idempotency_key,
            "request": request_payload,
            "issues": [] if request.status == "done" else [
                PlaycycleIssue(
                    path="direct_grant.request",
                    message=f"Native player_add_item ended with status `{request.status}`.",
                )
            ],
            }

    def _latest_publish_log_id(self, *, item_entry: int) -> int | None:
        rows = self._world_rows(
            "SELECT id FROM wm_publish_log "
            "WHERE artifact_type = 'item' "
            f"AND artifact_entry = {int(item_entry)} "
            "AND action = 'publish' "
            "AND status = 'success' "
            "ORDER BY id DESC LIMIT 1",
            issue_path="direct_grant.publish_log",
            issues=[],
            warning_only=True,
        )
        if not rows:
            return None
        try:
            return int(rows[0]["id"])
        except (KeyError, TypeError, ValueError):
            return None

    def _cleanup_player_item(
        self,
        *,
        scenario: ItemEffectScenario,
        enabled: bool,
        admin_override: bool,
    ) -> dict[str, Any]:
        if not enabled:
            return {
                "enabled": False,
                "status": "skipped",
                "ok": True,
                "message": "Inventory cleanup not requested; DB rollback does not remove already granted player copies.",
                "issues": [],
            }
        readiness = self._native_action_readiness(
            action_kind="player_remove_item",
            player_guid=scenario.player_guid,
            issue_prefix="cleanup",
        )
        if not readiness.get("ready", False):
            return {
                "enabled": True,
                "action_kind": "player_remove_item",
                **readiness,
                "ok": False,
                "status": "skipped",
                "message": "Native player_remove_item policy/scope is not ready.",
            }
        reserved = self._world_rows(
            "SELECT ReservedID FROM wm_reserved_slot "
            "WHERE EntityType = 'item' "
            f"AND ReservedID = {int(scenario.item_entry)} LIMIT 1",
            issue_path="cleanup.reserved_slot",
            issues=[],
        )
        if not reserved and not admin_override:
            return {
                "enabled": True,
                "action_kind": "player_remove_item",
                **readiness,
                "ok": False,
                "status": "skipped",
                "issues": [
                    PlaycycleIssue(
                        path="cleanup.reserved_slot",
                        message="Refusing item removal because the entry is not present in wm_reserved_slot and no admin override was supplied.",
                    )
                ],
            }
        count = max(
            1,
            int((scenario.direct_grant or {}).get("remove_count") or (scenario.direct_grant or {}).get("count") or 1),
        )
        payload = {
            "item_id": int(scenario.item_entry),
            "count": count,
            "admin_override": bool(admin_override),
        }
        idempotency_key = f"content_playcycle:{scenario.cycle_key}:player:{scenario.player_guid}:item:{scenario.item_entry}:cleanup"
        try:
            request = self.native_bridge.submit(
                idempotency_key=idempotency_key,
                player_guid=scenario.player_guid,
                action_kind="player_remove_item",
                payload=payload,
                created_by="wm.content.playcycle",
                risk_level="medium",
                expires_seconds=60,
                max_attempts=3,
            )
            request = self.native_bridge.wait(request_id=int(request.request_id))
        except Exception as exc:
            return {
                "enabled": True,
                "action_kind": "player_remove_item",
                **readiness,
                "ok": False,
                "status": "failed",
                "payload": payload,
                "issues": [PlaycycleIssue(path="cleanup.native_bridge", message=str(exc))],
            }
        return {
            "enabled": True,
            "action_kind": "player_remove_item",
            **readiness,
            "ok": request.status == "done",
            "status": request.status,
            "payload": payload,
            "idempotency_key": idempotency_key,
            "request": request.to_dict(),
            "issues": [] if request.status == "done" else [
                PlaycycleIssue(
                    path="cleanup.request",
                    message=f"Native player_remove_item ended with status `{request.status}`.",
                )
            ],
        }

    def _native_action_readiness(self, *, action_kind: str, player_guid: int, issue_prefix: str) -> dict[str, Any]:
        issues: list[PlaycycleIssue] = []
        kind = NATIVE_ACTION_KIND_BY_ID.get(action_kind)
        implemented = bool(kind and kind.implemented)
        if not implemented:
            issues.append(PlaycycleIssue(path=f"{issue_prefix}.action_kind", message=f"{action_kind} is not implemented."))
        try:
            scoped = bool(self.native_bridge.is_player_scoped(player_guid=player_guid))
        except Exception as exc:
            scoped = False
            issues.append(PlaycycleIssue(path=f"{issue_prefix}.player_scope", message=str(exc)))
        try:
            policy = self.native_bridge.get_action_policy(action_kind=action_kind)
        except Exception as exc:
            policy = None
            issues.append(PlaycycleIssue(path=f"{issue_prefix}.policy", message=str(exc)))
        policy_enabled = bool(policy and policy.get("enabled"))
        if not scoped:
            issues.append(
                PlaycycleIssue(
                    path=f"{issue_prefix}.player_scope",
                    message=f"Player {player_guid} is not enabled in wm_bridge_player_scope.",
                )
            )
        if not policy_enabled:
            issues.append(
                PlaycycleIssue(
                    path=f"{issue_prefix}.policy",
                    message=f"Native action policy for {action_kind} is missing or disabled.",
                )
            )
        return {
            "implemented": implemented,
            "player_scoped": scoped,
            "policy": policy,
            "ready": implemented and scoped and policy_enabled,
            "issues": issues,
        }

    def _verify_state(self, *, scenario: ItemEffectScenario) -> dict[str, Any]:
        issues: list[PlaycycleIssue] = []
        expectations = scenario.verify_expectations or {}
        item_rows = self._world_rows(
            "SELECT entry, name, description FROM item_template "
            f"WHERE entry = {int(scenario.item_entry)} LIMIT 1",
            issue_path="verify.item_template",
            issues=issues,
        )
        publish_rows = self._world_rows(
            "SELECT id, action, status, notes FROM wm_publish_log "
            "WHERE artifact_type = 'item' "
            f"AND artifact_entry = {int(scenario.item_entry)} "
            "ORDER BY id DESC LIMIT 5",
            issue_path="verify.publish_log",
            issues=issues,
        )
        snapshot_rows = self._world_rows(
            "SELECT id FROM wm_rollback_snapshot "
            "WHERE artifact_type = 'item' "
            f"AND artifact_entry = {int(scenario.item_entry)} "
            "ORDER BY id DESC LIMIT 1",
            issue_path="verify.rollback_snapshot",
            issues=issues,
        )
        slot_rows = self._world_rows(
            "SELECT EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON "
            "FROM wm_reserved_slot "
            f"WHERE EntityType = 'item' AND ReservedID = {int(scenario.item_entry)} LIMIT 1",
            issue_path="verify.reserved_slot",
            issues=issues,
        )
        inventory_rows = self._char_rows(
            "SELECT ci.guid AS OwnerGUID, ci.item AS ItemGuid, ii.itemEntry AS ItemEntry "
            "FROM character_inventory ci "
            "JOIN item_instance ii ON ii.guid = ci.item "
            f"WHERE ci.guid = {int(scenario.player_guid)} "
            f"AND ii.itemEntry = {int(scenario.item_entry)} "
            "LIMIT 10",
            issue_path="verify.inventory",
            issues=issues,
            warning_only=True,
        )
        if not item_rows:
            issues.append(PlaycycleIssue(path="verify.item_template", message=f"item_template row {scenario.item_entry} is missing."))
        if not publish_rows and bool(expectations.get("require_publish_log", True)):
            issues.append(PlaycycleIssue(path="verify.publish_log", message="No wm_publish_log rows found for this item."))
        if not snapshot_rows and bool(expectations.get("require_rollback_snapshot", True)):
            issues.append(PlaycycleIssue(path="verify.rollback_snapshot", message="No wm_rollback_snapshot row found for this item."))
        if not slot_rows and bool(expectations.get("require_reserved_slot", True)):
            issues.append(PlaycycleIssue(path="verify.reserved_slot", message="No wm_reserved_slot row found for this item."))
        require_inventory = bool(expectations.get("require_inventory_receipt", False)) or str(
            expectations.get("inventory_receipt") or ""
        ).lower() == "required"
        if require_inventory and not inventory_rows:
            issues.append(PlaycycleIssue(path="verify.inventory", message="No player inventory copy found for this item."))
        return {
            "item_template_rows": item_rows,
            "publish_log_rows": publish_rows,
            "rollback_snapshot_rows": snapshot_rows,
            "reserved_slot_rows": slot_rows,
            "inventory_rows": inventory_rows,
            "visible_expectations": {
                "wearer_aura": expectations.get("visible_wearer_aura"),
                "target_debuff": expectations.get("visible_target_debuff"),
            },
            "issues": issues,
        }

    def _load_promotion_template(self, *, config: dict[str, Any]) -> dict[str, Any]:
        if config.get("template_key") not in (None, ""):
            path = resolve_reactive_bounty_template_path(str(config["template_key"]))
        elif config.get("template_path") not in (None, ""):
            path = _resolve_repo_path(config["template_path"])
        else:
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Promotion bounty template must be a JSON object: {path}")
        return raw

    def _build_promotion_rule(
        self,
        *,
        config: dict[str, Any],
        scenario: ItemEffectScenario,
        player_guid: int,
        rule_key: str,
        quest_id: int,
    ) -> ReactiveQuestRule:
        subject_entry = int(config["subject_entry"])
        turn_in_npc_entry = int(config["turn_in_npc_entry"])
        player_name = self.reactive_store.fetch_character_name(player_guid=player_guid)
        subject = self.resolver.resolve(entry=subject_entry)
        turn_in = self.resolver.resolve(entry=turn_in_npc_entry)
        target_name = _str_or_none(config.get("objective_target_name")) or subject.name
        quest_title = _str_or_none(config.get("quest_title")) or f"Bounty: {target_name}"
        metadata: dict[str, Any] = {"installer": "wm.content.playcycle"}
        for key in (
            "objective_target_name",
            "quest_title",
            "subject_name_prefix",
            "reward_xp_difficulty",
            "reward_spell_id",
            "reward_spell_display_id",
        ):
            if config.get(key) not in (None, ""):
                metadata[key] = config[key]
        metadata["reward_item_entry"] = int(config.get("reward_item_entry") or scenario.item_entry)
        metadata["reward_item_name"] = str(config.get("reward_item_name") or scenario.effect_label)
        metadata["reward_item_count"] = int(config.get("reward_item_count") or 1)
        parsed_reputations = _reward_reputations_from_value(config.get("reward_reputations"))
        if parsed_reputations:
            metadata["reward_reputations"] = parsed_reputations

        return ReactiveQuestRule(
            rule_key=rule_key,
            is_active=True,
            player_guid_scope=player_guid,
            subject_type="creature",
            subject_entry=subject_entry,
            trigger_event_type="kill",
            kill_threshold=int(config.get("kill_threshold") or 4),
            window_seconds=int(config.get("window_seconds") or 300),
            quest_id=quest_id,
            turn_in_npc_entry=turn_in_npc_entry,
            grant_mode="direct_quest_add",
            post_reward_cooldown_seconds=int(config.get("post_reward_cooldown_seconds") or 60),
            metadata=metadata,
            notes=[f"content_playcycle:{scenario.cycle_key}", "fresh_reserved_reward_iteration"],
            player_scope=PlayerRef(guid=player_guid, name=player_name),
            subject=CreatureRef(entry=subject.entry, name=subject.name),
            quest=QuestRef(id=quest_id, title=quest_title),
            turn_in_npc=NpcRef(entry=turn_in.entry, name=turn_in.name),
        )

    def _world_rows(
        self,
        sql: str,
        *,
        issue_path: str,
        issues: list[PlaycycleIssue],
        warning_only: bool = False,
    ) -> list[dict[str, Any]]:
        try:
            return self.client.query(
                host=self.settings.world_db_host,
                port=self.settings.world_db_port,
                user=self.settings.world_db_user,
                password=self.settings.world_db_password,
                database=self.settings.world_db_name,
                sql=sql,
            )
        except MysqlCliError as exc:
            issues.append(
                PlaycycleIssue(
                    path=issue_path,
                    message=str(exc),
                    severity="warning" if warning_only else "error",
                )
            )
            return []

    def _char_rows(
        self,
        sql: str,
        *,
        issue_path: str,
        issues: list[PlaycycleIssue],
        warning_only: bool = False,
    ) -> list[dict[str, Any]]:
        try:
            return self.client.query(
                host=self.settings.char_db_host,
                port=self.settings.char_db_port,
                user=self.settings.char_db_user,
                password=self.settings.char_db_password,
                database=self.settings.char_db_name,
                sql=sql,
            )
        except MysqlCliError as exc:
            issues.append(
                PlaycycleIssue(
                    path=issue_path,
                    message=str(exc),
                    severity="warning" if warning_only else "error",
                )
            )
            return []


def load_item_effect_scenario(path: str | Path, *, player_guid: int | None = None) -> ItemEffectScenario:
    scenario_path = Path(path)
    raw = json.loads(scenario_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Content playcycle scenario JSON must be an object.")
    _validate_object_keys(raw, allowed=_TOP_LEVEL_KEYS, path="")
    _reject_forbidden_keys(raw, path="")
    schema_version = str(raw.get("schema_version") or "")
    if schema_version != SCENARIO_VERSION:
        raise ValueError(f"Unsupported scenario schema_version `{schema_version}`; expected `{SCENARIO_VERSION}`.")
    for key in ("cycle_key", "player_guid", "item_draft_path", "item_entry", "effect_label"):
        if raw.get(key) in (None, ""):
            raise ValueError(f"Scenario field `{key}` is required.")

    runtime_sync = _dict_value(raw.get("runtime_sync"), "runtime_sync")
    direct_grant = _dict_value(raw.get("direct_grant"), "direct_grant")
    promotion = _dict_value(raw.get("promotion_bounty_template"), "promotion_bounty_template")
    verify_expectations = _dict_value(raw.get("verify_expectations"), "verify_expectations")
    _validate_object_keys(runtime_sync, allowed=_RUNTIME_SYNC_KEYS, path="runtime_sync")
    _validate_object_keys(direct_grant, allowed=_DIRECT_GRANT_KEYS, path="direct_grant")
    _validate_object_keys(promotion, allowed=_PROMOTION_KEYS, path="promotion_bounty_template")
    _validate_object_keys(verify_expectations, allowed=_VERIFY_KEYS, path="verify_expectations")

    resolved_player_guid = int(player_guid if player_guid is not None else raw["player_guid"])
    return ItemEffectScenario(
        schema_version=schema_version,
        cycle_key=str(raw["cycle_key"]),
        player_guid=resolved_player_guid,
        item_draft_path=_resolve_repo_path(raw["item_draft_path"]),
        item_entry=int(raw["item_entry"]),
        effect_label=str(raw["effect_label"]),
        runtime_sync=runtime_sync,
        direct_grant=direct_grant,
        promotion_bounty_template=promotion,
        verify_expectations=verify_expectations,
        notes=[str(note) for note in raw.get("notes", [])],
    )


def _render_summary(result: ItemEffectPlaycycleResult) -> str:
    lines = [
        f"mode: {result.mode}",
        f"cycle_key: {result.cycle_key}",
        f"player_guid: {result.player_guid}",
        f"item_entry: {result.item_entry}",
        f"effect_label: {result.effect_label}",
        f"outcome: {result.outcome}",
        f"ok: {str(result.ok).lower()}",
        f"applied: {str(result.applied).lower()}",
        f"restart_recommended: {str(result.restart_recommended).lower()}",
    ]
    if result.publish is not None:
        lines.extend(
            [
                "",
                f"publish.applied: {str(bool(result.publish.get('applied', False))).lower()}",
                f"publish.validation_ok: {str(bool((result.publish.get('validation') or {}).get('ok', False))).lower()}",
                f"publish.preflight_ok: {str(bool((result.publish.get('preflight') or {}).get('ok', False))).lower()}",
            ]
        )
    if result.direct_grant is not None:
        lines.extend(
            [
                "",
                f"direct_grant.enabled: {str(bool(result.direct_grant.get('enabled', False))).lower()}",
                f"direct_grant.ready: {str(bool(result.direct_grant.get('ready', False))).lower()}",
                f"direct_grant.status: {result.direct_grant.get('status')}",
            ]
        )
    if result.promotion is not None:
        lines.extend(
            [
                "",
                f"promotion.quest_id: {result.promotion.get('allocated_quest_id')}",
                f"promotion.applied: {str(bool((result.promotion.get('quest_publish') or {}).get('applied', False))).lower()}",
            ]
        )
    if result.rollback is not None:
        lines.extend(
            [
                "",
                f"rollback.applied: {str(bool(result.rollback.get('applied', False))).lower()}",
                f"rollback.restored_action: {result.rollback.get('restored_action')}",
            ]
        )
    if result.cleanup is not None:
        lines.extend(
            [
                f"cleanup.enabled: {str(bool(result.cleanup.get('enabled', False))).lower()}",
                f"cleanup.status: {result.cleanup.get('status')}",
            ]
        )
    lines.extend(["", "issues:"])
    if not result.issues:
        lines.append("- none")
    else:
        for issue in result.issues:
            lines.append(f"- {issue.path} | {issue.severity} | {issue.message}")
    lines.extend(["", "notes:"])
    if not result.notes:
        lines.append("- none")
    else:
        lines.extend(f"- {note}" for note in result.notes)
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.content.playcycle")
    subparsers = parser.add_subparsers(dest="playcycle_kind", required=True)
    item_effect = subparsers.add_parser("item-effect")
    item_effect.add_argument("--scenario-json", type=Path, required=True)
    item_effect.add_argument("--mode", choices=["dry-run", "apply", "verify", "promote-quest", "rollback"], default="dry-run")
    item_effect.add_argument("--player-guid", type=int)
    item_effect.add_argument("--runtime-sync", choices=["scenario", "auto", "off", "soap"], default="scenario")
    item_effect.add_argument("--cleanup-player-item", action="store_true")
    item_effect.add_argument("--admin-override-remove-item", action="store_true")
    item_effect.add_argument("--summary", action="store_true")
    item_effect.add_argument("--output-json", type=Path)
    item_effect.add_argument("--write-artifact", action="store_true")
    item_effect.add_argument("--artifact-dir", type=Path, default=Path("artifacts/content_playcycle"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.playcycle_kind != "item-effect":
        parser.error("Only item-effect playcycles are supported.")
    scenario = load_item_effect_scenario(args.scenario_json, player_guid=args.player_guid)
    settings = Settings.from_env()
    client = MysqlCliClient()
    service = ItemEffectPlaycycle(client=client, settings=settings)
    result = service.run(
        scenario=scenario,
        mode=args.mode,
        runtime_sync_mode=args.runtime_sync,
        cleanup_player_item=args.cleanup_player_item,
        admin_override_remove_item=args.admin_override_remove_item,
    )
    raw = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    output_json = args.output_json
    if output_json is None and args.write_artifact:
        safe_mode = str(args.mode).replace("-", "_")
        output_json = args.artifact_dir.joinpath(f"{scenario.cycle_key}_{safe_mode}.json")
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(raw, encoding="utf-8")
    if args.summary or output_json is not None:
        print(_render_summary(result))
        if output_json is not None:
            print("")
            print(f"output_json: {output_json}")
    else:
        print(raw)
    return 0 if result.ok else 2


def _resolve_repo_path(value: object) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[3].joinpath(path)


def _validate_object_keys(value: dict[str, Any], *, allowed: set[str], path: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        prefix = f"{path}." if path else ""
        raise ValueError(f"Unsupported scenario field(s): {', '.join(prefix + key for key in unknown)}")


def _reject_forbidden_keys(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _FORBIDDEN_KEY_PARTS):
                raise ValueError(f"Forbidden freeform mutation-style scenario field: {path + '.' if path else ''}{key}")
            _reject_forbidden_keys(nested, path=f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_keys(nested, path=f"{path}[{index}]")


def _dict_value(value: object, field_name: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Scenario field `{field_name}` must be an object.")
    return dict(value)


def _draft_consistency_issues(*, scenario: ItemEffectScenario, draft: Any) -> list[PlaycycleIssue]:
    issues: list[PlaycycleIssue] = []
    if int(draft.item_entry) != int(scenario.item_entry):
        issues.append(
            PlaycycleIssue(
                path="item_entry",
                message=f"Scenario item_entry {scenario.item_entry} does not match draft item_entry {draft.item_entry}.",
            )
        )
    return issues


def _publish_preflight_ok(publish: dict[str, Any]) -> bool:
    return bool((publish.get("validation") or {}).get("ok", False)) and bool((publish.get("preflight") or {}).get("ok", False))


def _issues_from_publish(publish: dict[str, Any]) -> list[PlaycycleIssue]:
    issues: list[PlaycycleIssue] = []
    for section in ("validation", "preflight"):
        payload = publish.get(section) or {}
        for issue in payload.get("issues", []) or []:
            if not isinstance(issue, dict):
                continue
            issues.append(
                PlaycycleIssue(
                    path=f"{section}.{issue.get('path')}",
                    message=str(issue.get("message") or ""),
                    severity=str(issue.get("severity") or "error"),
                )
            )
    return issues


def _runtime_sync_commands(scenario: ItemEffectScenario, *, key: str) -> list[str]:
    return [str(command) for command in (scenario.runtime_sync or {}).get(key, [])]


def _effective_runtime_sync_mode(*, scenario: ItemEffectScenario, runtime_sync_mode: str) -> str:
    if runtime_sync_mode != "scenario":
        return runtime_sync_mode
    return str((scenario.runtime_sync or {}).get("mode") or "auto")


def _direct_grant_enabled(scenario: ItemEffectScenario) -> bool:
    return bool((scenario.direct_grant or {}).get("enabled", False))


def _has_error(issues: list[PlaycycleIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def _base_result(
    *,
    scenario: ItemEffectScenario,
    mode: str,
    outcome: str,
    issues: list[PlaycycleIssue],
) -> ItemEffectPlaycycleResult:
    return ItemEffectPlaycycleResult(
        mode=mode,
        cycle_key=scenario.cycle_key,
        player_guid=scenario.player_guid,
        item_entry=scenario.item_entry,
        effect_label=scenario.effect_label,
        outcome=outcome,
        ok=not _has_error(issues),
        scenario=scenario.to_dict(),
        issues=issues,
    )


def _serializable_action_block(block: dict[str, Any]) -> dict[str, Any]:
    serializable = dict(block)
    issues = serializable.get("issues")
    if isinstance(issues, list):
        serializable["issues"] = [issue.to_dict() if isinstance(issue, PlaycycleIssue) else issue for issue in issues]
    return serializable


def _bridge_lab_notes(*, settings: Settings, player_guid: int) -> list[str]:
    notes: list[str] = []
    if int(player_guid) == 5406 and (int(settings.world_db_port) != 33307 or int(settings.char_db_port) != 33307):
        notes.append("BridgeLab proof for Jecia expects WM_WORLD_DB_PORT=33307 and WM_CHAR_DB_PORT=33307.")
    return notes


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _int_or_default(value: object, default: int) -> int:
    if value in (None, ""):
        return default
    return int(value)


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


if __name__ == "__main__":
    sys.exit(main())
