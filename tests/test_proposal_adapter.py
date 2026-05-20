from pathlib import Path
import json
from wm.llm.proposal_adapter import (
    ProposalAdapter, ProposalKind, ProposalRequest, AdapterMode,
)

def _fixture(): return json.loads(Path("tests/fixtures/llm/quest_proposal_basic.json").read_text(encoding="utf-8"))

def test_fixture_mode_returns_recorded_proposal():
    a = ProposalAdapter(mode=AdapterMode.FIXTURE, fixture=_fixture())
    req = ProposalRequest(
        kind=ProposalKind.QUEST,
        context={"character": {"guid": 5407, "name": "Demo One", "zone_id": 12, "level": 2}},
        intent="A short Northshire quest. One kill objective. Tone: cautious.",
        constraints={"giver_pool": [197], "max_objectives": 1, "id_ranges": {"quest": [910500, 910549]}},
    )
    p = a.propose(req)
    assert p.kind is ProposalKind.QUEST
    assert p.payload["quest_release"]["title"]
    assert p.payload["quest_release"]["giver_creature_entry"] == 197
    assert p.character_guid == 5407
    assert p.provenance["mode"] == "fixture"

def test_invalid_fixture_routes_to_issues_queue():
    bad = {"kind": "quest", "payload": {"oops": "no quest_release"}}
    a = ProposalAdapter(mode=AdapterMode.FIXTURE, fixture=bad)
    req = ProposalRequest(kind=ProposalKind.QUEST, context={"character": {"guid": 5407}},
                          intent="x", constraints={})
    p = a.propose(req)
    assert p.is_blocked
    assert "quest_release" in p.block_reason
