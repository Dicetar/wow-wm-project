"""Wire the approval gate's item/spell appliers and per-lane rollbacks to the
real publish/rollback contracts.

Kept dependency-injected (publishers + rollbacks are passed in) so the wiring
is unit-testable with fakes and never imports a DB client at module load. The
live panel factory constructs the real publishers and calls this.

Convention: an item/spell proposal carries the full managed-draft dict under
`payload[<lane>_release]["draft"]` (mirrors the quest `quest_release.draft`
branch in slice_demo_live). The applier builds the typed draft and hands it to
the lane publisher with the gate's dry-run/apply mode.
"""
from __future__ import annotations

from typing import Any

from wm.items.publish import managed_item_draft_from_dict
from wm.llm.proposal_adapter import Proposal
from wm.spells.publish import managed_spell_draft_from_dict


def attach_cross_lane_wiring(
    rt: Any,
    *,
    item_publisher: Any | None = None,
    spell_publisher: Any | None = None,
    item_rollback: Any | None = None,
    spell_rollback: Any | None = None,
    quest_rollback: Any | None = None,
    runtime_sync_mode: str = "none",
) -> Any:
    """Attach item/spell appliers and quest/item/spell rollbacks onto rt.gate.

    Only the lanes whose dependency is provided are wired; the rest stay as-is
    (so a partially-configured environment degrades to no_applier/no_rollback
    rather than crashing).
    """
    applied_log = getattr(rt, "applied_log", None)

    if item_publisher is not None:
        rt.gate._item = _build_publish_applier(  # type: ignore[attr-defined]
            envelope_key="item_release", draft_from_dict=managed_item_draft_from_dict,
            publisher=item_publisher, kind="item", applied_log=applied_log)
    if spell_publisher is not None:
        rt.gate._spell = _build_publish_applier(  # type: ignore[attr-defined]
            envelope_key="spell_release", draft_from_dict=managed_spell_draft_from_dict,
            publisher=spell_publisher, kind="spell", applied_log=applied_log)

    if quest_rollback is not None:
        rt.gate._rollbacks["quest"] = _build_rollback(
            quest_rollback, entry_kw="quest_entry", runtime_sync_mode=runtime_sync_mode)
    if item_rollback is not None:
        rt.gate._rollbacks["item"] = _build_rollback(
            item_rollback, entry_kw="item_entry", runtime_sync_mode=runtime_sync_mode)
    if spell_rollback is not None:
        rt.gate._rollbacks["spell"] = _build_rollback(
            spell_rollback, entry_kw="spell_entry", runtime_sync_mode=runtime_sync_mode)
    return rt


def _build_publish_applier(*, envelope_key, draft_from_dict, publisher, kind, applied_log):
    def applier(p: Proposal, *, mode: str = "apply") -> dict:
        section = (p.payload or {}).get(envelope_key) or {}
        draft_dict = section.get("draft")
        if not draft_dict:
            raise ValueError(f"{kind} proposal payload is missing {envelope_key}.draft")
        draft = draft_from_dict(draft_dict)
        result = publisher.publish(draft=draft, mode=mode)
        detail = result.to_dict() if hasattr(result, "to_dict") else result
        if applied_log is not None:
            applied_log.append({"kind": kind, "mode": mode, "result": detail})
        return detail
    return applier


def _build_rollback(rollback_obj: Any, *, entry_kw: str, runtime_sync_mode: str):
    def do_rollback(entry: int, mode: str) -> dict:
        result = rollback_obj.rollback(**{
            entry_kw: int(entry),
            "mode": mode,
            "runtime_sync_mode": runtime_sync_mode,
            "soap_commands": [],
        })
        return result.to_dict() if hasattr(result, "to_dict") else result
    return do_rollback
