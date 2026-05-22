import json
from wm.llm.proposal_adapter import (
    ProposalAdapter, AdapterMode, ProposalKind, ProposalRequest,
)

SCHEMA = json.load(open("control/schemas/wm.slice.bounty_draft.v1.schema.json", encoding="utf-8"))

GOOD = {
    "schema_version": "wm.slice.bounty_draft.v1",
    "title": "Wolves at the Treeline",
    "quest_description": "Thin the wolves circling Northshire.",
    "objective_text": "Slay 6 Young Wolves.",
    "offer_reward_text": "The valley is safer for it.",
    "request_items_text": "Are the wolves dealt with?",
    "narrative_summary": "McBride sends you to thin the wolves.",
    "objective": {"kill_count": 6},
    "reward": {"money_copper": 250, "reward_xp_difficulty": 2},
}

CONSTRAINTS = {
    "quest_id_placeholder": 999000, "quest_level": 2, "min_level": 1,
    "questgiver_entry": 197, "questgiver_name": "Marshal McBride",
    "objective": {"target_entry": 299, "target_name": "Young Wolf"},
    "end_npc_entry": 197, "start_npc_entry": None,
    "grant_mode": "direct_quest_add", "template_defaults": {"SpecialFlags": 0},
}


class FakeClient:
    def __init__(self, parsed, content=None):
        self._parsed = parsed
        self._content = content if content is not None else json.dumps(parsed)
        self.calls = []

    def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return {"parsed": self._parsed, "content": self._content, "raw": {}, "request": {}}


def _req():
    return ProposalRequest(kind=ProposalKind.QUEST,
                           context={"character": {"guid": 5408}},
                           intent="A Northshire shake-out.",
                           constraints=CONSTRAINTS)


def test_live_good_draft_unblocked_with_embedded_flat_draft():
    client = FakeClient(GOOD)
    adapter = ProposalAdapter(mode=AdapterMode.LIVE, llm_client=client, quest_schema=SCHEMA)
    prop = adapter.propose(_req())
    assert prop.is_blocked is False
    qr = prop.payload["quest_release"]
    assert qr["title"] == "Wolves at the Treeline"
    assert qr["giver_creature_entry"] == 197
    assert qr["objective_kind"] == "kill"
    assert qr["draft"]["objective"]["target_entry"] == 299
    assert qr["draft"]["objective"]["kill_count"] == 6
    assert qr["draft"]["grant_mode"] == "direct_quest_add"
    assert "grant_quest_id" not in qr
    assert prop.provenance["mode"] == "live"


def test_live_forbidden_pattern_blocks():
    bad = {**GOOD, "quest_description": "'; DROP TABLE quest_template; --"}
    adapter = ProposalAdapter(mode=AdapterMode.LIVE, llm_client=FakeClient(bad), quest_schema=SCHEMA)
    prop = adapter.propose(_req())
    assert prop.is_blocked is True
    assert "forbidden" in prop.block_reason.lower()


def test_live_validator_error_blocks():
    bad = {**GOOD, "objective": {"kill_count": 99}}
    adapter = ProposalAdapter(mode=AdapterMode.LIVE, llm_client=FakeClient(bad), quest_schema=SCHEMA)
    prop = adapter.propose(_req())
    assert prop.is_blocked is True
    assert "kill_count" in prop.block_reason


def test_live_llm_unreachable_blocks():
    class Boom:
        def generate_json(self, **kwargs):
            raise RuntimeError("LM Studio request failed")
    adapter = ProposalAdapter(mode=AdapterMode.LIVE, llm_client=Boom(), quest_schema=SCHEMA)
    prop = adapter.propose(_req())
    assert prop.is_blocked is True
    assert "LM Studio" in prop.block_reason
