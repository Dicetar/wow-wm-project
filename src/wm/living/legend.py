"""Local Legend — a zone remembers the player and marks them.

Trigger: zone deed count crosses tiered thresholds. Decision: pick the tier
(title + proclamation + rumor letter). Native: world_announce_to_player
(implemented) + player_add_title + player_send_mail (Batch 2, lab-gated).
Reward: a CharTitles title and a mailed letter, recorded as a journey
reward_instance at install. Dry-run scaffold; never submits.
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
class LegendTier:
    threshold: int
    tier_name: str
    title_id: int


@dataclass(slots=True)
class LegendConfig:
    tiers: tuple[LegendTier, ...] = (
        LegendTier(15, "Known", 1),
        LegendTier(40, "Renowned", 2),
        LegendTier(80, "Local Legend", 3),
    )


@dataclass(slots=True)
class LegendTrigger:
    player_guid: int
    player_name: str
    zone_name: str
    deed_count: int


@dataclass(slots=True)
class LegendPlan:
    tier_name: str
    title_id: int
    scene_steps: list[dict[str, Any]]
    reward_refs: list[str]
    native_readiness: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier_name": self.tier_name,
            "title_id": self.title_id,
            "scene": {"schema_version": "control.scene.v1", "steps": self.scene_steps},
            "reward_refs": self.reward_refs,
            "native_readiness": self.native_readiness,
        }


@dataclass(slots=True)
class LegendDecision:
    eligible: bool
    reason: str
    plan: LegendPlan | None = None
    contract_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reason": self.reason,
            "plan": self.plan.to_dict() if self.plan else None,
            "contract_issues": self.contract_issues,
        }


def _readiness(kinds: list[str], note: str) -> dict[str, Any]:
    impl = [k for k in kinds if NATIVE_ACTION_KIND_BY_ID[k].implemented]
    pending = [k for k in kinds if not NATIVE_ACTION_KIND_BY_ID[k].implemented]
    return {"implemented": impl, "not_implemented": pending, "live_ready": not pending, "note": note}


def _current_tier(deed_count: int, config: LegendConfig) -> LegendTier | None:
    tier = None
    for t in config.tiers:
        if deed_count >= t.threshold:
            tier = t
    return tier


def build_legend_plan(trigger: LegendTrigger, tier: LegendTier) -> tuple[LegendPlan, list[str]]:
    proclamation = f"{trigger.player_name} is now {tier.tier_name} of {trigger.zone_name}."
    letter_body = (
        f"Word of your deeds in {trigger.zone_name} has reached us. "
        f"You are {tier.tier_name} here now. Carry it well."
    )
    steps = [
        {
            "native_action_kind": "world_announce_to_player",
            "payload": {"message": proclamation},
            "expected_effect": "tier proclamation visible to the player",
        },
        {
            "native_action_kind": "player_add_title",
            "payload": {"title_id": tier.title_id},
            "expected_effect": "CharTitles title granted",
        },
        {
            "native_action_kind": "player_send_mail",
            "payload": {"subject": f"{tier.tier_name} of {trigger.zone_name}", "body": letter_body},
            "expected_effect": "rumor letter mailed to the player",
        },
    ]
    issues: list[str] = []
    for step in steps:
        issues.extend(
            validate_native_action_payload(action_kind=step["native_action_kind"], payload=step["payload"])
        )
    plan = LegendPlan(
        tier_name=tier.tier_name,
        title_id=tier.title_id,
        scene_steps=steps,
        reward_refs=[f"title:{tier.title_id}", f"zone_legend:{trigger.zone_name}:{tier.tier_name}"],
        native_readiness=_readiness(
            [s["native_action_kind"] for s in steps],
            "announce implemented; title/mail are Batch-2 lab-gated.",
        ),
    )
    return plan, issues


def evaluate_legend(trigger: LegendTrigger, config: LegendConfig | None = None) -> LegendDecision:
    config = config or LegendConfig()
    tier = _current_tier(trigger.deed_count, config)
    if tier is None:
        floor = config.tiers[0].threshold
        return LegendDecision(eligible=False, reason=f"{trigger.deed_count}/{floor} deeds in {trigger.zone_name}; no legend yet")
    plan, issues = build_legend_plan(trigger, tier)
    if issues:
        return LegendDecision(eligible=False, reason="legend plan failed contract validation", plan=plan, contract_issues=issues)
    return LegendDecision(eligible=True, reason=f"{trigger.deed_count} deeds; {trigger.player_name} is {tier.tier_name} of {trigger.zone_name}", plan=plan)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wm living.legend", description="Local Legend scaffold (dry-run only).")
    p.add_argument("--player-guid", type=int, required=True)
    p.add_argument("--player-name", required=True)
    p.add_argument("--zone-name", required=True)
    p.add_argument("--deed-count", type=int, required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    trigger = LegendTrigger(args.player_guid, args.player_name, args.zone_name, args.deed_count)
    decision = evaluate_legend(trigger)
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
        return 0 if decision.eligible else 1
    print(f"eligible : {decision.eligible}")
    print(f"reason   : {decision.reason}")
    if decision.plan:
        print(f"tier     : {decision.plan.tier_name} (title {decision.plan.title_id})")
        print(f"native   : live_ready={decision.plan.native_readiness['live_ready']} "
              f"pending={decision.plan.native_readiness['not_implemented']}")
    print("\nDRY-RUN ONLY: nothing was submitted.")
    return 0 if decision.eligible else 1


if __name__ == "__main__":
    sys.exit(main())
