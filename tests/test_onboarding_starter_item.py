from wm.onboarding.starter_item import (
    build_starter_item_grant_plan, OnboardingHandler, OnboardingEvent,
)

def test_grant_plan_targets_active_character():
    plan = build_starter_item_grant_plan(character_guid=5407, item_entry=910500)
    assert plan.character_guid == 5407
    assert plan.steps and plan.steps[0].action_kind == "player_add_item"
    assert plan.steps[0].payload["item_id"] == 910500

def test_use_item_with_starter_emits_attention_granted():
    seen = []
    h = OnboardingHandler(starter_item_entry=910500,
                          active_character_guid=5407,
                          emit=lambda evt: seen.append(evt))
    h.on_event(OnboardingEvent(kind="use_item", character_guid=5407,
                               params={"item_entry": 910500}))
    assert len(seen) == 1
    assert seen[0].kind == "wm.attention.granted"
    assert seen[0].character_guid == 5407

def test_use_item_other_item_or_other_char_is_ignored():
    seen = []
    h = OnboardingHandler(starter_item_entry=910500, active_character_guid=5407,
                          emit=lambda evt: seen.append(evt))
    h.on_event(OnboardingEvent(kind="use_item", character_guid=5407, params={"item_entry": 6948}))
    h.on_event(OnboardingEvent(kind="use_item", character_guid=9999, params={"item_entry": 910500}))
    assert seen == []
