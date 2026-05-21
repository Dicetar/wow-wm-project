"""Tests for the live-engine wiring on top of SliceRuntime."""
from __future__ import annotations
import json
from wm.cli.slice_demo import SliceRuntime, ScriptedOperator
from wm.cli.slice_demo_live import wrap_with_live_compilers
from wm.cli.native_applier import NativeApplier


class _RecordingClient:
    def __init__(self): self.executed: list[str] = []
    def query(self, **kw): self.executed.append(kw["sql"]); return []


def _live_runtime():
    rt = SliceRuntime.bootstrap(character_guid=5407, starter_item_entry=910500)
    rc = _RecordingClient()
    applier = NativeApplier(client=rc, host="h", port=33307, user="u", password="p", database="acore_world")
    wrap_with_live_compilers(rt, applier=applier)
    return rt, rc, applier


def test_live_pinned_b00_inserts_quest_add_for_managed_quest():
    rt, rc, _ = _live_runtime()
    rt.feed_use_item(item_entry=910500)  # b00 PINNED auto-applies
    quest_add_sqls = [s for s in rc.executed if "'quest_add'" in s]
    assert len(quest_add_sqls) == 1
    assert "\"quest_id\":910500" in quest_add_sqls[0]  # managed quest, not stock 783
    assert "5407" in quest_add_sqls[0]


def test_live_open_b01_after_approval_inserts_quest_add_for_managed_quest():
    rt, rc, _ = _live_runtime()
    op = ScriptedOperator(rt.gate)
    rt.feed_use_item(item_entry=910500)
    rt.feed_quest_completed(beat_ref="b00_onboarding")
    op.approve_next()
    quest_add_sqls = [s for s in rc.executed if "'quest_add'" in s]
    assert any("\"quest_id\":910502" in s for s in quest_add_sqls)  # managed quest, not stock 15


def test_live_ability_grant_inserts_apply_aura_action():
    rt, rc, _ = _live_runtime()
    op = ScriptedOperator(rt.gate)
    rt.feed_use_item(item_entry=910500)
    rt.feed_quest_completed(beat_ref="b00_onboarding")
    op.approve_next()  # approve b01 quest
    rt.feed_quest_completed(beat_ref="b01_zone_intro", character_level=2)  # fires shadow_pulse grant
    op.approve_next()  # approve grant
    aura_apply = [s for s in rc.executed if "'player_apply_aura'" in s]
    assert len(aura_apply) >= 1
    assert "946700" in aura_apply[0]  # shadow_pulse visible aura id
