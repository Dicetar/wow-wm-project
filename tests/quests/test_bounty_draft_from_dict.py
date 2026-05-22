from wm.quests.publish import bounty_draft_from_dict
from wm.quests.models import BountyQuestDraft


def _raw() -> dict:
    return {
        "quest_id": 910503, "quest_level": 2, "min_level": 1,
        "questgiver_entry": 197, "questgiver_name": "Marshal McBride",
        "title": "Wolves at the Treeline",
        "quest_description": "Thin the wolves circling Northshire.",
        "objective_text": "Slay 6 Young Wolves.",
        "offer_reward_text": "The valley is safer for it.",
        "request_items_text": "Are the wolves dealt with?",
        "objective": {"target_entry": 299, "target_name": "Young Wolf", "kill_count": 6},
        "reward": {"money_copper": 250, "reward_xp_difficulty": 2},
        "start_npc_entry": None, "end_npc_entry": 197,
        "grant_mode": "direct_quest_add", "tags": ["wm-slice"],
        "template_defaults": {"SpecialFlags": 0},
    }


def test_bounty_draft_from_dict_builds_draft():
    draft = bounty_draft_from_dict(_raw())
    assert isinstance(draft, BountyQuestDraft)
    assert draft.quest_id == 910503
    assert draft.objective.target_entry == 299
    assert draft.objective.kill_count == 6
    assert draft.grant_mode == "direct_quest_add"


def test_load_bounty_quest_draft_still_works(tmp_path):
    import json
    from wm.quests.publish import load_bounty_quest_draft
    p = tmp_path / "d.json"
    p.write_text(json.dumps(_raw()), encoding="utf-8")
    assert load_bounty_quest_draft(p).quest_id == 910503


def test_slice_bounty_schema_is_valid_json_and_constrains_kill_count():
    import json
    from pathlib import Path
    schema = json.loads(Path("control/schemas/wm.slice.bounty_draft.v1.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == "wm.slice.bounty_draft.v1"
    assert schema["properties"]["objective"]["properties"]["kill_count"]["maximum"] == 25
    for fld in ("title", "quest_description", "objective_text", "offer_reward_text",
                "request_items_text", "objective", "reward"):
        assert fld in schema["required"]
