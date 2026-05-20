from wm.llm.proposal_adapter import Proposal, ProposalKind
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue

def _pending_quest():
    return Proposal(kind=ProposalKind.QUEST, character_guid=5407,
                    payload={"quest_release": {"title": "x", "objective": "y", "description": "z",
                              "giver_creature_entry": 197, "objective_kind": "kill_creature",
                              "rewards": {"xp": 10}}},
                    narrative_summary="hi", provenance={"mode": "fixture"})

def test_blocked_proposal_routes_to_issues_queue():
    iq = IssuesQueue()
    gate = ApprovalGate(issues=iq)
    blocked = Proposal(kind=ProposalKind.QUEST, character_guid=5407, payload={},
                       is_blocked=True, block_reason="missing quest_release")
    gate.submit(blocked)
    assert gate.pending() == []
    assert len(iq.list_open()) == 1
    assert iq.list_open()[0].reason == "missing quest_release"

def test_pending_proposal_can_be_approved():
    iq = IssuesQueue()
    applied: list[dict] = []
    def fake_quest_compiler(p): applied.append({"kind":"quest","payload":p.payload}); return {"ok": True, "request_ids":[123]}
    def fake_ability_compiler(p): raise AssertionError("not used here")
    gate = ApprovalGate(issues=iq, quest_compiler=fake_quest_compiler, ability_compiler=fake_ability_compiler)
    p = _pending_quest()
    gate.submit(p)
    pid = gate.pending()[0].id
    result = gate.approve(pid)
    assert result.ok
    assert applied and applied[0]["kind"] == "quest"
    assert gate.pending() == []

def test_rejection_records_and_drops():
    iq = IssuesQueue()
    gate = ApprovalGate(issues=iq)
    gate.submit(_pending_quest())
    pid = gate.pending()[0].id
    gate.reject(pid, reason="operator-deferred")
    assert gate.pending() == []
    # rejected proposals are logged in issues for triage
    assert any(i.reason == "operator-deferred" for i in iq.list_open())
