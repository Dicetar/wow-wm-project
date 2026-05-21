from wm.cli.slice_demo import SliceRuntime, ScriptedOperator


def test_feed_attention_activates_b00_like_the_aura_sentinel():
    # The aura sentinel (BridgeEventPump) calls feed_attention when the
    # marker aura is observed — same effect the obsolete item-use path had.
    rt = SliceRuntime.bootstrap(character_guid=5408, starter_item_entry=0)
    assert rt.runner.current_beat_id == "b00_onboarding"
    rt.feed_attention(character_guid=5408)
    assert rt.runner.current_beat_id == "b01_zone_intro"


def test_happy_path_demo():
    rt = SliceRuntime.bootstrap(character_guid=5407, starter_item_entry=910500)
    op = ScriptedOperator(rt.gate)
    # 1. player uses starter item → attention.granted → b00 PINNED auto-applies
    rt.feed_use_item(item_entry=910500)
    assert rt.runner.current_beat_id == "b01_zone_intro"
    # 2. player completes b00's quest → b01 OPEN proposal appears
    rt.feed_quest_completed(beat_ref="b00_onboarding")
    op.approve_next()  # operator approves
    # 3. player completes b01's quest → grant point 1 fires
    rt.feed_quest_completed(beat_ref="b01_zone_intro", character_level=2)
    op.approve_next()  # approve the ability grant
    # 4. Watcher: 8 zone kills in the window → bounty proposal
    for i in range(8):
        rt.feed_kill(creature_family="murloc", zone="elwynn", ts=i)
    op.approve_next()  # approve the watcher bounty
    # 5. complete b02 + b03 to reach finale grant
    rt.feed_quest_completed(beat_ref="b01_zone_intro", character_level=2)  # noop, already past
    rt.feed_quest_completed(beat_ref="b02_complication", character_level=3)
    rt.feed_quest_completed(beat_ref="b03_finale", character_level=4)
    # gate may now have b02 OPEN proposal, b03 PINNED auto-apply, then echo_lash grant
    while rt.gate.pending():
        op.approve_next()
    applied_kinds = [a["kind"] for a in rt.applied_log]
    assert "quest" in applied_kinds
    assert applied_kinds.count("ability") >= 1
    assert rt.issues.list_open() == []  # no parked errors in happy path
