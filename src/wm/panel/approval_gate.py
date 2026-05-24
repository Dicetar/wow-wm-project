"""Approval gate: one queue, both loops (arc OPEN + Watcher) feed in here.

Approve = call the matching deterministic compiler. Reject = log to issues.
Blocked proposals (from the LLM adapter validator) skip the gate and go
straight to issues.
"""
from __future__ import annotations
import inspect
from dataclasses import dataclass, field
from itertools import count
from typing import Callable
from wm.llm.proposal_adapter import Proposal, ProposalKind
from wm.panel.issues_queue import IssuesQueue


@dataclass(slots=True)
class PendingProposal:
    id: int
    proposal: Proposal


@dataclass(slots=True)
class ApplyResult:
    ok: bool
    detail: dict | None = None
    error: str | None = None


# An applier turns an approved proposal into a published artifact. Legacy
# appliers take just (proposal); mode-aware ones also accept a `mode` kwarg
# ("dry-run"/"apply") so the same gate drives both the per-lane dry-run and
# apply paths of the existing publish contracts.
Applier = Callable[..., dict]
QuestCompiler = Applier
AbilityCompiler = Applier
SceneCompiler = Applier
# A rollback callable takes (artifact_entry, mode) and drives the matching
# lane's existing rollback contract; the gate stays decoupled from DB clients.
Rollback = Callable[[int, str], dict]


class ApprovalGate:
    def __init__(self, *, issues: IssuesQueue,
                 quest_compiler: QuestCompiler | None = None,
                 ability_compiler: AbilityCompiler | None = None,
                 scene_compiler: SceneCompiler | None = None,
                 item_applier: Applier | None = None,
                 spell_applier: Applier | None = None,
                 action_applier: Applier | None = None,
                 quest_rollback: Rollback | None = None,
                 item_rollback: Rollback | None = None,
                 spell_rollback: Rollback | None = None) -> None:
        self._pending: list[PendingProposal] = []
        self._ids = count(1)
        self._issues = issues
        self._quest = quest_compiler
        self._ability = ability_compiler
        self._scene = scene_compiler
        self._item = item_applier
        self._spell = spell_applier
        self._action = action_applier
        self._rollbacks: dict[str, Rollback] = {
            k: v for k, v in {"quest": quest_rollback, "item": item_rollback, "spell": spell_rollback}.items()
            if v is not None
        }

    def _applier_for(self, kind: ProposalKind) -> Applier | None:
        return {ProposalKind.QUEST: self._quest,
                ProposalKind.ABILITY: self._ability,
                ProposalKind.SCENE: self._scene,
                ProposalKind.ITEM: self._item,
                ProposalKind.SPELL: self._spell,
                ProposalKind.ACTION: self._action}.get(kind)

    def submit(self, p: Proposal) -> None:
        if p.is_blocked:
            self._issues.add(reason=p.block_reason, kind=p.kind.value,
                             character_guid=p.character_guid,
                             payload=p.payload, provenance=p.provenance)
            return
        self._pending.append(PendingProposal(id=next(self._ids), proposal=p))

    def submit_auto_apply(self, p: Proposal) -> ApplyResult:
        """PINNED beats use this — the proposal is already authored and validated;
        skip the operator approval but run through the same compiler + catch-and-park."""
        if p.is_blocked:
            self.submit(p)
            return ApplyResult(ok=False, error="blocked")
        pp = PendingProposal(id=next(self._ids), proposal=p)
        self._pending.append(pp)
        return self.approve(pp.id)

    def pending(self) -> list[PendingProposal]:
        return list(self._pending)

    def approve(self, pid: int, *, mode: str = "apply") -> ApplyResult:
        pp = self._take(pid)
        if pp is None:
            return ApplyResult(ok=False, error="not_found")
        p = pp.proposal
        applier = self._applier_for(p.kind)
        if applier is None:
            self._issues.add(reason=f"no applier wired for kind={p.kind.value}",
                             kind=p.kind.value, character_guid=p.character_guid,
                             payload=p.payload, provenance=p.provenance)
            return ApplyResult(ok=False, error="no_applier")
        try:
            detail = _invoke(applier, p, mode)
            return ApplyResult(ok=True, detail=detail)
        except Exception as e:    # catch-and-park, never crash the loop
            self._issues.add(reason=f"applier_exception: {e}",
                             kind=p.kind.value, character_guid=p.character_guid,
                             payload=p.payload, provenance=p.provenance)
            return ApplyResult(ok=False, error=str(e))

    def rollback(self, *, artifact_type: str, artifact_entry: int, mode: str = "apply") -> ApplyResult:
        fn = self._rollbacks.get(artifact_type)
        if fn is None:
            self._issues.add(reason=f"no rollback wired for artifact_type={artifact_type}",
                             kind=artifact_type, character_guid=0,
                             payload={"artifact_entry": int(artifact_entry)}, provenance={})
            return ApplyResult(ok=False, error="no_rollback")
        try:
            detail = fn(int(artifact_entry), mode)
            return ApplyResult(ok=True, detail=detail)
        except Exception as e:    # catch-and-park, never crash the loop
            self._issues.add(reason=f"rollback_exception: {e}",
                             kind=artifact_type, character_guid=0,
                             payload={"artifact_entry": int(artifact_entry)}, provenance={})
            return ApplyResult(ok=False, error=str(e))

    def reject(self, pid: int, *, reason: str) -> None:
        pp = self._take(pid)
        if pp is None: return
        self._issues.add(reason=reason, kind=pp.proposal.kind.value,
                         character_guid=pp.proposal.character_guid,
                         payload=pp.proposal.payload, provenance=pp.proposal.provenance)

    def _take(self, pid: int) -> PendingProposal | None:
        for i, x in enumerate(self._pending):
            if x.id == pid:
                return self._pending.pop(i)
        return None


def _invoke(applier: Applier, p: Proposal, mode: str) -> dict:
    """Call a mode-aware applier with the mode kwarg; fall back to the legacy
    one-arg form so existing compilers keep working unchanged."""
    if _accepts_mode(applier):
        return applier(p, mode=mode)
    return applier(p)


def _accepts_mode(applier: Applier) -> bool:
    try:
        params = inspect.signature(applier).parameters
    except (TypeError, ValueError):
        return False
    if "mode" in params:
        return True
    return any(param.kind is inspect.Parameter.VAR_KEYWORD for param in params.values())
