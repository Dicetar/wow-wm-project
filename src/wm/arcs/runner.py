"""Arc Runner — advances a StoryModule's beats on sensed events.

PINNED beats auto-apply via the gate (authored + validated).
OPEN beats produce an LLM proposal via the adapter and submit to the gate.
Grant points fire as their own ability proposals when their `when` event +
`appropriateness` predicate hold.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from wm.arcs.story_module import StoryModule, Beat, BeatKind, GrantPoint
from wm.llm.proposal_adapter import (
    Proposal, ProposalKind, ProposalRequest, ProposalAdapter,
)
from wm.panel.approval_gate import ApprovalGate


@dataclass(slots=True)
class RunnerEvent:
    kind: str
    character_guid: int
    params: dict[str, Any] = field(default_factory=dict)


class ArcRunner:
    def __init__(self, *, module: StoryModule, adapter: ProposalAdapter, gate: ApprovalGate) -> None:
        self.module = module
        self.adapter = adapter
        self.gate = gate
        self.current_beat_id: str | None = module.beats[0].id if module.beats else None
        self._completed_beats: set[str] = set()
        self._beat_by_id = {b.id: b for b in module.beats}

    def on_event(self, evt: RunnerEvent) -> None:
        if evt.character_guid != self.module.character_guid:
            return
        if self.current_beat_id is None:
            return

        beat = self._beat_by_id[self.current_beat_id]
        if self._event_matches(evt, beat.entry_condition):
            self._process_beat(beat, evt)
            return

        # check if this event completes a previously-applied beat → grant points
        for b in self.module.beats:
            if b.id in self._completed_beats: continue
            for gp in b.outcome.grant_points:
                if self._event_matches(evt, gp.when) and self._appropriateness_ok(gp, evt):
                    self._submit_ability_grant(gp)
            # quest-completed events also advance the runner to next beat
            if self._event_matches(evt, {"event":"quest.completed","ref":b.id}):
                self._completed_beats.add(b.id)
                self.current_beat_id = b.outcome.next_beat_ref

    # --- processing ----------------------------------------------------

    def _process_beat(self, beat: Beat, evt: RunnerEvent) -> None:
        if beat.kind is BeatKind.PINNED:
            assert beat.payload is not None
            p = Proposal(
                kind=ProposalKind.QUEST,
                character_guid=self.module.character_guid,
                payload=beat.payload,
                narrative_summary=f"PINNED beat {beat.id} ({self.module.module_id})",
                provenance={"mode": "pinned", "beat_id": beat.id},
            )
            self.gate.submit_auto_apply(p)
            self._completed_beats.add(beat.id)
            self.current_beat_id = beat.outcome.next_beat_ref
            return

        # OPEN — build a proposal request and ask the adapter
        req = ProposalRequest(
            kind=ProposalKind.QUEST,
            context={"character": {"guid": self.module.character_guid,
                                   "name": self.module.character_name}},
            intent=beat.intent or "",
            constraints=beat.constraints,
        )
        prop = self.adapter.propose(req)
        prop.provenance.setdefault("beat_id", beat.id)
        self.gate.submit(prop)
        # do NOT mark completed here; completion fires on quest.completed event

    def _submit_ability_grant(self, gp: GrantPoint) -> None:
        prop = Proposal(
            kind=ProposalKind.ABILITY,
            character_guid=self.module.character_guid,
            payload={"ability_id": gp.ability_ref, "grant_kind": gp.grant_kind},
            narrative_summary=f"grant {gp.ability_ref}",
            provenance={"mode": "grant_point"},
        )
        self.gate.submit(prop)

    # --- predicates ----------------------------------------------------

    def _event_matches(self, evt: RunnerEvent, cond: dict[str, Any]) -> bool:
        if cond.get("event") != evt.kind: return False
        if "ref" in cond and evt.params.get("beat_ref") != cond["ref"]: return False
        return True

    def _appropriateness_ok(self, gp: GrantPoint, evt: RunnerEvent) -> bool:
        return self._eval_predicate(gp.appropriateness, evt)

    def _eval_predicate(self, pred: dict[str, Any], evt: RunnerEvent) -> bool:
        # tiny DSL: {"all_of":[...]} / {"any_of":[...]} over named checks
        if "all_of" in pred:
            return all(self._eval_predicate(p, evt) for p in pred["all_of"])
        if "any_of" in pred:
            return any(self._eval_predicate(p, evt) for p in pred["any_of"])
        if "character_level_at_least" in pred:
            return int(evt.params.get("character_level", 0)) >= int(pred["character_level_at_least"])
        if "journal_has_tag" in pred:
            return str(pred["journal_has_tag"]) in evt.params.get("journal_tags", [])
        return False  # unknown predicate ⇒ fail closed
