"""Approval gate: one queue, both loops (arc OPEN + Watcher) feed in here.

Approve = call the matching deterministic compiler. Reject = log to issues.
Blocked proposals (from the LLM adapter validator) skip the gate and go
straight to issues.
"""
from __future__ import annotations
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


QuestCompiler = Callable[[Proposal], dict]
AbilityCompiler = Callable[[Proposal], dict]
SceneCompiler = Callable[[Proposal], dict]


class ApprovalGate:
    def __init__(self, *, issues: IssuesQueue,
                 quest_compiler: QuestCompiler | None = None,
                 ability_compiler: AbilityCompiler | None = None,
                 scene_compiler: SceneCompiler | None = None) -> None:
        self._pending: list[PendingProposal] = []
        self._ids = count(1)
        self._issues = issues
        self._quest = quest_compiler
        self._ability = ability_compiler
        self._scene = scene_compiler

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

    def approve(self, pid: int) -> ApplyResult:
        pp = self._take(pid)
        if pp is None:
            return ApplyResult(ok=False, error="not_found")
        p = pp.proposal
        compiler = {ProposalKind.QUEST: self._quest,
                    ProposalKind.ABILITY: self._ability,
                    ProposalKind.SCENE: self._scene}.get(p.kind)
        if compiler is None:
            self._issues.add(reason=f"no compiler wired for kind={p.kind.value}",
                             kind=p.kind.value, character_guid=p.character_guid,
                             payload=p.payload, provenance=p.provenance)
            return ApplyResult(ok=False, error="no_compiler")
        try:
            detail = compiler(p)
            return ApplyResult(ok=True, detail=detail)
        except Exception as e:    # catch-and-park, never crash the loop
            self._issues.add(reason=f"compiler_exception: {e}",
                             kind=p.kind.value, character_guid=p.character_guid,
                             payload=p.payload, provenance=p.provenance)
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
