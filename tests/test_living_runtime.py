from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from wm.living.runtime import LivingStateStore, build_lane_steps, execute_lane, resolve_marker_session
from wm.panel.catalog import CommandCatalog


def _session(**over):
    base = {
        "character_guid": 3838,
        "character_name": "Marked",
        "source": "marker",
        "marker_spell_id": 946602,
        "bridge_event_id": 77,
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "marker": {"character_online": True},
    }
    base.update(over)
    return base


class FakeCoordinator:
    def __init__(self, status="applied"):
        self.status = status
        self.proposals = []

    def execute(self, *, proposal, mode, confirm_live_apply=False):
        self.proposals.append(proposal)
        status = "dry-run" if mode == "dry-run" else self.status
        return SimpleNamespace(status=status, to_dict=lambda: {"status": status})


def test_marker_session_rejects_wrong_stale_offline_and_noncanonical_targets():
    now = datetime.now(timezone.utc)
    assert resolve_marker_session(_session(), expected_player_guid=3838)["character_guid"] == 3838
    with pytest.raises(ValueError, match="conflicts"):
        resolve_marker_session(_session(), expected_player_guid=5406)
    with pytest.raises(ValueError, match="stale"):
        resolve_marker_session(_session(selected_at=(now - timedelta(hours=1)).isoformat()), now=now)
    with pytest.raises(ValueError, match="not confirmed online"):
        resolve_marker_session(_session(marker={"character_online": False}))
    with pytest.raises(ValueError, match="canonical marker"):
        resolve_marker_session(_session(marker_spell_id=946500))


def test_rumor_plan_injects_marker_session_identity():
    steps = build_lane_steps("rumor", {"lane": "rumor", "subject_name": "Gnolls", "deed_count": 10}, _session())
    assert "Marked" in steps[0]["payload"]["message"]
    assert "3838" not in steps[0]["payload"]["message"]


def test_scene_director_requires_two_bounded_owned_actors_and_cleanup():
    one_actor = [
        {"native_action_kind": "creature_spawn", "payload": {"creature_entry": 68, "arc_key": "a", "duration_ms": 1000}},
        {"native_action_kind": "creature_despawn", "payload": {"arc_key": "a"}},
    ]
    with pytest.raises(ValueError, match="at least two"):
        build_lane_steps("scene_director", {"lane": "scene_director", "steps": one_actor}, _session())

    two_actors = [
        {"native_action_kind": "creature_spawn", "payload": {"creature_entry": 68, "arc_key": "a", "duration_ms": 1000}},
        {"native_action_kind": "creature_spawn", "payload": {"creature_entry": 69, "arc_key": "b", "duration_ms": 1000}},
        {"native_action_kind": "creature_say", "payload": {"arc_key": "a", "text": "Begin."}},
        {"native_action_kind": "creature_despawn", "payload": {"arc_key": "a"}},
        {"native_action_kind": "creature_despawn", "payload": {"arc_key": "b"}},
    ]
    assert len(build_lane_steps("scene_director", {"lane": "scene_director", "steps": two_actors}, _session())) == 5


def test_apply_records_scoped_state_only_after_all_steps_succeed(tmp_path: Path):
    store = LivingStateStore(tmp_path)
    payload = {"lane": "patron", "completed_wm_count": 4, "run_key": "unit"}
    result = execute_lane(payload=payload, session=_session(), mode="apply", coordinator=FakeCoordinator(), state_store=store)
    assert result["status"] == "complete"
    assert store.load(3838)["lanes"]["patron"]["status"] == "active"

    failed_store = LivingStateStore(tmp_path / "failed")
    failed = execute_lane(payload=payload, session=_session(), mode="apply", coordinator=FakeCoordinator("failed"), state_store=failed_store)
    assert failed["status"] == "failed"
    assert failed_store.load(3838)["lanes"] == {}
    assert failed_store.load(3838)["audit"][-1]["status"] == "failed"


def test_living_panel_command_is_job_gated():
    entry = CommandCatalog().get("living.run")
    assert entry.mutating
    assert entry.dry_run_required
    assert entry.confirmation == "type_job_id"
