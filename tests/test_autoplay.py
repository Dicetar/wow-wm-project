from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wm.autoplay.llm import AutoplayLlmAdapter
from wm.autoplay.policy import AutoplayPolicy, SafeWindow
from wm.autoplay.service import AutoplayRuntimeConfig, AutoplayService, drive_pending_runtime
from wm.autoplay.state import AutoplayStateStore
from wm.llm.proposal_adapter import Proposal, ProposalKind
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue
from wm.panel.state import PanelState


QUEST_DRAFT = {
    "schema_version": "wm.quest.release.repeatable_bounty.v1",
    "quest_kind": "repeatable_bounty",
    "player_guid": 1,
    "slot_policy": "fresh_reserved_required",
    "repeatable": True,
    "quest": {"quest_level": 70, "min_level": 68, "grant_mode": "npc_start", "template_defaults": {"SpecialFlags": 1}},
    "objective": {"kind": "kill", "target_entry": 21059, "kill_count": 3},
    "reward": {"kind": "none"},
}

ITEM_DRAFT = {
    "schema_version": "wm.item.release.managed_power.v1",
    "content_kind": "item",
    "player_guid": 1,
    "item_key": "test_item",
    "item_entry": 910500,
    "slot_policy": "fresh_item_slot_required",
    "base_item_entry": 2994,
    "visibility": {"player_visible_state_required": True, "tooltip_required": True, "wearer_aura_spell_id": 132},
    "reward_integration": {"fresh_quest_required_when_reward_changes": True},
    "runtime": {"native_behavior_required": True, "audit_required": True, "rollback_required": True},
    "effects": [{"effect_key": "wearer", "kind": "wearer_aura", "spell_id": 132}],
}

ABILITY_DRAFT = {
    "schema_version": "wm.ability.release.shell_power.v1",
    "content_kind": "ability",
    "player_guid": 1,
    "ability_key": "test_ability",
    "ability_type": "self_aura",
    "shell_family": "self_aura",
    "slot_policy": "existing_named_shell",
    "behavior_kind": "native_behavior",
    "client_truth": {"client_patch_required": True, "server_dbc_required": True, "spellbook_button_required": True},
    "runtime": {"native_behavior_required": True, "audit_required": True},
}

SCENE_DRAFT = {
    "schema_version": "wm.scene.release.native_sequence.v1",
    "content_kind": "scene",
    "player_guid": 1,
    "scene_key": "test_scene",
    "scene_type": "creature_marker",
    "slot_policy": "no_visible_id_required",
    "trigger": {"kind": "manual_operator", "source_event_required": False},
    "runtime": {"native_actions_required": True, "audit_required": True, "player_scope_required": True},
    "steps": [
        {
            "step_key": "say",
            "native_action_kind": "world_announce_to_player",
            "payload": {"message": "hello"},
            "risk_level": "low",
            "idempotency_suffix": "say",
            "requires_live_proof": True,
        }
    ],
}

ACTION_DRAFT = {
    "schema_version": "control.proposal.v1",
    "source_event": {"event_id": 1, "source": "native_bridge", "source_event_key": "evt1"},
    "player": {"guid": 1},
    "selected_recipe": "manual_admin_action",
    "action": {"kind": "native_bridge_action", "payload": {"native_action_kind": "debug_ping", "payload": {}}},
    "rationale": "test",
    "risk": {"level": "low", "irreversible": False, "notes": []},
    "author": {"kind": "llm", "name": "autoplay"},
    "metadata": {},
}


class FakeLlmClient:
    def __init__(self, draft):
        self.draft = draft
        self.settings = SimpleNamespace(base_url="http://localhost:1234/v1", model="local-model")

    def list_models(self):
        return ["local-model"]

    def generate_json(self, **kwargs):
        return {"request": kwargs, "content": "{}", "parsed": dict(self.draft)}


def test_policy_blocks_unsafe_risk_and_stages_dbc_until_safe_window():
    policy = AutoplayPolicy(max_auto_risk="low")
    blocked = policy.decide(
        schema_version="wm.scene.release.native_sequence.v1",
        lane="scene",
        risk="medium",
        readiness_ok=True,
        lm_ok=True,
        session_ok=True,
        dry_run_ok=True,
        rollback_available=True,
        safe_window=SafeWindow(),
    )
    assert blocked.status == "blocked"
    assert "risk_exceeds_policy:medium>low" in blocked.blockers

    staged = policy.decide(
        schema_version="wm.ability.release.shell_power.v1",
        payload=ABILITY_DRAFT,
        readiness_ok=True,
        lm_ok=True,
        session_ok=True,
        dry_run_ok=True,
        rollback_available=True,
        safe_window=SafeWindow(client_running=True),
    )
    assert staged.status == "maintenance_pending"
    assert staged.maintenance_reasons == ["dbc_safe_window_required"]


