from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.items.models import ManagedItemDraft
from wm.items.publish import ItemPublisher
from wm.items.publish import load_managed_item_draft
from wm.reserved.custom_id_registry import load_custom_id_registry
from wm.reserved.db_allocator import ReservedSlotDbAllocator
from wm.reserved.models import ReservedSlot
from wm.runtime_sync import RuntimeCommandResult
from wm.runtime_sync import SoapRuntimeClient
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.actions import NativeBridgeActionClient
from wm.spells.models import ManagedSpellDraft
from wm.spells.publish import SpellPublisher
from wm.spells.publish import load_managed_spell_draft
from wm.spells.configure import update_wm_spells_runtime_config
from wm.spells.platform import SpellBehaviorDebugClient
from wm.spells.platform import create_shell_draft
from wm.spells.platform import load_shell_draft
from wm.spells.platform import SpellPlatformPublisher
from wm.spells.platform import write_shell_draft_file
from wm.spells.shell_bank import load_spell_shell_bank


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_draft_root() -> Path:
    return _repo_root().joinpath(".wm-bootstrap", "state", "content-drafts")


@dataclass(slots=True)
class DraftEnvelope:
    kind: str
    template: str
    draft: dict[str, Any]
    reserved_slot: dict[str, Any] | None = None
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "kind": self.kind,
            "template": self.template,
            "draft": self.draft,
        }
        if self.reserved_slot is not None:
            payload["reserved_slot"] = self.reserved_slot
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(slots=True)
class WorkbenchRuntimeResult:
    mode: str
    command: str
    ok: bool
    executed: bool
    result: str | None = None
    fault_code: str | None = None
    fault_string: str | None = None
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_item_draft(
    *,
    allocator: ReservedSlotDbAllocator,
    name: str,
    base_item_entry: int,
    player_guid: int | None = None,
    description: str | None = None,
    quality: int | None = 2,
    item_level: int | None = 10,
    required_level: int | None = 1,
    stackable: int | None = 1,
    max_count: int | None = 1,
) -> tuple[ManagedItemDraft, ReservedSlot]:
    slug = _slugify(name)
    slot = allocator.allocate_next_free_slot(
        entity_type="item",
        arc_key=f"wm_content:item:{slug}",
        character_guid=player_guid,
        notes=[
            "wm_content_workbench",
            f"name:{name}",
            f"base_item_entry:{int(base_item_entry)}",
        ],
    )
    if slot is None:
        raise ValueError("No free reserved item slot is available.")
    draft = ManagedItemDraft(
        item_entry=int(slot.reserved_id),
        base_item_entry=int(base_item_entry),
        name=str(name),
        description=description,
        quality=quality,
        item_level=item_level,
        required_level=required_level,
        stackable=stackable,
        max_count=max_count,
        clear_spells=True,
        tags=["wm_generated", "managed_item_slot", "workbench"],
        template_defaults={
            "RandomProperty": 0,
            "RandomSuffix": 0,
            "ScalingStatDistribution": 0,
            "ScalingStatValue": 0,
        },
    )
    return draft, slot


def create_passive_draft(
    *,
    allocator: ReservedSlotDbAllocator,
    name: str,
    player_guid: int | None = None,
    helper_spell_id: int | None = None,
    aura_description: str | None = None,
) -> tuple[ManagedSpellDraft, ReservedSlot]:
    slug = _slugify(name)
    slot = allocator.allocate_next_free_slot(
        entity_type="spell",
        arc_key=f"wm_content:passive:{slug}",
        character_guid=player_guid,
        notes=[
            "wm_content_workbench",
            f"name:{name}",
            "slot_kind:passive_slot",
        ],
    )
    if slot is None:
        raise ValueError("No free reserved spell slot is available.")
    draft = ManagedSpellDraft(
        spell_entry=int(slot.reserved_id),
        slot_kind="passive_slot",
        name=str(name),
        helper_spell_id=helper_spell_id,
        aura_description=aura_description,
        tags=["wm_generated", "spell_slot", "passive_slot", "workbench"],
    )
    return draft, slot


def create_trigger_spell_draft(
    *,
    allocator: ReservedSlotDbAllocator,
    name: str,
    trigger_item_entry: int,
    player_guid: int | None = None,
    helper_spell_id: int | None = None,
    aura_description: str | None = None,
) -> tuple[ManagedSpellDraft, ReservedSlot]:
    slug = _slugify(name)
    slot = allocator.allocate_next_free_slot(
        entity_type="spell",
        arc_key=f"wm_content:item_trigger:{slug}",
        character_guid=player_guid,
        notes=[
            "wm_content_workbench",
            f"name:{name}",
            "slot_kind:item_trigger_slot",
            f"trigger_item_entry:{int(trigger_item_entry)}",
        ],
    )
    if slot is None:
        raise ValueError("No free reserved spell slot is available.")
    draft = ManagedSpellDraft(
        spell_entry=int(slot.reserved_id),
        slot_kind="item_trigger_slot",
        name=str(name),
        helper_spell_id=helper_spell_id,
        trigger_item_entry=int(trigger_item_entry),
        aura_description=aura_description,
        tags=["wm_generated", "spell_slot", "item_trigger_slot", "workbench"],
    )
    return draft, slot


def create_visible_spell_draft(
    *,
    allocator: ReservedSlotDbAllocator,
    name: str,
    base_visible_spell_id: int,
    player_guid: int | None = None,
    helper_spell_id: int | None = None,
    aura_description: str | None = None,
) -> tuple[ManagedSpellDraft, ReservedSlot]:
    slug = _slugify(name)
    slot = allocator.allocate_next_free_slot(
        entity_type="spell",
        arc_key=f"wm_content:visible_spell:{slug}",
        character_guid=player_guid,
        notes=[
            "wm_content_workbench",
            f"name:{name}",
            "slot_kind:visible_spell_slot",
            f"base_visible_spell_id:{int(base_visible_spell_id)}",
        ],
    )
    if slot is None:
        raise ValueError("No free reserved spell slot is available.")
    draft = ManagedSpellDraft(
        spell_entry=int(slot.reserved_id),
        slot_kind="visible_spell_slot",
        name=str(name),
        base_visible_spell_id=int(base_visible_spell_id),
        helper_spell_id=helper_spell_id,
        aura_description=aura_description,
        tags=["wm_generated", "spell_slot", "visible_spell_slot", "workbench"],
    )
    return draft, slot


def build_additem_command(*, player: str, item_entry: int, count: int) -> str:
    return f".additem {player} {int(item_entry)} {int(count)}"


def build_send_items_command(
    *,
    player_name: str,
    item_entry: int,
    count: int,
    subject: str = "WM Content",
    body: str = "Prototype item delivery.",
) -> str:
    safe_subject = str(subject).replace('"', "'").replace("\r", " ").replace("\n", " ").strip() or "WM Content"
    safe_body = str(body).replace('"', "'").replace("\r", " ").replace("\n", " ").strip() or "Prototype item delivery."
    return f'.send items {player_name} "{safe_subject}" "{safe_body}" {int(item_entry)}:{int(count)}'


def build_player_learn_command(*, player: str, spell_entry: int, all_ranks: bool = False) -> str:
    suffix = " all" if all_ranks else ""
    return f".player learn {player} {int(spell_entry)}{suffix}"


def build_player_unlearn_command(*, player: str, spell_entry: int, all_ranks: bool = False) -> str:
    suffix = " all" if all_ranks else ""
    return f".player unlearn {player} {int(spell_entry)}{suffix}"


def resolve_managed_spell_runtime_target(*, draft: ManagedSpellDraft) -> dict[str, Any]:
    if draft.slot_kind == "visible_spell_slot":
        if draft.base_visible_spell_id in (None, 0):
            return {
                "can_runtime_learn": False,
                "artifact_spell_entry": int(draft.spell_entry),
                "reason": (
                    f"Visible spell slot {int(draft.spell_entry)} is missing base_visible_spell_id, "
                    "so WM cannot resolve a learnable runtime spell identity."
                ),
            }
        return {
            "can_runtime_learn": True,
            "artifact_spell_entry": int(draft.spell_entry),
            "runtime_spell_entry": int(draft.base_visible_spell_id),
            "runtime_source": "base_visible_spell_id",
        }

    return {
        "can_runtime_learn": False,
        "artifact_spell_entry": int(draft.spell_entry),
        "reason": (
            f"{draft.slot_kind} {int(draft.spell_entry)} is a managed spell-slot artifact, not a directly learnable spell identity. "
            "Publish the helper/proc rows first, then bind a real visible base spell or shell when player learning is required."
        ),
    }


