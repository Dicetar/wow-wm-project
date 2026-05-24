from __future__ import annotations

from wm.items.publish import managed_item_draft_from_dict
from wm.llm.proposal_adapter import Proposal, ProposalKind
from wm.panel.approval_gate import ApprovalGate
from wm.panel.cross_lane import attach_cross_lane_wiring
from wm.panel.issues_queue import IssuesQueue
from wm.spells.publish import managed_spell_draft_from_dict


class _FakeRuntime:
    def __init__(self, gate: ApprovalGate) -> None:
        self.gate = gate
        self.applied_log: list[dict] = []


class _FakePublisher:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def publish(self, *, draft, mode):
        self.calls.append((draft, mode))
        return {"ok": True, "mode": mode}


class _FakeRollback:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.calls: list[dict] = []

    def rollback(self, **kwargs):
        self.calls.append(kwargs)
        return {"ok": True}


_ITEM_DRAFT = {"item_entry": 910013, "base_item_entry": 6948, "name": "Lens"}
_SPELL_DRAFT = {"spell_entry": 946099, "slot_kind": "shell", "name": "Echo Blast"}


def test_managed_item_draft_from_dict_builds_draft():
    draft = managed_item_draft_from_dict(_ITEM_DRAFT)
    assert draft.item_entry == 910013
    assert draft.name == "Lens"


def test_managed_spell_draft_from_dict_builds_draft():
    draft = managed_spell_draft_from_dict(_SPELL_DRAFT)
    assert draft.spell_entry == 946099
    assert draft.name == "Echo Blast"


def _item_proposal():
    return Proposal(kind=ProposalKind.ITEM, character_guid=5407,
                    payload={"item_release": {"item_entry": 910013, "name": "Lens", "draft": _ITEM_DRAFT}})


def _spell_proposal():
    return Proposal(kind=ProposalKind.SPELL, character_guid=5407,
                    payload={"spell_release": {"spell_entry": 946099, "name": "Echo Blast", "draft": _SPELL_DRAFT}})


def test_item_applier_publishes_via_real_publisher():
    gate = ApprovalGate(issues=IssuesQueue())
    rt = _FakeRuntime(gate)
    item_pub = _FakePublisher()
    attach_cross_lane_wiring(rt, item_publisher=item_pub)
    gate.submit(_item_proposal())
    result = gate.approve(gate.pending()[0].id, mode="apply")
    assert result.ok
    assert len(item_pub.calls) == 1
    draft, mode = item_pub.calls[0]
    assert draft.item_entry == 910013
    assert mode == "apply"


def test_spell_applier_passes_dry_run_mode():
    gate = ApprovalGate(issues=IssuesQueue())
    rt = _FakeRuntime(gate)
    spell_pub = _FakePublisher()
    attach_cross_lane_wiring(rt, spell_publisher=spell_pub)
    gate.submit(_spell_proposal())
    gate.approve(gate.pending()[0].id, mode="dry-run")
    assert spell_pub.calls[0][1] == "dry-run"


def test_rollbacks_are_wired_for_each_lane():
    gate = ApprovalGate(issues=IssuesQueue())
    rt = _FakeRuntime(gate)
    item_rb = _FakeRollback("item")
    spell_rb = _FakeRollback("spell")
    attach_cross_lane_wiring(rt, item_rollback=item_rb, spell_rollback=spell_rb)

    assert gate.rollback(artifact_type="item", artifact_entry=910013, mode="apply").ok
    assert gate.rollback(artifact_type="spell", artifact_entry=946099, mode="apply").ok
    assert item_rb.calls[0]["item_entry"] == 910013
    assert spell_rb.calls[0]["spell_entry"] == 946099
