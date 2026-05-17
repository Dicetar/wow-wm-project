"""Oath / Contract — the player swears a constraint; keeping or breaking it matters.

Trigger: player accepts an oath (a tracked constraint with a target). State:
a hidden WM counter. Outcomes: kept -> reward ref; broken -> quest_fail +
counter clear. Native: wm_counter_set/clear, quest_fail (Batch 3, lab-gated)
+ world_announce_to_player (implemented). Dry-run scaffold; never submits.
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
class OathConfig:
    reward_ref: str = "shell:reserved_oath_boon"


@dataclass(slots=True)
class OathTrigger:
    player_guid: int
    player_name: str
    oath_key: str
    constraint_label: str
    target_count: int
    current_count: int = 0
    phase: str = "accept"  # accept | resolve
    oath_quest_id: int | None = None


@dataclass(slots=True)
class OathPlan:
    phase: str
    outcome: str | None
    scene_steps: list[dict[str, Any]]
    reward_refs: list[str]
    native_readiness: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "outcome": self.outcome,
            "scene": {"schema_version": "control.scene.v1", "steps": self.scene_steps},
            "reward_refs": self.reward_refs,
            "native_readiness": self.native_readiness,
        }


@dataclass(slots=True)
class OathDecision:
    eligible: bool
    reason: str
    plan: OathPlan | None = None
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
        "note": "announce implemented; wm_counter_*/quest_fail are Batch-3 lab-gated.",
    }


def build_oath_plan(trigger: OathTrigger, config: OathConfig) -> tuple[OathPlan, list[str]]:
    counter_key = f"oath:{trigger.oath_key}"
    if trigger.phase == "accept":
        outcome = None
        steps = [
            {
                "native_action_kind": "wm_counter_set",
                "payload": {"counter_key": counter_key, "value": 0},
                "expected_effect": "oath progress counter initialized",
            },
            {
                "native_action_kind": "world_announce_to_player",
                "payload": {"message": f"{trigger.player_name} swears: {trigger.constraint_label}."},
                "expected_effect": "oath acceptance is player-visible",
            },
        ]
    elif trigger.current_count >= trigger.target_count:
        outcome = "kept"
        steps = [
            {
                "native_action_kind": "world_announce_to_player",
                "payload": {"message": f"Oath kept. {trigger.constraint_label} held to the end."},
                "expected_effect": "success is player-visible",
            },
            {
                "native_action_kind": "wm_counter_clear",
                "payload": {"counter_key": counter_key},
                "expected_effect": "oath state cleared after success",
            },
        ]
    else:
        outcome = "broken"
        steps = []
        if trigger.oath_quest_id is not None:
            steps.append(
                {
                    "native_action_kind": "quest_fail",
                    "payload": {"quest_id": trigger.oath_quest_id},
                    "expected_effect": "oath contract quest failed",
                }
            )
        steps.extend(
            [
                {
                    "native_action_kind": "wm_counter_clear",
                    "payload": {"counter_key": counter_key},
                    "expected_effect": "oath state cleared after breach",
                },
                {
                    "native_action_kind": "world_announce_to_player",
                    "payload": {"message": f"Oath broken. {trigger.constraint_label} was not held."},
                    "expected_effect": "breach is player-visible",
                },
            ]
        )

    issues: list[str] = []
    for step in steps:
        issues.extend(
            validate_native_action_payload(action_kind=step["native_action_kind"], payload=step["payload"])
        )
    reward_refs = [config.reward_ref] if outcome == "kept" else []
    plan = OathPlan(
        phase=trigger.phase,
        outcome=outcome,
        scene_steps=steps,
        reward_refs=reward_refs,
        native_readiness=_readiness([s["native_action_kind"] for s in steps]),
    )
    return plan, issues


def evaluate_oath(trigger: OathTrigger, config: OathConfig | None = None) -> OathDecision:
    config = config or OathConfig()
    if trigger.phase not in {"accept", "resolve"}:
        return OathDecision(eligible=False, reason=f"unknown oath phase {trigger.phase!r}")
    if trigger.target_count <= 0:
        return OathDecision(eligible=False, reason="oath target_count must be positive")
    plan, issues = build_oath_plan(trigger, config)
    if issues:
        return OathDecision(eligible=False, reason="oath plan failed contract validation", plan=plan, contract_issues=issues)
    if trigger.phase == "accept":
        reason = f"oath {trigger.oath_key!r} sworn: {trigger.constraint_label}"
    else:
        reason = f"oath {trigger.oath_key!r} resolved: {plan.outcome}"
    return OathDecision(eligible=True, reason=reason, plan=plan)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wm living.oath", description="Oath/Contract scaffold (dry-run only).")
    p.add_argument("--player-guid", type=int, required=True)
    p.add_argument("--player-name", required=True)
    p.add_argument("--oath-key", required=True)
    p.add_argument("--constraint-label", required=True)
    p.add_argument("--target-count", type=int, required=True)
    p.add_argument("--current-count", type=int, default=0)
    p.add_argument("--phase", choices=["accept", "resolve"], default="accept")
    p.add_argument("--oath-quest-id", type=int, default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    trigger = OathTrigger(
        player_guid=args.player_guid,
        player_name=args.player_name,
        oath_key=args.oath_key,
        constraint_label=args.constraint_label,
        target_count=args.target_count,
        current_count=args.current_count,
        phase=args.phase,
        oath_quest_id=args.oath_quest_id,
    )
    decision = evaluate_oath(trigger)
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
        return 0 if decision.eligible else 1
    print(f"eligible : {decision.eligible}")
    print(f"reason   : {decision.reason}")
    if decision.plan:
        print(f"phase    : {decision.plan.phase}  outcome={decision.plan.outcome}")
        print(f"steps    : {[s['native_action_kind'] for s in decision.plan.scene_steps]}")
        print(f"native   : live_ready={decision.plan.native_readiness['live_ready']}")
    print("\nDRY-RUN ONLY: nothing was submitted.")
    return 0 if decision.eligible else 1


if __name__ == "__main__":
    sys.exit(main())