def write_draft_file(
    *,
    kind: str,
    template: str,
    draft: ManagedItemDraft | ManagedSpellDraft,
    slot: ReservedSlot,
    out_path: Path | None = None,
) -> Path:
    output = out_path or _default_draft_path(kind=kind, reserved_id=int(slot.reserved_id), name=getattr(draft, "name", kind))
    output.parent.mkdir(parents=True, exist_ok=True)
    envelope = DraftEnvelope(
        kind=kind,
        template=template,
        draft=draft.to_dict(),
        reserved_slot=slot.to_record(),
        notes=[
            "Generated by wm.content.workbench.",
            "Publish with the matching publish-* subcommand.",
        ],
    )
    output.write_text(json.dumps(envelope.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return output


def execute_runtime_command(
    *,
    settings: Settings,
    command: str,
    mode: str,
) -> WorkbenchRuntimeResult:
    if mode not in {"dry-run", "apply"}:
        raise ValueError(f"Unsupported runtime command mode: {mode}")
    if mode == "dry-run":
        return WorkbenchRuntimeResult(
            mode=mode,
            command=command,
            ok=bool(command),
            executed=False,
            notes=["Dry-run only; no SOAP command was sent."],
        )
    if not settings.soap_enabled:
        return WorkbenchRuntimeResult(
            mode=mode,
            command=command,
            ok=False,
            executed=False,
            fault_code="PreviewError",
            fault_string="WM_SOAP_ENABLED is not set.",
        )
    if not settings.soap_user or not settings.soap_password:
        return WorkbenchRuntimeResult(
            mode=mode,
            command=command,
            ok=False,
            executed=False,
            fault_code="PreviewError",
            fault_string="WM_SOAP_USER / WM_SOAP_PASSWORD are required.",
        )
    result = SoapRuntimeClient(settings=settings).execute_command(command)
    benign_known_spell = (
        command.startswith(".player learn ")
        and isinstance(result.fault_string, str)
        and "already know that spell" in result.fault_string.lower()
    )
    return WorkbenchRuntimeResult(
        mode=mode,
        command=command,
        ok=bool(result.ok or benign_known_spell),
        executed=True,
        result=result.result or None,
        fault_code=None if benign_known_spell else result.fault_code,
        fault_string=None if benign_known_spell else result.fault_string,
        notes=(
            ["Player already knows the spell; treating the learn command as idempotent."]
            if benign_known_spell
            else None
        ),
    )


def execute_item_delivery_command(
    *,
    settings: Settings,
    player_ref: dict[str, Any],
    item_entry: int,
    count: int,
    delivery: str,
    mail_subject: str,
    mail_body: str,
    mode: str,
) -> WorkbenchRuntimeResult:
    if delivery not in {"auto", "additem", "mail"}:
        raise ValueError(f"Unsupported item delivery mode: {delivery}")
    additem_command = build_additem_command(
        player=str(player_ref["command_player"]),
        item_entry=item_entry,
        count=count,
    )
    mail_command = build_send_items_command(
        player_name=str(player_ref["player_name"]),
        item_entry=item_entry,
        count=count,
        subject=mail_subject,
        body=mail_body,
    )
    if delivery == "additem":
        return execute_runtime_command(settings=settings, command=additem_command, mode=mode)
    if delivery == "mail":
        return execute_runtime_command(settings=settings, command=mail_command, mode=mode)

    additem_result = execute_runtime_command(settings=settings, command=additem_command, mode=mode)
    if mode != "apply" or additem_result.ok:
        return additem_result

    mail_result = execute_runtime_command(settings=settings, command=mail_command, mode=mode)
    fallback_notes = [
        "Primary .additem delivery failed; attempted .send items fallback.",
        f"additem_fault={additem_result.fault_string or additem_result.fault_code or 'unknown'}",
    ]
    if mail_result.notes:
        fallback_notes.extend(mail_result.notes)
    mail_result.notes = fallback_notes
    return mail_result


def execute_spell_runtime_action(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_ref: dict[str, Any],
    spell_entry: int,
    action_kind: str,
    mode: str,
    all_ranks: bool = False,
    created_by: str = "wm_content_workbench",
) -> WorkbenchRuntimeResult:
    if action_kind not in {"player_learn_spell", "player_unlearn_spell"}:
        raise ValueError(f"Unsupported spell runtime action kind: {action_kind}")
    fallback_command = (
        build_player_learn_command(
            player=str(player_ref["command_player"]),
            spell_entry=spell_entry,
            all_ranks=all_ranks,
        )
        if action_kind == "player_learn_spell"
        else build_player_unlearn_command(
            player=str(player_ref["command_player"]),
            spell_entry=spell_entry,
            all_ranks=all_ranks,
        )
    )
    if mode == "dry-run":
        return WorkbenchRuntimeResult(
            mode=mode,
            command=f"native:{action_kind} player_guid={player_ref['player_guid']} spell_id={int(spell_entry)}",
            ok=True,
            executed=False,
            notes=[
                "Dry-run only; no native bridge action was submitted.",
                "Preferred transport is native_bridge_action with SOAP fallback if the bridge rejects or cannot execute it.",
            ],
        )
    if all_ranks:
        result = execute_runtime_command(settings=settings, command=fallback_command, mode=mode)
        result.notes = list(result.notes or []) + ["Used SOAP fallback because native spell learn/unlearn does not support all-ranks mode."]
        return _verify_character_spell_runtime_state(
            client=client,
            settings=settings,
            player_guid=int(player_ref["player_guid"]),
            spell_entry=int(spell_entry),
            action_kind=action_kind,
            result=result,
        )

    action_meta = NATIVE_ACTION_KIND_BY_ID.get(action_kind)
    if action_meta is None or not action_meta.implemented:
        result = execute_runtime_command(settings=settings, command=fallback_command, mode=mode)
        result.notes = list(result.notes or []) + ["Used SOAP fallback because the native bridge action is not implemented."]
        return _verify_character_spell_runtime_state(
            client=client,
            settings=settings,
            player_guid=int(player_ref["player_guid"]),
            spell_entry=int(spell_entry),
            action_kind=action_kind,
            result=result,
        )

    action_client = NativeBridgeActionClient(client=client, settings=settings)
    request = action_client.submit(
        idempotency_key=f"wm.content.workbench:{action_kind}:{int(player_ref['player_guid'])}:{int(spell_entry)}",
        player_guid=int(player_ref["player_guid"]),
        action_kind=action_kind,
        payload={"spell_id": int(spell_entry)},
        created_by=created_by,
        risk_level=action_meta.default_risk,
        expires_seconds=60,
        purge_after_seconds=86400,
    )
    final = action_client.wait(request_id=request.request_id)
    native_ok = final.status == "done" and bool(final.result.get("ok", True))
    if native_ok:
        return _verify_character_spell_runtime_state(
            client=client,
            settings=settings,
            player_guid=int(player_ref["player_guid"]),
            spell_entry=int(spell_entry),
            action_kind=action_kind,
            result=WorkbenchRuntimeResult(
                mode=mode,
                command=f"native:{action_kind} player_guid={player_ref['player_guid']} spell_id={int(spell_entry)}",
                ok=True,
                executed=True,
                result=json.dumps(final.to_dict(), ensure_ascii=False),
                notes=[
                    "transport=native_bridge_action",
                    f"native_request_id={final.request_id}",
                ],
            ),
        )

    fallback_notes = [
        f"Native bridge action ended with status={final.status}.",
        f"native_request_id={final.request_id}",
    ]
    if final.error_text not in (None, ""):
        fallback_notes.append(f"native_error={final.error_text}")
    if settings.soap_enabled:
        fallback_result = execute_runtime_command(settings=settings, command=fallback_command, mode=mode)
        fallback_result.notes = fallback_notes + list(fallback_result.notes or []) + ["Used SOAP fallback after native bridge rejection/failure."]
        return _verify_character_spell_runtime_state(
            client=client,
            settings=settings,
            player_guid=int(player_ref["player_guid"]),
            spell_entry=int(spell_entry),
            action_kind=action_kind,
            result=fallback_result,
        )

    return WorkbenchRuntimeResult(
        mode=mode,
        command=f"native:{action_kind} player_guid={player_ref['player_guid']} spell_id={int(spell_entry)}",
        ok=False,
        executed=True,
        fault_code=final.status,
        fault_string=final.error_text or "Native bridge action did not succeed and SOAP fallback is unavailable.",
        result=json.dumps(final.to_dict(), ensure_ascii=False),
        notes=fallback_notes,
    )


def _verify_character_spell_runtime_state(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    spell_entry: int,
    action_kind: str,
    result: WorkbenchRuntimeResult,
) -> WorkbenchRuntimeResult:
    if result.mode != "apply" or not result.ok:
        return result

    should_exist = action_kind == "player_learn_spell"
    if settings.soap_enabled and settings.soap_user and settings.soap_password:
        save_result = execute_runtime_command(settings=settings, command=".saveall", mode="apply")
        result.notes = list(result.notes or []) + [
            f"saveall_ok={str(save_result.ok).lower()} executed={str(save_result.executed).lower()}"
        ]
        if save_result.fault_code not in (None, ""):
            result.notes.append(f"saveall_fault_code={save_result.fault_code}")
        if save_result.fault_string not in (None, ""):
            result.notes.append(f"saveall_fault={save_result.fault_string}")

    present = False
    attempts = 0
    for attempt in range(1, 6):
        attempts = attempt
        rows = client.query(
            host=settings.char_db_host,
            port=settings.char_db_port,
            user=settings.char_db_user,
            password=settings.char_db_password,
            database=settings.char_db_name,
            sql=(
                "SELECT guid, spell FROM character_spell "
                f"WHERE guid = {int(player_guid)} AND spell = {int(spell_entry)} LIMIT 1"
            ),
        )
        present = bool(rows)
        if present == should_exist:
            break
        if attempt < 5:
            time.sleep(0.25)
    result.notes = list(result.notes or []) + [
        f"character_spell_verify_attempts={attempts}",
        f"character_spell_present={str(present).lower()} expected_present={str(should_exist).lower()}"
    ]
    if present == should_exist:
        return result

    result.ok = False
    result.fault_code = "runtime_verification_failed"
    expectation = "present" if should_exist else "absent"
    result.fault_string = (
        f"character_spell verification failed for player {int(player_guid)} spell {int(spell_entry)}: "
        f"expected row to be {expectation}."
    )
    return result


def configure_twin_skeleton_runtime(
    *,
    settings: Settings,
    player_guid: int,
    shell_spell_id: int,
    mode: str,
    config_path: Path | None = None,
    reload_via_soap: bool = False,
    reload_command: str = ".reload config",
) -> dict[str, Any]:
    config_result = update_wm_spells_runtime_config(
        config_path=config_path or Path(settings.wm_spells_config_path),
        player_guids=[int(player_guid)],
        shell_spell_ids=[int(shell_spell_id)],
        append_players=True,
        replace_shell_spell_ids=False,
        ensure_enabled=True,
        enable_debug_invoke=True,
        debug_poll_interval_ms=50,
        ensure_bonebound_enabled=True,
        write=(mode == "apply"),
    )
    notes = [
        "Bonebound Alpha uses the WM shell-bank / mod-wm-spells lane; the old Twins command name is a compatibility alias.",
        "Do not bind this behavior to Summon Voidwalker, Raise Ghoul, or any other stock live spell carrier.",
        "Alpha receives the summoner's total intellect as all-stat bonus, shadow spell power as attack power, and native shadow/echo behavior.",
    ]
    if mode == "apply" and config_result.changed and not reload_via_soap:
        notes.append("Config changed on disk but worldserver has not reloaded it yet. Run .reload config or restart worldserver before casting.")
    if reload_via_soap:
        reload_result = execute_runtime_command(settings=settings, command=reload_command, mode=mode)
        config_result.reload_requested = True
        config_result.reload_result = reload_result.to_dict()
        if reload_result.notes:
            notes.extend(reload_result.notes)
    payload = config_result.to_dict()
    payload["notes"] = notes
    return payload


def configure_bonebound_servant_runtime(
    *,
    settings: Settings,
    player_guid: int,
    shell_spell_id: int,
    mode: str,
    config_path: Path | None = None,
    reload_via_soap: bool = False,
    reload_command: str = ".reload config",
) -> dict[str, Any]:
    config_result = update_wm_spells_runtime_config(
        config_path=config_path or Path(settings.wm_spells_config_path),
        player_guids=[int(player_guid)],
        shell_spell_ids=[int(shell_spell_id)],
        append_players=True,
        replace_shell_spell_ids=False,
        ensure_enabled=True,
        enable_debug_invoke=True,
        debug_poll_interval_ms=50,
        ensure_bonebound_enabled=True,
        write=(mode == "apply"),
    )
    notes = [
        "Bonebound Servant now uses the WM shell-bank / mod-wm-spells lane.",
        "This lane is isolated from stock live spell carriers.",
        "Lab-only debug invocation can exercise the same behavior implementation without teaching the player-facing shell.",
    ]
    if mode == "apply" and config_result.changed and not reload_via_soap:
        notes.append("Config changed on disk but worldserver has not reloaded it yet. Run .reload config or restart worldserver before casting.")
    if reload_via_soap:
        reload_result = execute_runtime_command(settings=settings, command=reload_command, mode=mode)
        config_result.reload_requested = True
        config_result.reload_result = reload_result.to_dict()
        if reload_result.notes:
            notes.extend(reload_result.notes)
    payload = config_result.to_dict()
    payload["notes"] = notes
    return payload


def execute_shell_behavior_debug_request(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    behavior_kind: str,
    payload: dict[str, Any],
    mode: str,
    timeout_seconds: float | None = None,
) -> WorkbenchRuntimeResult:
    if mode == "dry-run":
        return WorkbenchRuntimeResult(
            mode=mode,
            command=f"wm_spell_debug:{behavior_kind} player_guid={int(player_guid)}",
            ok=True,
            executed=False,
            notes=["Dry-run only; no wm_spell_debug_request row was inserted."],
        )
    debug_client = SpellBehaviorDebugClient(client=client, settings=settings)
    request = debug_client.submit(player_guid=int(player_guid), behavior_kind=behavior_kind, payload=payload)
    deadline = time.time() + (float(timeout_seconds) if timeout_seconds is not None else settings.native_bridge_action_wait_seconds)
    current = request
    while current.status not in {"done", "failed", "rejected", "expired"} and time.time() < deadline:
        time.sleep(max(settings.native_bridge_action_poll_seconds, 0.05))
        refreshed = debug_client.get(request_id=current.request_id)
        if refreshed is None:
            break
        current = refreshed
    ok = current.status == "done" and bool(current.result.get("ok", True))
    return WorkbenchRuntimeResult(
        mode=mode,
        command=f"wm_spell_debug:{behavior_kind} player_guid={int(player_guid)}",
        ok=ok,
        executed=True,
        result=json.dumps(current.to_dict(), ensure_ascii=False),
        fault_code=None if ok else current.status,
        fault_string=None if ok else current.error_text,
        notes=[f"debug_request_id={current.request_id}"],
    )


def resolve_shell_target(
    *,
    draft_json: Path | None = None,
    shell_key: str | None = None,
    spell_id: int | None = None,
) -> dict[str, Any]:
    if draft_json is not None:
        draft = load_shell_draft(draft_json)
        return {
            "shell_key": draft.shell_key,
            "spell_id": int(draft.spell_id),
            "label": draft.label,
            "behavior_kind": draft.behavior_kind,
        }
    bank = load_spell_shell_bank()
    if shell_key not in (None, ""):
        shell = bank.shell_by_key(str(shell_key))
        if shell is None:
            raise ValueError(f"Unknown shell key: {shell_key}")
        return {
            "shell_key": shell.shell_key,
            "spell_id": int(shell.spell_id),
            "label": shell.label,
            "behavior_kind": shell.behavior_kind,
        }
    if spell_id is None:
        raise ValueError("Provide --draft-json, --shell-key, or --spell-id.")
    shell = bank.shell_by_spell_id(int(spell_id))
    if shell is not None:
        return {
            "shell_key": shell.shell_key,
            "spell_id": int(shell.spell_id),
            "label": shell.label,
            "behavior_kind": shell.behavior_kind,
        }
    return {
        "shell_key": f"shell_{int(spell_id)}",
        "spell_id": int(spell_id),
        "label": f"Shell {int(spell_id)}",
        "behavior_kind": "",
    }


def describe_wm_spell_scope(*, spell_id: int) -> dict[str, Any] | None:
    shell = load_spell_shell_bank().shell_by_spell_id(int(spell_id))
    if shell is not None:
        return {
            "grant_scope": "spell_shell",
            "claim_key": shell.shell_key,
            "label": shell.label,
            "family_id": shell.family_id,
            "behavior_kind": shell.behavior_kind,
        }

    registry = load_custom_id_registry()
    claim = registry.claim_by_id(namespace="spell", id=int(spell_id))
    managed_range = registry.range_by_key(namespace="spell", range_key="managed_spell_slots")
    if claim is None and managed_range is not None and managed_range.start_id <= int(spell_id) <= managed_range.end_id:
        return {
            "grant_scope": "managed_spell_slot",
            "range_key": managed_range.range_key,
            "range_status": managed_range.status,
        }
    if claim is None:
        return None

    grant_scope = "wm_custom_spell"
    if managed_range is not None and managed_range.start_id <= claim.id <= managed_range.end_id:
        grant_scope = "managed_spell_slot"
    payload = {
        "grant_scope": grant_scope,
        "claim_key": claim.key,
        "claim_kind": claim.kind,
        "claim_status": claim.status,
        "owner_system": claim.owner_system,
    }
    if managed_range is not None and managed_range.start_id <= claim.id <= managed_range.end_id:
        payload["range_key"] = managed_range.range_key
    return payload


def build_managed_spell_grant_metadata(
    *,
    draft: ManagedSpellDraft,
    draft_path: Path | None,
    reserved_slot: dict[str, Any] | None,
    source_command: str,
    all_ranks: bool,
) -> dict[str, Any]:
    metadata = describe_wm_spell_scope(spell_id=draft.spell_entry) or {"grant_scope": "managed_spell_slot"}
    runtime_target = resolve_managed_spell_runtime_target(draft=draft)
    metadata.update(
        {
            "spell_entry": int(draft.spell_entry),
            "spell_name": str(draft.name),
            "slot_kind": str(draft.slot_kind),
            "source_command": str(source_command),
            "all_ranks": bool(all_ranks),
            "runtime_can_learn": bool(runtime_target.get("can_runtime_learn", False)),
            "runtime_spell_entry": _int_or_none(runtime_target.get("runtime_spell_entry")),
            "runtime_source": _str_or_none(runtime_target.get("runtime_source")),
        }
    )
    if draft_path is not None:
        metadata["draft_path"] = str(draft_path)
    if isinstance(reserved_slot, dict):
        metadata["reserved_slot"] = {
            "entity_type": _str_or_none(reserved_slot.get("entity_type")),
            "reserved_id": _int_or_none(reserved_slot.get("reserved_id")),
            "slot_status": _str_or_none(reserved_slot.get("slot_status")),
            "arc_key": _str_or_none(reserved_slot.get("arc_key")),
        }
    return metadata


def build_direct_spell_grant_metadata(
    *,
    spell_entry: int,
    source_command: str,
    all_ranks: bool,
) -> dict[str, Any] | None:
    metadata = describe_wm_spell_scope(spell_id=spell_entry)
    if metadata is None:
        return None
    metadata.update(
        {
            "spell_entry": int(spell_entry),
            "source_command": str(source_command),
            "all_ranks": bool(all_ranks),
        }
    )
    return metadata


def publish_result_allows_runtime(*, publish_result: dict[str, Any]) -> bool:
    validation_ok = bool(publish_result.get("validation", {}).get("ok", False))
    preflight_ok = bool(publish_result.get("preflight", {}).get("ok", False))
    if not validation_ok or not preflight_ok:
        return False
    if str(publish_result.get("mode") or "") == "apply":
        return bool(publish_result.get("applied", False))
    return True


def build_skipped_runtime_result(*, mode: str, command: str, reason: str) -> WorkbenchRuntimeResult:
    return WorkbenchRuntimeResult(
        mode=mode,
        command=command,
        ok=False,
        executed=False,
        fault_code="runtime_skipped",
        fault_string=reason,
        notes=[reason],
    )


def record_spell_grant_state(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    spell_id: int,
    grant_kind: str,
    author: str,
    metadata: dict[str, Any] | None = None,
    revoked: bool = False,
) -> dict[str, Any] | None:
    if not _world_table_exists(client=client, settings=settings, table_name="wm_spell_grant"):
        return None
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
    if revoked:
        client.query(
            host=settings.world_db_host,
            port=settings.world_db_port,
            user=settings.world_db_user,
            password=settings.world_db_password,
            database=settings.world_db_name,
            sql=(
                "UPDATE wm_spell_grant "
                "SET RevokedAt = CURRENT_TIMESTAMP, MetadataJSON = "
                f"{_sql_string(metadata_json)} "
                f"WHERE PlayerGUID = {int(player_guid)} AND ShellSpellID = {int(spell_id)} AND RevokedAt IS NULL"
            ),
        )
        return {
            "player_guid": int(player_guid),
            "spell_id": int(spell_id),
            "grant_kind": grant_kind,
            "revoked": True,
        }
    client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql=(
            "INSERT INTO wm_spell_grant (PlayerGUID, ShellSpellID, GrantKind, Author, MetadataJSON) VALUES ("
            f"{int(player_guid)}, {int(spell_id)}, {_sql_string(grant_kind)}, {_sql_string(author)}, {_sql_string(metadata_json)}"
            ")"
        ),
    )
    return {
        "player_guid": int(player_guid),
        "spell_id": int(spell_id),
        "grant_kind": grant_kind,
        "revoked": False,
    }


def record_shell_grant_state(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    spell_id: int,
    grant_kind: str,
    author: str,
    metadata: dict[str, Any] | None = None,
    revoked: bool = False,
) -> dict[str, Any] | None:
    return record_spell_grant_state(
        client=client,
        settings=settings,
        player_guid=player_guid,
        spell_id=spell_id,
        grant_kind=grant_kind,
        author=author,
        metadata=metadata,
        revoked=revoked,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    allocator = ReservedSlotDbAllocator(client=client, settings=settings)

    if args.command == "new-item":
        draft, slot = create_item_draft(
            allocator=allocator,
            name=args.name,
            base_item_entry=args.base_item_entry,
            player_guid=args.player_guid,
            description=args.description,
            quality=args.quality,
            item_level=args.item_level,
            required_level=args.required_level,
            stackable=args.stackable,
            max_count=args.max_count,
        )
        path = write_draft_file(
            kind="item",
            template="managed_item",
            draft=draft,
            slot=slot,
            out_path=args.out,
        )
        return _print_draft_summary(kind="item", draft=draft.to_dict(), slot=slot, path=path)

    if args.command == "new-passive":
        draft, slot = create_passive_draft(
            allocator=allocator,
            name=args.name,
            player_guid=args.player_guid,
            helper_spell_id=args.helper_spell_id,
            aura_description=args.aura_description,
        )
        path = write_draft_file(
            kind="spell",
            template="passive_slot",
            draft=draft,
            slot=slot,
            out_path=args.out,
        )
        return _print_draft_summary(kind="spell", draft=draft.to_dict(), slot=slot, path=path)

    if args.command == "new-trigger-spell":
        draft, slot = create_trigger_spell_draft(
            allocator=allocator,
            name=args.name,
            trigger_item_entry=args.trigger_item_entry,
            player_guid=args.player_guid,
            helper_spell_id=args.helper_spell_id,
            aura_description=args.aura_description,
        )
        path = write_draft_file(
            kind="spell",
            template="item_trigger_slot",
            draft=draft,
            slot=slot,
            out_path=args.out,
        )
        return _print_draft_summary(kind="spell", draft=draft.to_dict(), slot=slot, path=path)

    if args.command == "new-visible-spell":
        draft, slot = create_visible_spell_draft(
            allocator=allocator,
            name=args.name,
            base_visible_spell_id=args.base_visible_spell_id,
            player_guid=args.player_guid,
            helper_spell_id=args.helper_spell_id,
            aura_description=args.aura_description,
        )
        path = write_draft_file(
            kind="spell",
            template="visible_spell_slot",
            draft=draft,
            slot=slot,
            out_path=args.out,
        )
        return _print_draft_summary(kind="spell", draft=draft.to_dict(), slot=slot, path=path)

    if args.command == "new-summon-shell":
        behavior_overrides: dict[str, Any] | None = None
        if args.behavior_config_json is not None:
            behavior_overrides = json.loads(args.behavior_config_json.read_text(encoding="utf-8"))
            if not isinstance(behavior_overrides, dict):
                raise ValueError("--behavior-config-json must contain a JSON object.")
        draft = create_shell_draft(
            shell_key=args.shell_key,
            ownership_key=args.ownership_key,
            player_guid=args.player_guid,
            behavior_config=behavior_overrides,
        )
        path = write_shell_draft_file(draft=draft, out_path=args.out)
        return _print_draft_summary(
            kind="shell",
            draft=draft.to_dict(),
            slot=ReservedSlot(
                entity_type="spell_shell",
                reserved_id=int(draft.spell_id),
                slot_status="staged",
                arc_key=draft.ownership_key,
            ),
            path=path,
        )

    if args.command == "publish-item":
        draft = load_managed_item_draft(args.draft_json)
        slot = _load_reserved_slot(args.draft_json)
        if args.mode == "apply":
            _prepare_slot(
                allocator=allocator,
                entity_type="item",
                reserved_id=int(draft.item_entry),
                slot=slot,
            )
        publish_result = ItemPublisher(client=client, settings=settings).publish(draft=draft, mode=args.mode)
        runtime_result = None
        if args.give_to_player_guid is not None or args.give_to_player_name not in (None, ""):
            player_ref = _resolve_player_reference(
                client=client,
                settings=settings,
                player_guid=args.give_to_player_guid,
                player_name=args.give_to_player_name,
            )
            wait_notes: list[str] = []
            player_ref, wait_notes = _maybe_wait_for_player_online(
                client=client,
                settings=settings,
                player_ref=player_ref,
                player_guid=args.give_to_player_guid,
                player_name=args.give_to_player_name,
                mode=args.mode,
                wait_for_player_online=bool(args.wait_for_player_online),
                wait_timeout_seconds=args.wait_timeout_seconds,
                wait_poll_seconds=args.wait_poll_seconds,
            )
            runtime_result = execute_item_delivery_command(
                settings=settings,
                player_ref=player_ref,
                item_entry=draft.item_entry,
                count=args.count,
                delivery=args.delivery,
                mail_subject=args.mail_subject,
                mail_body=args.mail_body,
                mode=args.mode,
            )
            if wait_notes:
                runtime_result.notes = wait_notes + list(runtime_result.notes or [])
        return _print_publish_summary(
            publish_result=publish_result.to_dict(),
            runtime_result=None if runtime_result is None else runtime_result.to_dict(),
            grant_record=None,
            output_json=args.output_json,
        )

    if args.command == "publish-shell":
        draft = load_shell_draft(args.draft_json)
        publish_result = SpellPlatformPublisher(client=client, settings=settings).publish(draft=draft, mode=args.mode)
        return _print_publish_summary(
            publish_result=publish_result.to_dict(),
            runtime_result=None,
            grant_record=None,
            output_json=args.output_json,
        )

    if args.command == "publish-spell":
        draft = load_managed_spell_draft(args.draft_json)
        slot = _load_reserved_slot(args.draft_json)
        runtime_target = resolve_managed_spell_runtime_target(draft=draft)
        if args.mode == "apply":
            _prepare_slot(
                allocator=allocator,
                entity_type="spell",
                reserved_id=int(draft.spell_entry),
                slot=slot,
            )
        publish_result = SpellPublisher(client=client, settings=settings).publish(draft=draft, mode=args.mode)
        publish_payload = publish_result.to_dict()
        runtime_result = None
        grant_record = None
        if args.learn_to_player_guid is not None or args.learn_to_player_name not in (None, ""):
            if publish_result_allows_runtime(publish_result=publish_payload):
                if not bool(runtime_target.get("can_runtime_learn", False)):
                    runtime_result = build_skipped_runtime_result(
                        mode=args.mode,
                        command=f"managed_spell_runtime spell_entry={int(draft.spell_entry)}",
                        reason=str(runtime_target.get("reason") or "Managed spell draft does not expose a learnable runtime spell identity."),
                    )
                else:
                    player_ref = _resolve_player_reference(
                        client=client,
                        settings=settings,
                        player_guid=args.learn_to_player_guid,
                        player_name=args.learn_to_player_name,
                    )
                    wait_notes: list[str] = []
                    player_ref, wait_notes = _maybe_wait_for_player_online(
                        client=client,
                        settings=settings,
                        player_ref=player_ref,
                        player_guid=args.learn_to_player_guid,
                        player_name=args.learn_to_player_name,
                        mode=args.mode,
                        wait_for_player_online=bool(args.wait_for_player_online),
                        wait_timeout_seconds=args.wait_timeout_seconds,
                        wait_poll_seconds=args.wait_poll_seconds,
                    )
                    runtime_result = execute_spell_runtime_action(
                        client=client,
                        settings=settings,
                        player_ref=player_ref,
                        spell_entry=int(runtime_target["runtime_spell_entry"]),
                        action_kind="player_learn_spell",
                        all_ranks=bool(args.all_ranks),
                        mode=args.mode,
                    )
                    runtime_notes = list(runtime_result.notes or [])
                    runtime_notes.append(
                        f"Managed spell slot {int(draft.spell_entry)} used runtime spell {int(runtime_target['runtime_spell_entry'])} via {runtime_target.get('runtime_source')}."
                    )
                    runtime_result.notes = runtime_notes
                    if wait_notes:
                        runtime_result.notes = wait_notes + list(runtime_result.notes or [])
                    if args.mode == "apply" and runtime_result.ok:
                        grant_record = record_spell_grant_state(
                            client=client,
                            settings=settings,
                            player_guid=int(player_ref["player_guid"]),
                            spell_id=int(draft.spell_entry),
                            grant_kind="managed_spell_slot_grant",
                            author="wm.content.workbench",
                            metadata=build_managed_spell_grant_metadata(
                                draft=draft,
                                draft_path=args.draft_json,
                                reserved_slot=slot,
                                source_command="publish-spell",
                                all_ranks=bool(args.all_ranks),
                            ),
                        )
            else:
                runtime_result = build_skipped_runtime_result(
                    mode=args.mode,
                    command=f"native:player_learn_spell spell_id={int(draft.spell_entry)}",
                    reason="Skipped runtime learn because spell publish validation, preflight, or apply did not succeed.",
                )
        return _print_publish_summary(
            publish_result=publish_payload,
            runtime_result=None if runtime_result is None else runtime_result.to_dict(),
            grant_record=grant_record,
            output_json=args.output_json,
        )

    if args.command == "give-item":
        player_ref = _resolve_player_reference(
            client=client,
            settings=settings,
            player_guid=args.player_guid,
            player_name=args.player_name,
        )
        wait_notes: list[str] = []
        player_ref, wait_notes = _maybe_wait_for_player_online(
            client=client,
            settings=settings,
            player_ref=player_ref,
            player_guid=args.player_guid,
            player_name=args.player_name,
            mode=args.mode,
            wait_for_player_online=bool(args.wait_for_player_online),
            wait_timeout_seconds=args.wait_timeout_seconds,
            wait_poll_seconds=args.wait_poll_seconds,
        )
        runtime_result = execute_item_delivery_command(
            settings=settings,
            player_ref=player_ref,
            item_entry=args.item_entry,
            count=args.count,
            delivery=args.delivery,
            mail_subject=args.mail_subject,
            mail_body=args.mail_body,
            mode=args.mode,
        )
        if wait_notes:
            runtime_result.notes = wait_notes + list(runtime_result.notes or [])
        return _print_runtime_summary(runtime_result, output_json=args.output_json)

    if args.command == "learn-spell":
        player_ref = _resolve_player_reference(
            client=client,
            settings=settings,
            player_guid=args.player_guid,
            player_name=args.player_name,
        )
        wait_notes: list[str] = []
        player_ref, wait_notes = _maybe_wait_for_player_online(
            client=client,
            settings=settings,
            player_ref=player_ref,
            player_guid=args.player_guid,
            player_name=args.player_name,
            mode=args.mode,
            wait_for_player_online=bool(args.wait_for_player_online),
            wait_timeout_seconds=args.wait_timeout_seconds,
            wait_poll_seconds=args.wait_poll_seconds,
        )
        runtime_result = execute_spell_runtime_action(
            client=client,
            settings=settings,
            player_ref=player_ref,
            spell_entry=args.spell_entry,
            action_kind="player_learn_spell",
            all_ranks=bool(args.all_ranks),
            mode=args.mode,
        )
        if wait_notes:
            runtime_result.notes = wait_notes + list(runtime_result.notes or [])
        grant_record = None
        if args.mode == "apply" and runtime_result.ok:
            metadata = build_direct_spell_grant_metadata(
                spell_entry=int(args.spell_entry),
                source_command="learn-spell",
                all_ranks=bool(args.all_ranks),
            )
            if metadata is not None:
                grant_record = record_spell_grant_state(
                    client=client,
                    settings=settings,
                    player_guid=int(player_ref["player_guid"]),
                    spell_id=int(args.spell_entry),
                    grant_kind="manual_wm_spell_grant",
                    author="wm.content.workbench",
                    metadata=metadata,
                )
        return _print_runtime_summary(runtime_result, grant_record=grant_record, output_json=args.output_json)

    if args.command == "unlearn-spell":
        player_ref = _resolve_player_reference(
            client=client,
            settings=settings,
            player_guid=args.player_guid,
            player_name=args.player_name,
        )
        wait_notes: list[str] = []
        player_ref, wait_notes = _maybe_wait_for_player_online(
            client=client,
            settings=settings,
            player_ref=player_ref,
            player_guid=args.player_guid,
            player_name=args.player_name,
            mode=args.mode,
            wait_for_player_online=bool(args.wait_for_player_online),
            wait_timeout_seconds=args.wait_timeout_seconds,
            wait_poll_seconds=args.wait_poll_seconds,
        )
        runtime_result = execute_spell_runtime_action(
            client=client,
            settings=settings,
            player_ref=player_ref,
            spell_entry=args.spell_entry,
            action_kind="player_unlearn_spell",
            all_ranks=bool(args.all_ranks),
            mode=args.mode,
        )
        if wait_notes:
            runtime_result.notes = wait_notes + list(runtime_result.notes or [])
        grant_record = None
        if args.mode == "apply" and runtime_result.ok:
            metadata = build_direct_spell_grant_metadata(
                spell_entry=int(args.spell_entry),
                source_command="unlearn-spell",
                all_ranks=bool(args.all_ranks),
            )
            if metadata is not None:
                grant_record = record_spell_grant_state(
                    client=client,
                    settings=settings,
                    player_guid=int(player_ref["player_guid"]),
                    spell_id=int(args.spell_entry),
                    grant_kind="manual_wm_spell_revoke",
                    author="wm.content.workbench",
                    metadata=metadata,
                    revoked=True,
                )
        return _print_runtime_summary(runtime_result, grant_record=grant_record, output_json=args.output_json)

    if args.command == "grant-shell":
        player_ref = _resolve_player_reference(
            client=client,
            settings=settings,
            player_guid=args.player_guid,
            player_name=args.player_name,
        )
        wait_notes: list[str] = []
        player_ref, wait_notes = _maybe_wait_for_player_online(
            client=client,
            settings=settings,
            player_ref=player_ref,
            player_guid=args.player_guid,
            player_name=args.player_name,
            mode=args.mode,
            wait_for_player_online=bool(args.wait_for_player_online),
            wait_timeout_seconds=args.wait_timeout_seconds,
            wait_poll_seconds=args.wait_poll_seconds,
        )
        shell_target = resolve_shell_target(draft_json=args.draft_json, shell_key=args.shell_key, spell_id=args.spell_id)
        config_result = configure_bonebound_servant_runtime(
            settings=settings,
            player_guid=int(player_ref["player_guid"]),
            shell_spell_id=int(shell_target["spell_id"]),
            mode=args.mode,
            config_path=args.config_path,
            reload_via_soap=bool(args.reload_via_soap),
            reload_command=str(args.reload_command),
        )
        runtime_result = execute_spell_runtime_action(
            client=client,
            settings=settings,
            player_ref=player_ref,
            spell_entry=int(shell_target["spell_id"]),
            action_kind="player_learn_spell",
            mode=args.mode,
            created_by="wm_spell_shell_grant",
        )
        if wait_notes:
            runtime_result.notes = wait_notes + list(runtime_result.notes or [])
        grant_record = None
        if args.mode == "apply" and runtime_result.ok:
            grant_record = record_spell_grant_state(
                client=client,
                settings=settings,
                player_guid=int(player_ref["player_guid"]),
                spell_id=int(shell_target["spell_id"]),
                grant_kind=str(args.grant_kind),
                author="wm.content.workbench",
                metadata={
                    "shell_key": shell_target["shell_key"],
                    "label": shell_target["label"],
                    "behavior_kind": shell_target["behavior_kind"],
                },
            )
        return _print_shell_grant_summary(
            player_ref=player_ref,
            shell_target=shell_target,
            config_result=config_result,
            runtime_result=runtime_result,
            grant_record=grant_record,
            output_json=args.output_json,
        )

    if args.command == "ungrant-shell":
        player_ref = _resolve_player_reference(
            client=client,
            settings=settings,
            player_guid=args.player_guid,
            player_name=args.player_name,
        )
        wait_notes: list[str] = []
        player_ref, wait_notes = _maybe_wait_for_player_online(
            client=client,
            settings=settings,
            player_ref=player_ref,
            player_guid=args.player_guid,
            player_name=args.player_name,
            mode=args.mode,
            wait_for_player_online=bool(args.wait_for_player_online),
            wait_timeout_seconds=args.wait_timeout_seconds,
            wait_poll_seconds=args.wait_poll_seconds,
        )
        shell_target = resolve_shell_target(draft_json=args.draft_json, shell_key=args.shell_key, spell_id=args.spell_id)
        runtime_result = execute_spell_runtime_action(
            client=client,
            settings=settings,
            player_ref=player_ref,
            spell_entry=int(shell_target["spell_id"]),
            action_kind="player_unlearn_spell",
            mode=args.mode,
            created_by="wm_spell_shell_revoke",
        )
        if wait_notes:
            runtime_result.notes = wait_notes + list(runtime_result.notes or [])
        grant_record = None
        if args.mode == "apply" and runtime_result.ok:
            grant_record = record_spell_grant_state(
                client=client,
                settings=settings,
                player_guid=int(player_ref["player_guid"]),
                spell_id=int(shell_target["spell_id"]),
                grant_kind="manual_shell_revoke",
                author="wm.content.workbench",
                metadata={"shell_key": shell_target["shell_key"], "label": shell_target["label"]},
                revoked=True,
            )
        return _print_shell_grant_summary(
            player_ref=player_ref,
            shell_target=shell_target,
            config_result=None,
            runtime_result=runtime_result,
            grant_record=grant_record,
            output_json=args.output_json,
        )

    if args.command == "invoke-shell-behavior":
        player_ref = _resolve_player_reference(
            client=client,
            settings=settings,
            player_guid=args.player_guid,
            player_name=args.player_name,
        )
        wait_notes: list[str] = []
        player_ref, wait_notes = _maybe_wait_for_player_online(
            client=client,
            settings=settings,
            player_ref=player_ref,
            player_guid=args.player_guid,
            player_name=args.player_name,
            mode=args.mode,
            wait_for_player_online=bool(args.wait_for_player_online),
            wait_timeout_seconds=args.wait_timeout_seconds,
            wait_poll_seconds=args.wait_poll_seconds,
        )
        shell_target = resolve_shell_target(draft_json=args.draft_json, shell_key=args.shell_key, spell_id=args.spell_id)
        payload: dict[str, Any] = {"shell_spell_id": int(shell_target["spell_id"])}
        if args.payload_json is not None:
            raw_payload = json.loads(args.payload_json.read_text(encoding="utf-8"))
            if not isinstance(raw_payload, dict):
                raise ValueError("--payload-json must contain a JSON object.")
            payload.update(raw_payload)
        runtime_result = execute_shell_behavior_debug_request(
            client=client,
            settings=settings,
            player_guid=int(player_ref["player_guid"]),
            behavior_kind=args.behavior_kind or str(shell_target["behavior_kind"]),
            payload=payload,
            mode=args.mode,
            timeout_seconds=args.timeout_seconds,
        )
        if wait_notes:
            runtime_result.notes = wait_notes + list(runtime_result.notes or [])
        return _print_runtime_summary(runtime_result, output_json=args.output_json)

    if args.command == "learn-twin-skeleton":
        player_ref = _resolve_player_reference(
            client=client,
            settings=settings,
            player_guid=args.player_guid,
            player_name=args.player_name,
        )
        wait_notes: list[str] = []
        player_ref, wait_notes = _maybe_wait_for_player_online(
            client=client,
            settings=settings,
            player_ref=player_ref,
            player_guid=args.player_guid,
            player_name=args.player_name,
            mode=args.mode,
            wait_for_player_online=bool(args.wait_for_player_online),
            wait_timeout_seconds=args.wait_timeout_seconds,
            wait_poll_seconds=args.wait_poll_seconds,
        )
        config_result = configure_twin_skeleton_runtime(
            settings=settings,
            player_guid=int(player_ref["player_guid"]),
            shell_spell_id=args.shell_spell_id,
            mode=args.mode,
            config_path=args.config_path,
            reload_via_soap=bool(args.reload_via_soap),
            reload_command=str(args.reload_command),
        )
        command = build_player_learn_command(
            player_name=str(player_ref["player_name"]),
            spell_entry=args.shell_spell_id,
            all_ranks=bool(args.all_ranks),
        )
        runtime_result = execute_runtime_command(settings=settings, command=command, mode=args.mode)
        if wait_notes:
            runtime_result.notes = wait_notes + list(runtime_result.notes or [])
        return _print_twin_skeleton_summary(
            player_ref=player_ref,
            shell_spell_id=args.shell_spell_id,
            config_result=config_result,
            runtime_result=runtime_result,
            output_json=args.output_json,
        )

    raise SystemExit(f"Unsupported command: {args.command}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.content.workbench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_item = subparsers.add_parser("new-item", help="Allocate a managed item slot and write a draft JSON.")
    new_item.add_argument("--name", required=True)
    new_item.add_argument("--base-item-entry", type=int, default=6948)
    new_item.add_argument("--player-guid", type=int)
    new_item.add_argument("--description")
    new_item.add_argument("--quality", type=int, default=2)
    new_item.add_argument("--item-level", type=int, default=10)
    new_item.add_argument("--required-level", type=int, default=1)
    new_item.add_argument("--stackable", type=int, default=1)
    new_item.add_argument("--max-count", type=int, default=1)
    new_item.add_argument("--out", type=Path)

    new_passive = subparsers.add_parser("new-passive", help="Allocate a managed passive spell slot draft JSON.")
    new_passive.add_argument("--name", required=True)
    new_passive.add_argument("--player-guid", type=int)
    new_passive.add_argument("--helper-spell-id", type=int)
    new_passive.add_argument("--aura-description")
    new_passive.add_argument("--out", type=Path)

    new_trigger = subparsers.add_parser("new-trigger-spell", help="Allocate a managed item-trigger spell slot draft JSON.")
    new_trigger.add_argument("--name", required=True)
    new_trigger.add_argument("--trigger-item-entry", type=int, required=True)
    new_trigger.add_argument("--player-guid", type=int)
    new_trigger.add_argument("--helper-spell-id", type=int)
    new_trigger.add_argument("--aura-description")
    new_trigger.add_argument("--out", type=Path)

    new_visible = subparsers.add_parser("new-visible-spell", help="Allocate a managed visible spell slot draft JSON.")
    new_visible.add_argument("--name", required=True)
    new_visible.add_argument("--base-visible-spell-id", type=int, required=True)
    new_visible.add_argument("--player-guid", type=int)
    new_visible.add_argument("--helper-spell-id", type=int)
    new_visible.add_argument("--aura-description")
    new_visible.add_argument("--out", type=Path)

    new_shell = subparsers.add_parser("new-summon-shell", help="Write a WM shell-bank summon draft JSON.")
    new_shell.add_argument("--shell-key", default="bonebound_servant_v1")
    new_shell.add_argument("--player-guid", type=int)
    new_shell.add_argument("--ownership-key")
    new_shell.add_argument("--behavior-config-json", type=Path)
    new_shell.add_argument("--out", type=Path)

    publish_item = subparsers.add_parser("publish-item", help="Publish a managed item draft and optionally give it to a player.")
    publish_item.add_argument("--draft-json", type=Path, required=True)
    publish_item.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    publish_item.add_argument("--give-to-player-guid", type=int)
    publish_item.add_argument("--give-to-player-name")
    publish_item.add_argument("--delivery", choices=["auto", "additem", "mail"], default="auto")
    publish_item.add_argument("--count", type=int, default=1)
    publish_item.add_argument("--mail-subject", default="WM Content")
    publish_item.add_argument("--mail-body", default="Prototype item delivery.")
    _add_wait_for_player_online_args(publish_item)
    publish_item.add_argument("--output-json", type=Path)

    publish_spell = subparsers.add_parser("publish-spell", help="Publish a managed spell draft and optionally learn it on a player.")
    publish_spell.add_argument("--draft-json", type=Path, required=True)
    publish_spell.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    publish_spell.add_argument("--learn-to-player-guid", type=int)
    publish_spell.add_argument("--learn-to-player-name")
    publish_spell.add_argument("--all-ranks", action="store_true")
    _add_wait_for_player_online_args(publish_spell)
    publish_spell.add_argument("--output-json", type=Path)

    publish_shell = subparsers.add_parser("publish-shell", help="Publish a WM spell shell draft into wm_spell_shell / wm_spell_behavior.")
    publish_shell.add_argument("--draft-json", type=Path, required=True)
    publish_shell.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    publish_shell.add_argument("--output-json", type=Path)

    give_item = subparsers.add_parser("give-item", help="Give an item directly to a player over SOAP.")
    give_item.add_argument("--item-entry", type=int, required=True)
    give_item.add_argument("--count", type=int, default=1)
    give_item.add_argument("--player-guid", type=int)
    give_item.add_argument("--player-name")
    give_item.add_argument("--delivery", choices=["auto", "additem", "mail"], default="auto")
    give_item.add_argument("--mail-subject", default="WM Content")
    give_item.add_argument("--mail-body", default="Prototype item delivery.")
    give_item.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    _add_wait_for_player_online_args(give_item)
    give_item.add_argument("--output-json", type=Path)

    learn_spell = subparsers.add_parser("learn-spell", help="Teach a spell directly to a player over SOAP.")
    learn_spell.add_argument("--spell-entry", type=int, required=True)
    learn_spell.add_argument("--player-guid", type=int)
    learn_spell.add_argument("--player-name")
    learn_spell.add_argument("--all-ranks", action="store_true")
    learn_spell.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    _add_wait_for_player_online_args(learn_spell)
    learn_spell.add_argument("--output-json", type=Path)

    unlearn_spell = subparsers.add_parser("unlearn-spell", help="Remove a spell directly from a player over SOAP.")
    unlearn_spell.add_argument("--spell-entry", type=int, required=True)
    unlearn_spell.add_argument("--player-guid", type=int)
    unlearn_spell.add_argument("--player-name")
    unlearn_spell.add_argument("--all-ranks", action="store_true")
    unlearn_spell.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    _add_wait_for_player_online_args(unlearn_spell)
    unlearn_spell.add_argument("--output-json", type=Path)

    grant_shell = subparsers.add_parser("grant-shell", help="Scope the WM spell module for a player and learn a WM shell spell.")
    grant_shell.add_argument("--draft-json", type=Path)
    grant_shell.add_argument("--shell-key")
    grant_shell.add_argument("--spell-id", type=int)
    grant_shell.add_argument("--player-guid", type=int)
    grant_shell.add_argument("--player-name")
    grant_shell.add_argument("--grant-kind", default="manual_shell_grant")
    grant_shell.add_argument("--config-path", type=Path)
    grant_shell.add_argument("--reload-via-soap", action="store_true")
    grant_shell.add_argument("--reload-command", default=".reload config")
    grant_shell.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    _add_wait_for_player_online_args(grant_shell)
    grant_shell.add_argument("--output-json", type=Path)

    ungrant_shell = subparsers.add_parser("ungrant-shell", help="Remove a WM shell spell from a player.")
    ungrant_shell.add_argument("--draft-json", type=Path)
    ungrant_shell.add_argument("--shell-key")
    ungrant_shell.add_argument("--spell-id", type=int)
    ungrant_shell.add_argument("--player-guid", type=int)
    ungrant_shell.add_argument("--player-name")
    ungrant_shell.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    _add_wait_for_player_online_args(ungrant_shell)
    ungrant_shell.add_argument("--output-json", type=Path)

    invoke_shell = subparsers.add_parser("invoke-shell-behavior", help="Invoke a WM spell behavior through the lab-only debug lane.")
    invoke_shell.add_argument("--draft-json", type=Path)
    invoke_shell.add_argument("--shell-key")
    invoke_shell.add_argument("--spell-id", type=int)
    invoke_shell.add_argument("--behavior-kind")
    invoke_shell.add_argument("--payload-json", type=Path)
    invoke_shell.add_argument("--player-guid", type=int)
    invoke_shell.add_argument("--player-name")
    invoke_shell.add_argument("--timeout-seconds", type=float)
    invoke_shell.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    _add_wait_for_player_online_args(invoke_shell)
    invoke_shell.add_argument("--output-json", type=Path)

    learn_twin_skeleton = subparsers.add_parser(
        "learn-twin-skeleton",
        help="Configure the WM-owned Bonebound Alpha shell and optionally teach that shell; command name is a legacy alias.",
    )
    learn_twin_skeleton.add_argument("--player-guid", type=int)
    learn_twin_skeleton.add_argument("--player-name")
    learn_twin_skeleton.add_argument("--shell-spell-id", type=int, default=940001)
    learn_twin_skeleton.add_argument("--all-ranks", action="store_true")
    learn_twin_skeleton.add_argument("--config-path", type=Path)
    learn_twin_skeleton.add_argument("--reload-via-soap", action="store_true")
    learn_twin_skeleton.add_argument("--reload-command", default=".reload config")
    learn_twin_skeleton.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    _add_wait_for_player_online_args(learn_twin_skeleton)
    learn_twin_skeleton.add_argument("--output-json", type=Path)

    return parser


def _load_reserved_slot(path: Path) -> dict[str, Any] | None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("reserved_slot"), dict):
        return dict(raw["reserved_slot"])
    return None


def _prepare_slot(
    *,
    allocator: ReservedSlotDbAllocator,
    entity_type: str,
    reserved_id: int,
    slot: dict[str, Any] | None,
) -> None:
    allocator.ensure_slot_prepared(
        entity_type=entity_type,
        reserved_id=int(reserved_id),
        arc_key=_str_or_none(slot.get("arc_key")) if isinstance(slot, dict) else None,
        character_guid=_int_or_none(slot.get("character_guid")) if isinstance(slot, dict) else None,
        source_quest_id=_int_or_none(slot.get("source_quest_id")) if isinstance(slot, dict) else None,
        notes=[str(note) for note in slot.get("notes", [])] if isinstance(slot, dict) and isinstance(slot.get("notes"), list) else None,
    )


def _resolve_player_reference(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int | None,
    player_name: str | None,
) -> dict[str, Any]:
    if player_guid not in (None, 0) and player_name not in (None, "") and client is None and settings is None:
        return {
            "player_guid": int(player_guid),
            "player_name": str(player_name),
            "command_player": str(player_name),
        }
    if player_guid in (None, 0) and player_name in (None, ""):
        raise ValueError("Provide --player-name or --player-guid.")

    sql: str
    if player_guid not in (None, 0):
        sql = f"SELECT guid, name, online FROM characters WHERE guid = {int(player_guid)} LIMIT 1"
    else:
        sql = f"SELECT guid, name, online FROM characters WHERE name = {_sql_string(str(player_name))} LIMIT 1"

    rows = client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=sql,
    )
    if not rows:
        if player_guid not in (None, 0):
            raise ValueError(f"Could not resolve player GUID {int(player_guid)} in characters DB.")
        raise ValueError(f"Could not resolve player name `{player_name}` in characters DB.")
    resolved_name = str(rows[0]["name"])
    resolved_guid = int(rows[0]["guid"])
    online = bool(int(rows[0]["online"] or 0))
    command_player = str(player_name) if player_name not in (None, "") else str(resolved_guid)
    return {
        "player_guid": resolved_guid,
        "player_name": resolved_name,
        "command_player": command_player,
        "online": online,
    }


def _maybe_wait_for_player_online(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_ref: dict[str, Any],
    player_guid: int | None,
    player_name: str | None,
    mode: str,
    wait_for_player_online: bool,
    wait_timeout_seconds: float,
    wait_poll_seconds: float,
) -> tuple[dict[str, Any], list[str]]:
    if mode != "apply" or not wait_for_player_online:
        return player_ref, []
    if bool(player_ref.get("online", False)):
        return player_ref, [f"player_online=true player={player_ref.get('player_name')}"]
    return _wait_for_player_online(
        client=client,
        settings=settings,
        player_guid=player_guid if player_guid not in (None, 0) else _int_or_none(player_ref.get("player_guid")),
        player_name=player_name if player_name not in (None, "") else _str_or_none(player_ref.get("player_name")),
        timeout_seconds=wait_timeout_seconds,
        poll_seconds=wait_poll_seconds,
    )


def _wait_for_player_online(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int | None,
    player_name: str | None,
    timeout_seconds: float,
    poll_seconds: float,
) -> tuple[dict[str, Any], list[str]]:
    deadline = time.time() + max(float(timeout_seconds), 1.0)
    interval = max(float(poll_seconds), 0.2)
    while True:
        player_ref = _resolve_player_reference(
            client=client,
            settings=settings,
            player_guid=player_guid,
            player_name=player_name,
        )
        if bool(player_ref.get("online", False)):
            return player_ref, [
                f"waited_for_player_online=true player={player_ref.get('player_name')}",
                f"player_guid={player_ref.get('player_guid')}",
            ]
        if time.time() >= deadline:
            raise ValueError(
                f"Timed out waiting for player `{player_ref.get('player_name')}` ({player_ref.get('player_guid')}) to come online."
            )
        time.sleep(interval)


def _add_wait_for_player_online_args(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--wait-for-player-online", action="store_true")
    subparser.add_argument("--wait-timeout-seconds", type=float, default=600.0)
    subparser.add_argument("--wait-poll-seconds", type=float, default=2.0)


def _default_draft_path(*, kind: str, reserved_id: int, name: str) -> Path:
    slug = _slugify(name) or kind
    return _default_draft_root().joinpath(f"{kind}-{int(reserved_id)}-{slug}.json")


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", str(value).strip().lower()).strip("-")
    return text[:48]


def _print_draft_summary(*, kind: str, draft: dict[str, Any], slot: ReservedSlot, path: Path) -> int:
    print(f"kind={kind} reserved_id={slot.reserved_id} slot_status={slot.slot_status} path={path}")
    print(f"name={draft.get('name')} arc_key={slot.arc_key}")
    return 0


def _print_publish_summary(
    *,
    publish_result: dict[str, Any],
    runtime_result: dict[str, Any] | None,
    grant_record: dict[str, Any] | None,
    output_json: Path | None,
) -> int:
    payload = {"publish": publish_result, "runtime_test": runtime_result, "grant_record": grant_record}
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    mode = str(publish_result.get("mode") or "dry-run")
    validation_ok = bool(publish_result.get("validation", {}).get("ok", False))
    preflight_ok = bool(publish_result.get("preflight", {}).get("ok", False))
    applied = bool(publish_result.get("applied", False))
    print(
        f"publish_applied={str(applied).lower()} validation_ok={str(validation_ok).lower()} "
        f"preflight_ok={str(preflight_ok).lower()}"
    )
    if runtime_result is not None:
        print(
            f"runtime_ok={str(bool(runtime_result.get('ok', False))).lower()} "
            f"executed={str(bool(runtime_result.get('executed', False))).lower()} "
            f"command={runtime_result.get('command')}"
        )
        for note in runtime_result.get("notes", []) or []:
            print(f"note={note}")
    if grant_record is not None:
        print(f"grant_recorded=true revoked={str(bool(grant_record.get('revoked', False))).lower()}")
    if output_json is not None:
        print(f"output_json={output_json}")
    success = validation_ok and preflight_ok and (runtime_result is None or bool(runtime_result.get("ok", False)))
    if mode == "apply":
        success = success and applied
    return 0 if success else 1


def _print_runtime_summary(
    result: WorkbenchRuntimeResult,
    *,
    grant_record: dict[str, Any] | None = None,
    output_json: Path | None,
) -> int:
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps({"runtime_test": result.to_dict(), "grant_record": grant_record}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    print(
        f"mode={result.mode} ok={str(bool(result.ok)).lower()} executed={str(bool(result.executed)).lower()} "
        f"command={result.command}"
    )
    if result.fault_string not in (None, ""):
        print(f"fault={result.fault_string}")
    for note in result.notes or []:
        print(f"note={note}")
    if grant_record is not None:
        print(f"grant_recorded=true revoked={str(bool(grant_record.get('revoked', False))).lower()}")
    if output_json is not None:
        print(f"output_json={output_json}")
    return 0 if result.ok else 1


def _print_twin_skeleton_summary(
    *,
    player_ref: dict[str, Any],
    shell_spell_id: int,
    config_result: dict[str, Any],
    runtime_result: WorkbenchRuntimeResult,
    output_json: Path | None,
) -> int:
    payload = {
        "prototype": "twin_skeleton",
        "player": player_ref,
        "shell_spell_id": int(shell_spell_id),
        "config_update": config_result,
        "runtime_test": runtime_result.to_dict(),
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    reload_result = config_result.get("reload_result") if isinstance(config_result, dict) else None
    reload_ok = True
    if isinstance(reload_result, dict):
        reload_ok = bool(reload_result.get("ok", False))
    print(
        f"prototype=twin_skeleton player={player_ref.get('player_name')} shell_spell_id={int(shell_spell_id)} "
        f"config_changed={str(bool(config_result.get('changed', False))).lower()} "
        f"learn_ok={str(bool(runtime_result.ok)).lower()} reload_ok={str(bool(reload_ok)).lower()}"
    )
    if output_json is not None:
        print(f"output_json={output_json}")
    return 0 if runtime_result.ok and reload_ok else 1


def _print_shell_grant_summary(
    *,
    player_ref: dict[str, Any],
    shell_target: dict[str, Any],
    config_result: dict[str, Any] | None,
    runtime_result: WorkbenchRuntimeResult,
    grant_record: dict[str, Any] | None,
    output_json: Path | None,
) -> int:
    payload = {
        "player": player_ref,
        "shell": shell_target,
        "config_update": config_result,
        "runtime_test": runtime_result.to_dict(),
        "grant_record": grant_record,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    reload_ok = True
    if isinstance(config_result, dict) and isinstance(config_result.get("reload_result"), dict):
        reload_ok = bool(config_result["reload_result"].get("ok", False))
    print(
        f"player={player_ref.get('player_name')} shell={shell_target.get('shell_key')} "
        f"spell_id={int(shell_target.get('spell_id', 0))} "
        f"config_changed={str(bool(config_result.get('changed', False)) if isinstance(config_result, dict) else False).lower()} "
        f"runtime_ok={str(bool(runtime_result.ok)).lower()} reload_ok={str(bool(reload_ok)).lower()}"
    )
    for note in runtime_result.notes or []:
        print(f"note={note}")
    if grant_record is not None:
        print(f"grant_recorded=true revoked={str(bool(grant_record.get('revoked', False))).lower()}")
    if output_json is not None:
        print(f"output_json={output_json}")
    return 0 if runtime_result.ok and reload_ok else 1


def _world_table_exists(*, client: MysqlCliClient, settings: Settings, table_name: str) -> bool:
    rows = client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database="information_schema",
        sql=(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            f"WHERE TABLE_SCHEMA = {_sql_string(settings.world_db_name)} "
            f"AND TABLE_NAME = {_sql_string(table_name)} "
            "LIMIT 1"
        ),
    )
    return bool(rows)


def _sql_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