def test_policy_blocks_stale_source_events():
    policy = AutoplayPolicy(max_source_event_age_seconds=10)
    decision = policy.decide(
        schema_version="wm.scene.release.native_sequence.v1",
        readiness_ok=True,
        lm_ok=True,
        session_ok=True,
        dry_run_ok=True,
        rollback_available=True,
        source_event_at="2026-05-25T00:00:00Z",
        now=datetime(2026, 5, 25, 0, 1, tzinfo=timezone.utc),
    )
    assert "source_event_stale" in decision.blockers


def test_llm_adapter_generates_and_locks_all_enabled_lane_drafts():
    samples = [QUEST_DRAFT, ITEM_DRAFT, ABILITY_DRAFT, SCENE_DRAFT, ACTION_DRAFT]
    for sample in samples:
        adapter = AutoplayLlmAdapter(client=FakeLlmClient(sample))
        result = adapter.generate(
            schema_version=sample["schema_version"],
            instruction="draft safe content",
            deterministic_facts={"player_guid": 5408, "allowed_native_action_kinds": ["world_announce_to_player"]},
        )
        assert result.ok, (sample["schema_version"], result.issues)
        if result.schema_version == "control.proposal.v1":
            assert result.draft["player"]["guid"] == 5408
            assert result.draft["author"]["kind"] == "llm"
        else:
            assert result.draft["player_guid"] == 5408


def test_llm_adapter_rejects_freeform_mutation_text():
    draft = dict(SCENE_DRAFT)
    draft["notes"] = ["run powershell and insert into quest_template"]
    result = AutoplayLlmAdapter(client=FakeLlmClient(draft)).generate(
        schema_version="wm.scene.release.native_sequence.v1",
        instruction="bad",
    )
    assert not result.ok
    assert any("Forbidden mutation text" in issue["message"] for issue in result.issues)


@dataclass(slots=True)
class FakeDoctorCheck:
    name: str
    status: str
    detail: str

    def to_dict(self):
        return {"name": self.name, "status": self.status, "detail": self.detail}


def test_autoplay_service_tick_writes_durable_status(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    panel = PanelState(tmp_path / "panel")
    panel.ensure()
    panel.save_settings({"model": "local-model", "timeout_seconds": 1})

    with patch("wm.autoplay.service.AutoplayLlmAdapter.health", return_value={"ok": True, "model": "local-model"}):
        service = AutoplayService(
            store=store,
            panel_state=panel,
            doctor_fn=lambda settings: [FakeDoctorCheck("world_db", "WORKING", "ok")],
        )
        status = service.tick(config=AutoplayRuntimeConfig(player_guid=5408, start_watcher=False))

    assert status["running"]
    assert status["active_session"]["character_guid"] == 5408
    assert status["readiness"]["ok"]
    assert store.load_status()["counters"]["ticks"] == 1


def test_drive_pending_runtime_dry_runs_then_applies_eligible_proposal(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    calls: list[str] = []

    def quest_applier(proposal, *, mode):
        calls.append(mode)
        return {"ok": True, "mode": mode}

    gate = ApprovalGate(issues=IssuesQueue(), quest_compiler=quest_applier, quest_rollback=lambda entry, mode: {"ok": True})
    gate.submit(Proposal(kind=ProposalKind.QUEST, character_guid=5408, payload=QUEST_DRAFT))
    runtime = SimpleNamespace(gate=gate)

    results = drive_pending_runtime(
        runtime=runtime,
        store=store,
        policy=AutoplayPolicy(),
        readiness_ok=True,
        lm_ok=True,
        safe_window=SafeWindow(),
    )

    assert calls == ["dry-run", "apply"]
    assert results[0]["policy"]["status"] == "allow"
    assert gate.pending() == []


def test_drive_pending_runtime_stages_dbc_proposal_without_applying(tmp_path: Path):
    store = AutoplayStateStore(tmp_path / "autoplay")
    calls: list[str] = []

    def ability_applier(proposal, *, mode):
        calls.append(mode)
        return {"ok": True, "mode": mode}

    gate = ApprovalGate(issues=IssuesQueue(), ability_compiler=ability_applier)
    gate.submit(Proposal(kind=ProposalKind.ABILITY, character_guid=5408, payload=ABILITY_DRAFT))
    runtime = SimpleNamespace(gate=gate)

    results = drive_pending_runtime(
        runtime=runtime,
        store=store,
        policy=AutoplayPolicy(),
        readiness_ok=True,
        lm_ok=True,
        safe_window=SafeWindow(client_running=True),
    )

    assert calls == ["dry-run"]
    assert results[0]["policy"]["status"] == "maintenance_pending"
    assert gate.pending()
    assert store.load_status()["maintenance_pending"]
