import pytest
from wm.cli.slice_publish import SlicePublishService, SlicePublishError


class FakeSlot:
    def __init__(self, reserved_id): self.reserved_id = reserved_id; self.slot_status = "staged"


class FakeAllocator:
    def __init__(self, reserved_id=910600): self._id = reserved_id; self.calls = []
    def allocate_next_free_slot(self, **kw):
        self.calls.append(kw); return FakeSlot(self._id)


class FakePublisher:
    def __init__(self, applied=True): self.applied = applied; self.published = []
    def publish(self, *, draft, mode, **kw):
        self.published.append((draft.quest_id, mode))
        outer = self
        class R:
            applied = outer.applied
            validation = {"ok": True}; preflight = {"ok": True}
            def to_dict(self): return {"applied": outer.applied}
        return R()


class FakeSoap:
    def __init__(self): self.commands = []
    def execute_command(self, cmd):
        self.commands.append(cmd)
        class R: ok = True
        return R()


class FakeApplier:
    def __init__(self): self.grants = []
    def insert_quest_add(self, *, character_guid, quest_id, idempotency_key):
        self.grants.append((character_guid, quest_id)); return {"ok": True, "quest_id": quest_id}


DRAFT = {
    "quest_id": 999000, "quest_level": 2, "min_level": 1,
    "questgiver_entry": 197, "questgiver_name": "Marshal McBride",
    "title": "T", "quest_description": "d", "objective_text": "o",
    "offer_reward_text": "r", "request_items_text": "q",
    "objective": {"target_entry": 299, "target_name": "Young Wolf", "kill_count": 6},
    "reward": {"money_copper": 250, "reward_xp_difficulty": 2},
    "start_npc_entry": None, "end_npc_entry": 197,
    "grant_mode": "direct_quest_add", "template_defaults": {"SpecialFlags": 0},
}


def _svc(publisher=None, soap=None, applier=None, alloc=None):
    return SlicePublishService(
        allocator=alloc or FakeAllocator(),
        publisher=publisher or FakePublisher(),
        soap=soap or FakeSoap(),
        applier=applier or FakeApplier(),
    )


def test_publish_and_grant_orders_allocate_publish_reload_grant():
    pub, soap, applier = FakePublisher(), FakeSoap(), FakeApplier()
    svc = _svc(publisher=pub, soap=soap, applier=applier)
    out = svc.publish_and_grant(draft_dict=dict(DRAFT), character_guid=5408, beat_id="b01")
    assert out["quest_id"] == 910600
    assert pub.published == [(910600, "apply")]
    assert any("reload" in c for c in soap.commands)
    assert applier.grants == [(5408, 910600)]


def test_publish_failure_parks_no_grant():
    applier = FakeApplier()
    svc = _svc(publisher=FakePublisher(applied=False), applier=applier)
    with pytest.raises(SlicePublishError):
        svc.publish_and_grant(draft_dict=dict(DRAFT), character_guid=5408, beat_id="b01")
    assert applier.grants == []


def test_no_free_slot_raises():
    class Empty(FakeAllocator):
        def allocate_next_free_slot(self, **kw): return None
    svc = _svc(alloc=Empty())
    with pytest.raises(SlicePublishError):
        svc.publish_and_grant(draft_dict=dict(DRAFT), character_guid=5408, beat_id="b01")


def test_live_quest_compiler_publishes_when_draft_present():
    from wm.cli.slice_demo_live import build_live_quest_compiler
    from wm.llm.proposal_adapter import Proposal, ProposalKind
    pub, applier = FakePublisher(), FakeApplier()
    svc = _svc(publisher=pub, applier=applier)
    log = []
    compiler = build_live_quest_compiler(applied_log=log, publish_service=svc, applier=applier)
    prop = Proposal(kind=ProposalKind.QUEST, character_guid=5408,
                    payload={"quest_release": {"draft": dict(DRAFT)}},
                    provenance={"beat_id": "b01"})
    out = compiler(prop)
    assert out["ok"] is True
    assert applier.grants == [(5408, 910600)]
    assert log and log[0]["kind"] == "quest"


def test_live_quest_compiler_grants_existing_when_only_id_present():
    from wm.cli.slice_demo_live import build_live_quest_compiler
    from wm.llm.proposal_adapter import Proposal, ProposalKind
    applier = FakeApplier()
    log = []
    compiler = build_live_quest_compiler(applied_log=log, publish_service=_svc(applier=applier), applier=applier)
    prop = Proposal(kind=ProposalKind.QUEST, character_guid=5408,
                    payload={"quest_release": {"grant_quest_id": 910502}},
                    provenance={"beat_id": "watcher"})
    out = compiler(prop)
    assert out["ok"] is True
    assert applier.grants == [(5408, 910502)]
