"""Tests for NativeApplier — translates plans/proposals into wm_bridge_action_request INSERTs."""
from __future__ import annotations
import json
from wm.cli.native_applier import (
    NativeApplier, apply_quest_grant_proposal,
)
from wm.abilities.grant_compiler import GrantPlan, GrantStep
from wm.llm.proposal_adapter import Proposal, ProposalKind


class _RecordingClient:
    """Captures every SQL statement that would have been executed."""
    def __init__(self): self.executed: list[str] = []
    def execute(self, *, host, port, user, password, database, sql):  # mirrors mysql_cli
        self.executed.append(sql)
        return []


def test_apply_grant_plan_inserts_one_row_per_step():
    rc = _RecordingClient()
    applier = NativeApplier(client=rc, host="h", port=1, user="u", password="p", database="d",
                            created_by="wm-test")
    plan = GrantPlan(
        ability_id="shadow_pulse_aura_v1", character_guid=5407,
        idempotency_key="ability.grant.shadow_pulse_aura_v1:5407",
        steps=[GrantStep(action_kind="player_apply_aura", payload={"spell_id": 946700, "duration": -1})],
        revoke_path="managed.rollback.shadow_pulse_aura_v1",
    )
    applier.apply_grant_plan(plan)
    assert len(rc.executed) == 1
    sql = rc.executed[0]
    assert "INSERT INTO wm_bridge_action_request" in sql
    assert "'player_apply_aura'" in sql
    assert "ability.grant.shadow_pulse_aura_v1:5407" in sql
    assert "5407" in sql


def test_apply_active_plan_inserts_learn_and_apply_aura():
    rc = _RecordingClient()
    applier = NativeApplier(client=rc, host="h", port=1, user="u", password="p", database="d")
    plan = GrantPlan(
        ability_id="echo_lash_v1", character_guid=5407,
        idempotency_key="ability.grant.echo_lash_v1:5407",
        steps=[
            GrantStep(action_kind="player_learn_spell", payload={"spell_id": 946701}),
            GrantStep(action_kind="player_apply_aura", payload={"spell_id": 946701, "duration": 0}),
        ],
        revoke_path="managed.rollback.echo_lash_v1",
    )
    applier.apply_grant_plan(plan)
    assert len(rc.executed) == 2
    assert any("'player_learn_spell'" in s for s in rc.executed)
    assert any("'player_apply_aura'" in s for s in rc.executed)
    # idempotency keys are unique per step
    keys = [s.split("IdempotencyKey")[1].split("'")[1] for s in rc.executed]
    assert keys[0] != keys[1]


def test_quest_grant_proposal_inserts_quest_add_action():
    rc = _RecordingClient()
    applier = NativeApplier(client=rc, host="h", port=1, user="u", password="p", database="d")
    p = Proposal(
        kind=ProposalKind.QUEST, character_guid=5407,
        payload={"quest_release": {"title": "An Unfamiliar Weight",
                                   "grant_quest_id": 12,
                                   "objective": "Speak with McBride.",
                                   "description": "...",
                                   "giver_creature_entry": 197,
                                   "objective_kind": "talk_to_npc",
                                   "rewards": {"xp": 80}}},
        narrative_summary="b00 pinned",
        provenance={"mode": "pinned", "beat_id": "b00_onboarding"},
    )
    result = apply_quest_grant_proposal(p, applier=applier)
    assert result["ok"] is True
    assert "quest_id" in result and result["quest_id"] == 12
    assert len(rc.executed) == 1
    sql = rc.executed[0]
    assert "'quest_add'" in sql
    assert '"quest_id":12' in sql or "'quest_id': 12" in sql
    assert "5407" in sql


def test_quest_grant_without_quest_id_returns_ok_false():
    rc = _RecordingClient()
    applier = NativeApplier(client=rc, host="h", port=1, user="u", password="p", database="d")
    p = Proposal(
        kind=ProposalKind.QUEST, character_guid=5407,
        payload={"quest_release": {"title": "Generated only", "objective": "x", "description": "y",
                                   "giver_creature_entry": 197, "objective_kind": "kill_creature",
                                   "rewards": {"xp": 0}}},
    )
    result = apply_quest_grant_proposal(p, applier=applier)
    assert result["ok"] is False
    assert "grant_quest_id" in result["error"]
    assert rc.executed == []
