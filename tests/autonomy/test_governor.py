from __future__ import annotations

from datetime import datetime, timedelta, timezone

from wm.autonomy.governor import AutonomyBudget, AutonomyGovernor

NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _recent(*offsets_seconds_kinds):
    # each arg is (seconds_ago, kind)
    return [{"at": NOW - timedelta(seconds=s), "action_kind": k} for s, k in offsets_seconds_kinds]


def test_low_risk_within_budget_auto_applies():
    gov = AutonomyGovernor(AutonomyBudget(max_actions_per_window=6, max_risk="low", cooldown_seconds=0))
    d = gov.evaluate(action_kind="player_chat_message", risk="low", recent_actions=[], now=NOW)
    assert d.allow is True and d.requires_review is False


def test_risk_above_ceiling_is_rejected():
    gov = AutonomyGovernor(AutonomyBudget(max_risk="low"))
    d = gov.evaluate(action_kind="creature_spawn", risk="medium", recent_actions=[], now=NOW)
    assert d.allow is False and d.requires_review is False
    assert "exceeds max" in d.reason


def test_ceiling_off_rejects_everything():
    gov = AutonomyGovernor(AutonomyBudget(max_risk="off"))
    d = gov.evaluate(action_kind="player_chat_message", risk="low", recent_actions=[], now=NOW)
    assert d.allow is False and not d.requires_review


def test_at_ceiling_medium_is_queued_for_review():
    gov = AutonomyGovernor(AutonomyBudget(max_risk="medium", cooldown_seconds=0))
    d = gov.evaluate(action_kind="creature_spawn", risk="medium", recent_actions=[], now=NOW)
    assert d.allow is False and d.requires_review is True


def test_rate_cap_rejects_when_window_full():
    gov = AutonomyGovernor(AutonomyBudget(max_actions_per_window=2, window_seconds=600, cooldown_seconds=0, max_risk="low"))
    recent = _recent((10, "x"), (20, "y"))
    d = gov.evaluate(action_kind="player_chat_message", risk="low", recent_actions=recent, now=NOW)
    assert d.allow is False and "budget" in d.reason


def test_old_actions_fall_outside_window():
    gov = AutonomyGovernor(AutonomyBudget(max_actions_per_window=2, window_seconds=600, cooldown_seconds=0, max_risk="low"))
    recent = _recent((10, "x"), (5000, "y"))  # second one is well outside the window
    d = gov.evaluate(action_kind="player_chat_message", risk="low", recent_actions=recent, now=NOW)
    assert d.allow is True


def test_per_kind_cap_is_independent():
    gov = AutonomyGovernor(AutonomyBudget(
        max_actions_per_window=10, window_seconds=600, cooldown_seconds=0, max_risk="low",
        per_kind_caps={"world_announce_to_player": 1},
    ))
    recent = _recent((30, "world_announce_to_player"))
    capped = gov.evaluate(action_kind="world_announce_to_player", risk="low", recent_actions=recent, now=NOW)
    assert capped.allow is False and "per-kind" in capped.reason
    other = gov.evaluate(action_kind="player_chat_message", risk="low", recent_actions=recent, now=NOW)
    assert other.allow is True


def test_cooldown_blocks_recent_action():
    gov = AutonomyGovernor(AutonomyBudget(max_actions_per_window=10, cooldown_seconds=120, max_risk="low"))
    recent = _recent((30, "x"))  # 30s ago, inside 120s cooldown
    d = gov.evaluate(action_kind="player_chat_message", risk="low", recent_actions=recent, now=NOW)
    assert d.allow is False and "cooldown" in d.reason


def test_cooldown_clears_after_window():
    gov = AutonomyGovernor(AutonomyBudget(max_actions_per_window=10, cooldown_seconds=120, max_risk="low"))
    recent = _recent((200, "x"))  # 200s ago, past cooldown
    d = gov.evaluate(action_kind="player_chat_message", risk="low", recent_actions=recent, now=NOW)
    assert d.allow is True


def test_iso_string_timestamps_accepted():
    gov = AutonomyGovernor(AutonomyBudget(max_actions_per_window=1, cooldown_seconds=0, max_risk="low"))
    recent = [{"at": (NOW - timedelta(seconds=10)).isoformat(), "action_kind": "x"}]
    d = gov.evaluate(action_kind="player_chat_message", risk="low", recent_actions=recent, now=NOW)
    assert d.allow is False  # window already has 1 (the cap)


def test_budget_from_config():
    b = AutonomyBudget.from_config({"autonomy_per_window": 3, "autonomy_max_risk": "medium", "autonomy_cooldown_seconds": 30})
    assert b.max_actions_per_window == 3 and b.max_risk == "medium" and b.cooldown_seconds == 30
