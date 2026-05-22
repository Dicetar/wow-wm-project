import json
from wm.panel.slice_wiring import load_slice_quest_schema
from wm.cli.slice_demo import SliceRuntime
from wm.llm.proposal_adapter import AdapterMode


class FakeClient:
    def generate_json(self, **kwargs):
        authored = {
            "schema_version": "wm.slice.bounty_draft.v1",
            "title": "T", "quest_description": "d", "objective_text": "o",
            "offer_reward_text": "r", "request_items_text": "q",
            "objective": {"kill_count": 4}, "reward": {"money_copper": 100},
        }
        return {"parsed": authored, "content": json.dumps(authored), "raw": {}, "request": {}}


def test_bootstrap_live_adapter_builds_with_fake_client():
    rt = SliceRuntime.bootstrap(
        character_guid=5408, starter_item_entry=0,
        adapter_mode=AdapterMode.LIVE,
        llm_client=FakeClient(), quest_schema=load_slice_quest_schema())
    assert rt.runner is not None
    # the demo OPEN beat must carry fixed-fact constraints for the LIVE merge:
    beats = getattr(rt.runner.module, "beats", [])
    open_beats = [b for b in beats if getattr(b, "constraints", None) and "questgiver_entry" in b.constraints]
    assert open_beats, "expected at least one beat with fixed-fact constraints"
