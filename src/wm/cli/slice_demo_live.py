"""Live-engine wiring for the slice demo.

Replaces SliceRuntime's in-memory fake quest/ability compilers with ones
that drive the NativeApplier — INSERTing real wm_bridge_action_request
rows that the post-0D native bus picks up and executes in-game.

Compilers continue to honor the catch-and-park contract: if the applier
raises, the approval gate catches it and routes the proposal to the
issues queue (no crash).
"""
from __future__ import annotations
from typing import Any
from wm.cli.slice_demo import SliceRuntime
from wm.cli.native_applier import NativeApplier, apply_quest_grant_proposal
from wm.cli.slice_publish import SlicePublishService
from wm.abilities.grant_compiler import compile_grant_plan
from wm.llm.proposal_adapter import Proposal


def build_live_quest_compiler(*, applied_log, publish_service, applier):
    """Build the live quest compiler closure.

    Backward-compatible branch: if the proposal carries a full `draft`
    (LLM-generated, Phase 2), publish-then-grant via the service; if it
    only carries a `grant_quest_id` (proven path / FIXTURE), use the
    existing grant-existing path.
    """

    def live_quest(p: Proposal) -> dict:
        qr = (p.payload or {}).get("quest_release", {})
        if qr.get("draft"):
            beat_id = (p.provenance or {}).get("beat_id", "watcher")
            result = publish_service.publish_and_grant(
                draft_dict=qr["draft"], character_guid=p.character_guid, beat_id=beat_id)
        else:
            result = apply_quest_grant_proposal(p, applier=applier)
        applied_log.append({"kind": "quest", "applier": result,
                            "narrative": p.narrative_summary, "provenance": p.provenance})
        return result

    return live_quest


def wrap_with_live_compilers(rt: SliceRuntime, *, applier: NativeApplier,
                             publish_service: SlicePublishService | None = None) -> SliceRuntime:
    """Mutates the runtime's gate to use live compilers backed by `applier`.

    The applied_log is preserved as a structured trace (kind + payload +
    applier result), so the demo CLI can still print what fired.
    """

    def live_ability(p: Proposal) -> dict[str, Any]:
        ability_id = (p.payload or {}).get("ability_id")
        spec = rt.abilities_by_id.get(ability_id)
        if spec is None:
            raise ValueError(f"unknown ability_id={ability_id}")
        plan = compile_grant_plan(spec, character_guid=p.character_guid)
        result = applier.apply_grant_plan(plan)
        rt.applied_log.append({"kind": "ability", "ability_id": ability_id,
                                "steps": result["steps"]})
        return result

    def live_scene(p: Proposal) -> dict[str, Any]:
        # YAGNI: scene compiler is wm.content.release territory; record only.
        rt.applied_log.append({"kind": "scene", "payload": p.payload})
        return {"ok": True, "note": "scene not wired to native bus in slice"}

    rt.gate._quest = build_live_quest_compiler(   # type: ignore[attr-defined]
        applied_log=rt.applied_log, publish_service=publish_service, applier=applier)
    rt.gate._ability = live_ability      # type: ignore[attr-defined]
    rt.gate._scene = live_scene          # type: ignore[attr-defined]
    return rt
