import json
from pathlib import Path
from wm.arcs.story_module import parse_story_module
from wm.arcs.runner import ArcRunner, RunnerEvent
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue
from wm.llm.proposal_adapter import ProposalAdapter, AdapterMode

def _load(p): return json.loads(Path(p).read_text(encoding="utf-8"))

def _make_runner(fixture):
    iq = IssuesQueue()
    applied = []
    def quest_c(p):
        applied.append({"kind":"quest","payload":p.payload,"narrative":p.narrative_summary})
        return {"ok": True, "request_ids":[1]}
    def ability_c(p):
        applied.append({"kind":"ability","payload":p.payload})
        return {"ok": True}
    gate = ApprovalGate(issues=iq, quest_compiler=quest_c, ability_compiler=ability_c)
    adapter = ProposalAdapter(mode=AdapterMode.FIXTURE, fixture=fixture)
    module = parse_story_module(_load("control/examples/story_modules/demo_one.story_module.json"))
    runner = ArcRunner(module=module, adapter=adapter, gate=gate)
    return runner, gate, iq, applied

def test_attention_granted_auto_applies_pinned_b00():
    fixture = _load("tests/fixtures/llm/quest_proposal_basic.json")
    r, gate, iq, applied = _make_runner(fixture)
    r.on_event(RunnerEvent(kind="wm.attention.granted", character_guid=5407, params={}))
    # PINNED b00 auto-applied via gate; no pending proposal left
    assert gate.pending() == []
    assert any(a["kind"] == "quest" and a["payload"]["quest_release"]["title"] == "An Unfamiliar Weight"
               for a in applied)
    assert r.current_beat_id == "b01_zone_intro"

def test_quest_complete_b00_opens_b01_proposal_at_gate():
    fixture = _load("tests/fixtures/llm/quest_proposal_basic.json")
    r, gate, iq, applied = _make_runner(fixture)
    r.on_event(RunnerEvent(kind="wm.attention.granted", character_guid=5407, params={}))
    r.on_event(RunnerEvent(kind="quest.completed", character_guid=5407, params={"beat_ref":"b00_onboarding"}))
    pending = gate.pending()
    assert len(pending) == 1
    assert pending[0].proposal.payload["quest_release"]["title"] == "Wolves at the Vineyard"

def test_grant_point_fires_after_open_beat_quest_complete():
    fixture = _load("tests/fixtures/llm/quest_proposal_basic.json")
    r, gate, iq, applied = _make_runner(fixture)
    r.on_event(RunnerEvent(kind="wm.attention.granted", character_guid=5407, params={}))
    r.on_event(RunnerEvent(kind="quest.completed", character_guid=5407, params={"beat_ref":"b00_onboarding"}))
    # approve the b01 open proposal so the beat is "completed" from the runner's view
    gate.approve(gate.pending()[0].id)
    r.on_event(RunnerEvent(kind="quest.completed", character_guid=5407, params={"beat_ref":"b01_zone_intro",
                          "character_level": 2}))
    # ability grant point fires → ability proposal pending at gate
    abilities_pending = [p for p in gate.pending() if p.proposal.kind.value == "ability"]
    assert len(abilities_pending) == 1
    assert abilities_pending[0].proposal.payload["ability_id"] == "shadow_pulse_aura_v1"
