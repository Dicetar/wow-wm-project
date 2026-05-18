"""Patron / Favor — a WM-owned patron whose favor rises with completed WM work.

Trigger: count of completed WM arcs/bounties. Decision: compute favor tier.
Native: wm_counter_set (favor state, Batch 3, lab-gated) + world_announce_to_player
(implemented). Reward: tiered reward refs (item/shell), allocated from fresh
reserved slots at install. Dry-run scaffold; never submits.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import sys
from typing import Any

from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.payload_contract import validate_native_action_payload


@dataclass(slots=True)
class PatronTier:
    threshold: int
    tier_name: str
    reward_ref: str


@dataclass(slots=True)
class PatronConfig:
    patron_key: str = "wm_patron"
    favor_per_completion: int = 10
    tiers: tuple[PatronTier, ...] = (
        PatronTier(30, "Acknowledged", "item:reserved_patron_token"),
        PatronTier(80, "Favored", "shell:reserved_patron_boon"),
        PatronTier(150, "Chosen", "shell:reserved_patron_mantle"),
    )


@dataclass(slots=True)
class PatronTrigger:
    player_guid: int
    player_name: str
    completed_wm_count: int


@dataclass(slots=True)
class PatronPlan:
    favor: int
    tier_name: str | None
    scene_steps: list[dict[str, Any]]
    reward_refs: list[str]
    native_readiness: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "favor": self.favor,
            "tier_name": self.tier_name,
            "scene": {"schema_version": "control.scene.v1", "steps": self.scene_steps},
            "reward_refs": self.reward_refs,
            "native_readiness": self.native_readiness,
        }


@dataclass(slots=True)
class PatronDecision:
    eligible: bool
    reason: str
    plan: PatronPlan | None = None
    contract_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reason": self.reason,
            "plan": self.plan.to_dict() if self.plan else None,
            "contract_issues": self.contract_issues,
        }


def _readiness(kinds: list[str]) -> dict[str, Any]:
    impl = [k for k in kinds if NATIVE_ACTION_KIND_BY_ID[k].implemented]
    pending = [k for k in kinds if not NATIVE_ACTION_KIND_BY_ID[k].implemented]
    return {
        "implemented": impl,
        "not_implemented": pending,
        "live_ready": not pending,
        "note": "announce implemented; wm_counter_set is Batch-3 lab-gated.",
    }


def build_patron_plan(trigger: PatronTrigger, config: PatronConfig) -> tuple[PatronPlan, list[str]]:
    favor = trigger.completed_wm_count * config.favor_per_completion
    tier = None
    for t in config.tiers:
        if favor >= t.threshold:
            tier = t
    announce = (
        f"The patron's favor for {trigger.player_name} stands at {favor}."
        + (f" You are {tier.tier_name}." if tier else "")
    )
    steps = [
        {
            "native_action_kind": "wm_counter_set",
            "payload": {"counter_key": f"{config.patron_key}:favor", "value": favor},
            "expected_effect": "favor counter persisted as hidden WM state",
        },
        {
            "native_action_kind": "world_announce_to_player",
            "payload": {"message": announce},
            "expected_effect": "patron acknowledges the player's standing",
        },
    ]
    issues: list[str] = []
    for step in steps:
        issues.extend(
            validate_native_action_payload(action_kind=step["native_action_kind"], payload=step["payload"])
        )
    plan = PatronPlan(
        favor=favor,
        tier_name=tier.tier_name if tier else None,
        scene_steps=steps,
        reward_refs=[tier.reward_ref] if tier else [],
        native_readiness=_readiness([s["native_action_kind"] for s in steps]),
    )
    return plan, issues


def evaluate_patron(trigger: PatronTrigger, config: PatronConfig | None = None) -> PatronDecision:
    config = config or PatronConfig()
    if trigger.completed_wm_count <= 0:
        return PatronDecision(eligible=False, reason="no completed WM work; no favor yet")
    plan, issues = build_patron_plan(trigger, config)
    if issues:
        return PatronDecision(eligible=False, reason="patron plan failed contract validation", plan=plan, contract_issues=issues)
    return PatronDecision(
        eligible=True,
        reason=f"favor {plan.favor}" + (f"; tier {plan.tier_name}" if plan.tier_name else "; below first tier"),
        plan=plan,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wm living.patron", description="Patron/Favor scaffold (dry-run only).")
    p.add_argument("--player-guid", type=int, required=True)
    p.add_argument("--player-name", required=True)
    p.add_argument("--completed-wm-count", type=int, required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    decision = evaluate_patron(PatronTrigger(args.player_guid, args.player_name, args.completed_wm_count))
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
        return 0 if decision.eligible else 1
    print(f"eligible : {decision.eligible}")
    print(f"reason   : {decision.reason}")
    if decision.plan:
        print(f"favor    : {decision.plan.favor}  tier={decision.plan.tier_name}")
        print(f"rewards  : {decision.plan.reward_refs}")
        print(f"native   : live_ready={decision.plan.native_readiness['live_ready']}")
    print("\nDRY-RUN ONLY: nothing was submitted.")
    return 0 if decision.eligible else 1


PATRON_STAGES = ("none", "acknowledged", "favored", "chosen")


class PatronManager:
    """Reads/writes patron favor state from wm_patron table."""

    def __init__(self, db_client: Any = None):
        self._db = db_client

    def get_favor(self, player_guid: int, patron_key: str = "wm_patron") -> int:
        if self._db is None:
            return 0
        rows = self._db.query(
            "SELECT favor FROM wm_patron WHERE player_guid = %s AND patron_key = %s",
            (player_guid, patron_key),
        )
        return int(rows[0]["favor"]) if rows else 0

    def set_favor(self, player_guid: int, favor: int,
                  tier_name: str | None = None,
                  patron_key: str = "wm_patron") -> None:
        if self._db is None:
            return
        self._db.execute(
            """
            INSERT INTO wm_patron (player_guid, patron_key, favor, tier_name)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE favor = VALUES(favor), tier_name = VALUES(tier_name),
                updated_at = NOW()
            """,
            (player_guid, patron_key, favor, tier_name),
        )

    def apply_completion(self, player_guid: int, player_name: str,
                         completed_wm_count: int,
                         config: PatronConfig | None = None) -> PatronDecision:
        config = config or PatronConfig()
        trigger = PatronTrigger(
            player_guid=player_guid,
            player_name=player_name,
            completed_wm_count=completed_wm_count,
        )
        decision = evaluate_patron(trigger, config)
        if decision.eligible and decision.plan:
            self.set_favor(player_guid, decision.plan.favor,
                           decision.plan.tier_name, config.patron_key)
        return decision


if __name__ == "__main__":
    sys.exit(main())
