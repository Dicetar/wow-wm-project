from wm.llm.proposal_adapter import (
    AdapterMode, ProposalAdapter, ProposalKind, ProposalRequest,
)


def _req(kind: ProposalKind) -> ProposalRequest:
    return ProposalRequest(kind=kind, context={"character": {"guid": 5407}}, intent="", constraints={})


def _adapter(fixture: dict) -> ProposalAdapter:
    return ProposalAdapter(mode=AdapterMode.FIXTURE, fixture=fixture)


def test_item_proposal_with_item_release_is_accepted():
    fixture = {"kind": "item", "payload": {"item_release": {"item_entry": 910013, "name": "Lens"}}}
    p = _adapter(fixture).propose(_req(ProposalKind.ITEM))
    assert p.kind is ProposalKind.ITEM
    assert not p.is_blocked


def test_item_proposal_missing_required_field_is_blocked():
    fixture = {"kind": "item", "payload": {"item_release": {"item_entry": 910013}}}
    p = _adapter(fixture).propose(_req(ProposalKind.ITEM))
    assert p.is_blocked
    assert "name" in p.block_reason


def test_item_proposal_missing_envelope_is_blocked():
    fixture = {"kind": "item", "payload": {}}
    p = _adapter(fixture).propose(_req(ProposalKind.ITEM))
    assert p.is_blocked
    assert "item_release" in p.block_reason


def test_spell_proposal_with_spell_release_is_accepted():
    fixture = {"kind": "spell", "payload": {"spell_release": {"spell_entry": 946099, "name": "Echo Blast"}}}
    p = _adapter(fixture).propose(_req(ProposalKind.SPELL))
    assert p.kind is ProposalKind.SPELL
    assert not p.is_blocked


def test_spell_proposal_missing_required_field_is_blocked():
    fixture = {"kind": "spell", "payload": {"spell_release": {"name": "Echo Blast"}}}
    p = _adapter(fixture).propose(_req(ProposalKind.SPELL))
    assert p.is_blocked
    assert "spell_entry" in p.block_reason


def test_action_proposal_with_action_request_is_accepted():
    fixture = {"kind": "action", "payload": {"action_request": {"action_kind": "AddAura"}}}
    p = _adapter(fixture).propose(_req(ProposalKind.ACTION))
    assert p.kind is ProposalKind.ACTION
    assert not p.is_blocked


def test_action_proposal_missing_action_kind_is_blocked():
    fixture = {"kind": "action", "payload": {"action_request": {}}}
    p = _adapter(fixture).propose(_req(ProposalKind.ACTION))
    assert p.is_blocked
    assert "action_kind" in p.block_reason
