import json
from pathlib import Path
from wm.reactive.reactive_template import parse_reactive_template
from wm.reactive.watcher import Watcher, WatcherEvent
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue
from wm.llm.proposal_adapter import ProposalAdapter, AdapterMode

def _load(p): return json.loads(Path(p).read_text(encoding="utf-8"))

def _make_watcher(active_character_guid=5407):
    iq = IssuesQueue()
    applied = []
    def quest_c(p): applied.append(p); return {"ok": True}
    gate = ApprovalGate(issues=iq, quest_compiler=quest_c)
    adapter = ProposalAdapter(
        mode=AdapterMode.FIXTURE,
        fixture=_load("tests/fixtures/llm/quest_proposal_basic.json"),
    )
    templates = [parse_reactive_template(_load("control/examples/reactive_templates/zone_kill_bounty.json"))]
    w = Watcher(templates=templates, adapter=adapter, gate=gate,
                active_character_guid=active_character_guid)
    return w, gate, iq, applied

def test_no_match_below_threshold():
    w, gate, iq, _ = _make_watcher()
    for i in range(3):
        w.on_event(WatcherEvent(kind="kill", character_guid=5407,
                                params={"creature_family":"murloc","zone":"elwynn"}, ts=i))
    assert gate.pending() == []

def test_threshold_match_fires_proposal_at_gate():
    w, gate, iq, _ = _make_watcher()
    for i in range(8):
        w.on_event(WatcherEvent(kind="kill", character_guid=5407,
                                params={"creature_family":"murloc","zone":"elwynn"}, ts=i))
    pending = gate.pending()
    assert len(pending) == 1
    assert pending[0].proposal.kind.value == "quest"

def test_cooldown_suppresses_duplicate_fire_within_window():
    w, gate, iq, _ = _make_watcher()
    # first fire
    for i in range(8):
        w.on_event(WatcherEvent(kind="kill", character_guid=5407,
                                params={"creature_family":"murloc","zone":"elwynn"}, ts=i))
    assert len(gate.pending()) == 1
    # 8 more kills well inside cooldown_min=60 ⇒ no second fire
    for i in range(8, 16):
        w.on_event(WatcherEvent(kind="kill", character_guid=5407,
                                params={"creature_family":"murloc","zone":"elwynn"}, ts=i))
    assert len(gate.pending()) == 1

def test_other_character_events_do_not_trigger():
    w, gate, iq, _ = _make_watcher(active_character_guid=5407)
    for i in range(8):
        w.on_event(WatcherEvent(kind="kill", character_guid=9999,
                                params={"creature_family":"murloc","zone":"elwynn"}, ts=i))
    assert gate.pending() == []
